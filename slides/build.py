"""Refresh the editable PPTX from checked analysis outputs, then export its PDF."""
import csv
from pathlib import Path
import posixpath
import re
import shutil
import statistics
import subprocess
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZipFile


HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
SOURCES = {"simulation_fig2.png", "calibration.png"}
TOKEN = re.compile(rb"\{\{([a-z0-9_]+)\}\}")
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def read_table(name):
    with (RESULTS / (name + ".csv")).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def matching(rows, **keys):
    return [row for row in rows if all(row[k] == str(v) for k, v in keys.items())]


def one(rows, **keys):
    records = matching(rows, **keys)
    if len(records) != 1:
        raise ValueError(f"Expected exactly one source record for {keys}; found {len(records)}")
    return records[0]


def number(x):
    return f"{float(x) * 100:.2f}"


def percent(x):
    return number(x) + "%"


def signed(x):
    return f"{float(x) * 100:+.2f}"


def result_fields():
    comparison = read_table("paper_comparison")
    training = read_table("training")
    uncertainty = read_table("uncertainty")
    eval_rmse = read_table("evaluation_rmse")
    policy = read_table("policy")
    sensitivity = read_table("simulation_comparison")
    audits = read_table("audit_summary")
    cohort = read_table("cohort")
    fields = {}
    for key, dataset in [("orig", "monedo"), ("tw", "taiwan"), ("pr", "prosper")]:
        for label, method in [("a", "accepts"), ("i", "ipw"), ("b", "bayes")]:
            fields[f"{key}_eval_{label}"] = number(one(comparison, table=2, method=method, metric="abr")[dataset])
        for metric in ("auc", "brier", "pauc", "abr"):
            a, b = [float(one(comparison, table=3, method=method, metric=metric)[dataset])
                    for method in ("accepts", "basl")]
            fields[f"{key}_pair_{metric}"] = f"{a:.4f} / {b:.4f}"
        baseline = float(one(comparison, table=3, method="accepts", metric="abr")[dataset])
        basl = float(one(comparison, table=3, method="basl", metric="abr")[dataset])
        fields[f"{key}_tr_a"] = percent(baseline)
        fields[f"{key}_tr_b"] = percent(basl)
        fields[f"{key}_delta"] = signed(basl - baseline)
        if dataset == "monedo":
            continue
        ci = one(uncertainty, dataset=dataset, contrast="basl_minus_accepts_abr")
        fields[f"{key}_ci"] = f"[{signed(ci['ci_low'])}, {signed(ci['ci_high'])}]"
        fields[f"{dataset}_n"] = format(int(one(cohort, dataset=dataset)["population_rows"]), ",")
        guarded = matching(training, dataset=dataset, method="basl_guarded")
        fields[f"{key}_guard"] = percent(statistics.mean(float(r["abr"]) for r in guarded))
        for label, method in [("low", "bayes_odds_half"), ("high", "bayes_odds_double")]:
            fields[f"{key}_{label}"] = number(one(eval_rmse, dataset=dataset, method=method, metric="abr")["rmse"])
        selected = matching(policy, dataset=dataset, method="bayes", lgd="0.5")
        for label, metric in [("approval", "test_approval"), ("margin", "profit_per_applicant")]:
            fields[f"{key}_{label}"] = percent(statistics.mean(float(row[metric]) for row in selected))
        fields[f"{key}_profit_delta"] = number(
            one(uncertainty, dataset=dataset, contrast="bayes_minus_accepts_profit_at_lgd50")["estimate"])
        for label, design in [("all", "all_rejects"), ("target", "policy_rejects")]:
            fields[f"{key}_audit_{label}"] = number(one(audits, dataset=dataset, design=design,
                                                        n_audited=50)["audit_rmse"])
        fields[f"{key}_audit_prior"] = number(one(audits, dataset=dataset, design="all_rejects",
                                                  n_audited=50)["prior_only_rmse"])
    for label, method in [("a", "accepts"), ("b", "basl")]:
        row = one(training, dataset="prosper", method=method)
        fields[f"pr_auc_{label}"] = f"{float(row['auc']):.3f}"
    fields["pr_lift"] = f"{float(one(training, dataset='prosper', method='basl')['lift10']):.2f}"
    for key, stat in [("ignore", "accept_eval_rmse"), ("bayes", "bayes_eval_rmse"),
                      ("recovery", "basl_recovery_fraction"), ("guard", "basl_conservative_recovery_fraction")]:
        estimate = one(sensitivity, metric="abr", statistic=stat)["estimate"]
        fields["sim_" + key] = percent(estimate) if key in {"recovery", "guard"} else number(estimate)
    return fields


def image_paths(template):
    """Match a figure's slide alt text to its embedded media target."""
    assets = {}
    for slide in template.namelist():
        if not re.fullmatch(r"ppt/slides/slide\d+\.xml", slide):
            continue
        xml = ET.fromstring(template.read(slide))
        for pic in xml.findall(".//p:pic", NS):
            label = pic.find("p:nvPicPr/p:cNvPr", NS).get("descr")
            if label not in SOURCES:
                continue
            relid = pic.find("p:blipFill/a:blip", NS).get("{" + NS["r"] + "}embed")
            directory, name = posixpath.split(slide)
            rels = ET.fromstring(template.read(f"{directory}/_rels/{name}.rels"))
            target = next(r.get("Target") for r in rels if r.get("Id") == relid)
            item = posixpath.normpath(posixpath.join(directory, target)).lstrip("/")
            assets[item] = label
    if set(assets.values()) != SOURCES:
        raise ValueError("Missing figure alt text in slide template")
    return assets


def refresh_pptx(target, fields):
    def substitute(match):
        return fields[match.group(1).decode()].encode("utf-8")

    with ZipFile(HERE / "template.pptx") as src, ZipFile(target, "w") as out:
        assets = image_paths(src)
        for item in src.infolist():
            payload = src.read(item)
            if item.filename in assets:
                payload = (RESULTS / assets[item.filename]).read_bytes()
            elif re.fullmatch(r"ppt/(slides/slide|notesSlides/notesSlide)\d+\.xml", item.filename):
                payload = TOKEN.sub(substitute, payload)
                if b"{{" in payload or b"}}" in payload:
                    raise ValueError(f"Unresolved numeric field in {item.filename}")
            out.writestr(item, payload)


def main():
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if not office:
        raise SystemExit("Install LibreOffice and make soffice available on PATH to export the PDF.")
    # A private LibreOffice profile also works while a desktop session is open.
    with tempfile.TemporaryDirectory(dir=HERE) as work:
        tmp = Path(work)
        pptx = tmp / "paper11.pptx"
        refresh_pptx(pptx, result_fields())
        subprocess.run([office, f"-env:UserInstallation={(tmp / 'profile').as_uri()}", "--headless",
                        "--convert-to", "pdf", "--outdir", str(tmp), str(pptx)], check=True)
        pdf = tmp / "paper11.pdf"
        if not pdf.exists() or not pdf.stat().st_size:
            raise RuntimeError("LibreOffice did not produce a PDF")
        for output in (pptx, pdf):
            output.replace(HERE / output.name)


if __name__ == "__main__":
    main()
