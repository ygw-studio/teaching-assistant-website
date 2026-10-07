"""Extract teacher materials and package the original resources by chapter."""

import argparse
import json
import re
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "数据结构课程资源"
TARGET = ROOT / "backend" / "assets" / "data-structures"
CHINESE_NUMBERS = dict(enumerate("一二三四五六七八", 1))
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


def slide_text(path):
    with ZipFile(path) as archive:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        relationships = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
        }
        slides = []
        for index, slide in enumerate(presentation.findall("p:sldIdLst/p:sldId", NS), 1):
            target = relationships[slide.attrib[f"{{{NS['r']}}}id"]]
            part = target.lstrip("/") if target.startswith("/") else f"ppt/{target}"
            tree = ET.fromstring(archive.read(part))
            paragraphs = [
                "".join(node.text or "" for node in paragraph.findall(".//a:t", NS)).strip()
                for paragraph in tree.findall(".//a:p", NS)
            ]
            paragraphs = [text for text in paragraphs if text]
            slides.append({"page": index, "paragraphs": paragraphs})
    return slides


def document_text(path):
    with ZipFile(path) as archive:
        tree = ET.fromstring(archive.read("word/document.xml"))
        return "\n".join(
            text for paragraph in tree.findall(".//w:p", NS)
            if (text := "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip())
        )


def code_text(path):
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            pass
    raise ValueError(f"Unknown code encoding: {path}")


def copy_handout(source, destination):
    if destination.exists() and source.read_bytes() != destination.read_bytes():
        destination.with_suffix(".pdf").unlink(missing_ok=True)
    shutil.copy2(source, destination)


def build(inspect=False):
    TARGET.mkdir(parents=True, exist_ok=True)
    materials = []
    for number in range(1, 9):
        pptx = next((SOURCE / "1、数据结构Python版PPT").glob(f"第{number}章*.pptx"))
        title = re.sub(r"^第\d+章\s*", "", pptx.stem)
        chapter_folder = f"第{CHINESE_NUMBERS[number]}章"
        code_paths = sorted(SOURCE.glob(f"3、正文代码清单/**/{chapter_folder}/*.py"))
        documents = sorted((SOURCE / "4、算法设计题").glob(f"*{chapter_folder}.docx"))
        questions = sorted(SOURCE.glob(f"2、题库/{chapter_folder}*/*"))
        material = {
            "number": number, "title": title, "handout_name": pptx.name,
            "slides": slide_text(pptx),
            "code": [{"filename": path.name, "code": code_text(path)} for path in code_paths],
            "assignments": [{"filename": path.name, "text": document_text(path)} for path in documents],
            "resources": [str(path.relative_to(SOURCE)).replace("\\", "/") for path in [pptx, *code_paths, *documents, *questions]],
        }
        materials.append(material)
        if inspect:
            print(f"\nCHAPTER {number}: {title} ({len(material['slides'])} slides)")
            for slide in material["slides"]:
                print(f"{slide['page']:3}: {' / '.join(slide['paragraphs'][:2])[:180]}")
            for assignment in material["assignments"]:
                print(f"ASSIGNMENT {assignment['filename']}:\n{assignment['text']}")
            for code in material["code"]:
                print(f"CODE {code['filename']}: {' / '.join(code['code'].splitlines()[:5])}")
        copy_handout(pptx, TARGET / f"chapter-{number}.pptx")
        with ZipFile(TARGET / f"chapter-{number}-resources.zip", "w", ZIP_DEFLATED) as archive:
            for path in [pptx, *code_paths, *documents, *questions]:
                archive.write(path, str(path.relative_to(SOURCE)))
    (TARGET / "source-material.json").write_text(
        json.dumps(materials, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Packaged {len(materials)} chapters, {sum(len(m['code']) for m in materials)} code files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true")
    build(parser.parse_args().inspect)
