"""Assemble the main talk and its linked question index from the two editable decks."""
from copy import deepcopy
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PK = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
AP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
NS = {"p": P, "a": A}
INDEX = 15  # fourteen talk slides, then the question index

# Short menu label and source page: a number refers to the 38-page evidence book,
# "talk:n" to a slide of the talk template kept for questions after the summary.
TOPICS = [
    ("Data and holdout design", 4), ("Paper Table 2 · evaluation error", 6),
    ("Paper Table 3 · four score metrics", 22), ("Calibration and AUC", 18),
    ("Borrowers between cutoffs", "talk:15"), ("Identical totals, opposite decisions", 12),
    ("How many repayments to audit?", 26), ("Philippine randomized offers", 11),
    ("Pilot break-even horizon", 28), ("An Estonian decision switch", 30),
    ("Pilot selection on later loans", 32), ("The missed Finnish pilot", 33),
    ("Historical frequency vs. boosting", 35), ("Pooling at Wells Fargo", 38),
    ("Netherlands · early defaults", "talk:16"), ("Czech bank · early arrears", "talk:17"),
]



def topic_page(title):
    return INDEX + 1 + [name for name, _ in TOPICS].index(title)


for prefix, uri in (("p", P), ("a", A), ("r", R)):
    ET.register_namespace(prefix, uri)


def xml(element):
    # OPC manifests and relationship files must retain their package default namespace.
    namespace = element.tag[1:].partition("}")[0]
    if namespace in (CT, PK):
        ET.register_namespace("", namespace)
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def slide_parts(number):
    slide = f"ppt/slides/slide{number}.xml"
    notes = f"ppt/notesSlides/notesSlide{number}.xml"
    return (slide, f"ppt/slides/_rels/slide{number}.xml.rels",
            notes, f"ppt/notesSlides/_rels/notesSlide{number}.xml.rels")


def shapes(slide):
    return {s.find("p:nvSpPr/p:cNvPr", NS).get("name"): s for s in slide.findall(".//p:sp", NS)}


def set_text(body, text):
    paragraphs = body.findall("a:p", NS)
    first = paragraphs[0]
    for paragraph in paragraphs[1:]:
        body.remove(paragraph)
    runs = first.findall("a:r", NS)
    for run in runs[1:]:
        first.remove(run)
    runs[0].find("a:t", NS).text = text


def label(shape, text):
    set_text(shape.find("p:txBody", NS), text)


def textbox(tree, name, text, x, y, width, height, size, bold=False, align="l", jump=None):
    proto = next(sh for sh in tree.findall("p:sp", NS)
                 if sh.find("p:nvSpPr/p:cNvPr", NS).get("name") == "TextBox 3")
    shape = deepcopy(proto)
    props = shape.find("p:nvSpPr/p:cNvPr", NS)
    next_id = max(int(e.get("id")) for e in tree.findall(".//p:cNvPr", NS)) + 1
    props.set("id", str(next_id))
    props.set("name", name)
    xfrm = shape.find("p:spPr/a:xfrm", NS)
    xfrm.find("a:off", NS).attrib.update(x=str(9525*x), y=str(9525*y))
    xfrm.find("a:ext", NS).attrib.update(cx=str(9525*width), cy=str(9525*height))
    label(shape, text)
    para = shape.find("p:txBody/a:p", NS)
    para.find("a:pPr", NS).set("algn", align)
    prop = para.find("a:r/a:rPr", NS)
    prop.set("sz", str(round(100*size)))
    prop.set("b", str(int(bold)))
    if jump:
        attrs = {f"{{{R}}}id": jump, "action": "ppaction://hlinksldjump", "tooltip": text}
        ET.SubElement(props, f"{{{A}}}hlinkClick", attrs)
        ET.SubElement(prop, f"{{{A}}}hlinkClick", attrs)
    tree.append(shape)


def link(rels, page):
    rid = f"GoTo{page}"
    if not any(r.get("Id") == rid for r in rels):
        ET.SubElement(rels, f"{{{PK}}}Relationship",
                      Id=rid, Type=R+"/slide", Target=f"slide{page}.xml")
    return rid


def menu(slide, rels):
    tree = slide.find("p:cSld/p:spTree", NS)
    for shape in list(tree):
        info = shape.find(".//p:cNvPr", NS)
        if info is not None and info.get("name") not in {"Title", "TextBox 2", "TextBox 3", "Picture 1"}:
            tree.remove(shape)
    header = shapes(slide)
    label(header["Title"], "Questions and supporting evidence")
    header["TextBox 2"].findall("p:txBody/a:p", NS)[-1].find(".//a:t", NS).text = "Question index"
    label(header["TextBox 3"], str(INDEX))
    for col, group_names in enumerate((("Study design and replication", "Policy comparisons"),
                                       ("Learning from pilot loans", "Early signals and transfer"))):
        x = 65 + 605*col
        for y, group_name in zip((162, 470), group_names):
            textbox(tree, group_name, group_name, x, y, 555, 43, 21, bold=True)
        for row in range(8):
            topic_index = 8*col+row
            title, _ = TOPICS[topic_index]
            page = INDEX + topic_index + 1
            y = 218+49*row if row < 5 else 526+49*(row-5)
            textbox(tree, title, f"{page}   {title}", x, y, 566, 44, 17.5, jump=link(rels, page))


def notes_body(notes):
    return next(sp.find("p:txBody", NS) for sp in notes.findall(".//p:sp", NS)
                if sp.find("p:nvSpPr/p:nvPr/p:ph[@type='body']", NS) is not None)


