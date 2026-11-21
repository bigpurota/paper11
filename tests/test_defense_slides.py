"""Check navigation in the packaged PowerPoint, independently of the slide builder."""
import csv
from pathlib import Path, PurePosixPath
from posixpath import join, normpath
from xml.etree import ElementTree as ET
from zipfile import ZipFile


DECK = Path(__file__).resolve().parents[1] / "slides" / "paper11.pptx"
OFFICE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PRESENTATION = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
DRAWING = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
TALK = 14  # spoken slides before the question index


def slide_targets(package, owner):
    part = PurePosixPath(owner)
    relations = part.parent / "_rels" / (part.name + ".rels")
    result = {}
    for rel in ET.fromstring(package.read(str(relations))):
        if not rel.get("Type").endswith("/slide") or rel.get("TargetMode") == "External":
            continue
        target = rel.get("Target")
        absolute = target.lstrip("/") if target.startswith("/") else join(str(part.parent), target)
        result[rel.get("Id")] = normpath(absolute)
    return result


def test_all_backup_slides_reachable_from_the_menu_and_back():
    with ZipFile(DECK) as package:
        manifest = ET.fromstring(package.read("[Content_Types].xml"))
        overrides = [node.attrib["PartName"] for node in manifest if "PartName" in node.attrib]
        assert len(overrides) == len(set(overrides))
        presentation = "ppt/presentation.xml"
        targets = slide_targets(package, presentation)
        tree = ET.fromstring(package.read(presentation))
        ordered = [targets[node.attrib[OFFICE+"id"]] for node in tree.find(PRESENTATION+"sldIdLst")]
        assert len(ordered) > TALK + 1 and len(set(ordered)) == len(ordered)
        menu = ordered[TALK]

        def destinations(slide):
            linked = slide_targets(package, slide)
            page = ET.fromstring(package.read(slide))
            return {linked[node.get(OFFICE+"id")] for node in page.iter(DRAWING+"hlinkClick")
                    if node.get(OFFICE+"id") in linked}

        assert menu in destinations(ordered[TALK - 1])
        assert set(ordered[TALK + 1:]).issubset(destinations(menu))
        for backup in ordered[TALK + 1:]:
            assert menu in destinations(backup), backup


def test_defense_shows_both_archived_platform_refits():
    archive = DECK.parents[1] / "docs" / "refits" / "taiwan-hard-cutoff.csv"
    with archive.open(newline="") as stream:
        refits = {row["platform"]: row for row in csv.DictReader(stream)}
    with ZipFile(DECK) as package:
        slide = ET.fromstring(package.read("ppt/slides/slide9.xml"))
    text = " ".join(run.text or "" for run in slide.iter(DRAWING+"t"))
    pairs = []
    for platform in ("macos-arm64", "linux-x86_64"):
        row = refits[platform]
        estimates = [f"{100 * float(row[key]):+.2f}".replace("-", "−")
                     for key in ("B_minus_A", "Bplus_minus_Aplus")]
        pairs.append(" / ".join(estimates))
    assert "two independent refits" in text.lower()
    assert f"{pairs[0]} and {pairs[1]} pp" in text