def navigation(slide, rels, page):
    tree = slide.find("p:cSld/p:spTree", NS)
    caption = "Questions  →" if page == INDEX - 1 else "←  Question index"
    textbox(tree, "Evidence navigation", caption, 832, 34, 267, 37, 16,
            align="r", jump=link(rels, INDEX))


def adapt_notes(notes, page):
    if page < INDEX:
        return  # Spoken slides keep their timed notes unchanged.
    body = notes_body(notes)
    text = " ".join(node.text or "" for node in body.findall(".//a:t", NS))
    # The evidence book originally had a second timing plan. The spoken
    # presentation ends before the question index.
    if text.startswith("Time: "):
        text = text.partition(". ")[2]
    # Talk slides reused as evidence keep their notes without the spoken timing.
    text = re.sub(r"^\d+:\d\d\. ", "", text)
    text = text.removeprefix("Backup for questions. ").removeprefix("Back-up. ")
    set_text(body, text)


def assemble(talk, evidence, output, fields):
    with ZipFile(talk) as base, ZipFile(evidence) as library:
        parts = {p: base.read(p) for p in base.namelist()}
        manifest = ET.fromstring(parts["[Content_Types].xml"])
        declared = {node.get("PartName") for node in manifest.findall(f"{{{CT}}}Override")}
        pres = ET.fromstring(parts["ppt/presentation.xml"])
        pres_rels = ET.fromstring(parts["ppt/_rels/presentation.xml.rels"])
        page_ids = pres.find("p:sldIdLst", NS)
        # Talk-template slides after the summary are reused as evidence pages below.
        spoken = {f"TalkSlide{k}" for k in range(1, INDEX)}
        for node in list(page_ids):
            if node.get(f"{{{R}}}id") not in spoken:
                page_ids.remove(node)
        for rel in list(pres_rels):
            if rel.get("Id", "").startswith("TalkSlide") and rel.get("Id") not in spoken:
                pres_rels.remove(rel)
        slide_count = INDEX + len(TOPICS)
        for page in range(5, slide_count+1):
            new = page >= INDEX
            if page < INDEX:
                n, source = page, base
            elif page == INDEX:
                n, source = 9, base
            else:
                original = TOPICS[page-INDEX-1][1]
                n, source = (int(original[5:]), base) if isinstance(original, str) else (original, library)
            slide, srels, notes, nrels = [ET.fromstring(source.read(p)) for p in slide_parts(n)]
            if page < INDEX:
                for node in slide.findall(".//a:t", NS):
                    node.text = (node.text or "").replace("evidence slide 18", f"page {topic_page('Calibration and AUC')}")
            if page == INDEX:
                menu(slide, srels)
                set_text(notes_body(notes), "Use any entry to open that evidence page. Each reserve page links back here.")
            elif page > INDEX:
                head = shapes(slide)
                label(head["TextBox 3"], str(page))
                header_lines = head["TextBox 2"].findall("p:txBody/a:p", NS)
                header_lines[-1].find(".//a:t", NS).text = "Supporting evidence"
                # Evidence-book cross references do not apply to the assembled numbering.
                for node in slide.findall(".//a:t", NS):
                    node.text = (node.text or "").replace(" (backup 31)", "")
                navigation(slide, srels, page)
            elif page == INDEX - 1:
                navigation(slide, srels, page)
            if page != INDEX:
                adapt_notes(notes, page)
            out_names = slide_parts(page)
            for rel in srels:
                kind = rel.get("Type")
                if kind == R+"/notesSlide":
                    rel.set("Target", "/"+out_names[2])
                elif kind == R+"/image":
                    target = rel.get("Target").lstrip("/")
                    if target not in parts:
                        parts[target] = source.read(target)
                    elif parts[target] != source.read(target):
                        raise ValueError(f"Conflicting embedded figure {target}")
            for rel in nrels:
                if rel.get("Type") == R+"/slide":
                    rel.set("Target", "/"+out_names[0])
            for name, doc in zip(out_names, (slide, srels, notes, nrels), strict=True):
                parts[name] = xml(doc)
            if new:
                rid = f"EvidencePage{page}"
                ET.SubElement(page_ids, f"{{{P}}}sldId", {"id": str(255+page), f"{{{R}}}id": rid})
                ET.SubElement(pres_rels, f"{{{PK}}}Relationship", Id=rid, Target="/"+out_names[0], Type=R+"/slide")
                for path, kind in ((out_names[0], "slide"), (out_names[2], "notesSlide")):
                    # Some reserve pages replace slides already present in the talk template.
                    if "/"+path not in declared:
                        ET.SubElement(manifest, f"{{{CT}}}Override", PartName="/"+path,
                                      ContentType=f"application/vnd.openxmlformats-officedocument.presentationml.{kind}+xml")
        properties = ET.fromstring(parts["docProps/app.xml"])
        for prop in ("Slides", "Notes"):
            properties.find(f"{{{AP}}}"+prop).text = str(slide_count)
        for name, doc in (("docProps/app.xml", properties), ("ppt/presentation.xml", pres),
                          ("ppt/_rels/presentation.xml.rels", pres_rels), ("[Content_Types].xml", manifest)):
            parts[name] = xml(doc)
        with ZipFile(output, "w") as dest:
            for name, data in parts.items():
                item = ZipInfo(name, (2026, 11, 18, 12, 0, 0))
                item.compress_type = ZIP_DEFLATED
                dest.writestr(item, data)
