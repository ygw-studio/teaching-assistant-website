import json
import os
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from app import database
from app.data_structure_course import DATA_STRUCTURE_COURSE
from app.data_structure_examples import EXAMPLES
from app.data_structure_syllabus import ASSET_ROOT, SECTIONS


class DataStructureImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"DATABASE_PATH": str(Path(self.temp.name) / "course.db")})
        self.env.start()
        database.init_database()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_removed_intro_course_is_not_reseeded_and_history_is_preserved(self):
        with database.get_connection() as connection:
            connection.execute(
                "INSERT INTO courses VALUES (?, ?, ?, ?)",
                ("python-basic", "Retired intro course", "", database.utc_now()),
            )
            connection.execute(
                "INSERT INTO lesson_progress VALUES (?, ?, ?, ?)",
                ("20250001", "python-basic", "p1", database.utc_now()),
            )
            connection.execute("DELETE FROM courses WHERE id = ?", ("python-basic",))
        database.save_code_draft("20250001", "lesson", "p1", "print('saved')", "")

        database.init_database()
        database.init_database()

        self.assertIsNone(database.get_course_tree("python-basic"))
        self.assertEqual([course["id"] for course in database.list_courses()], [DATA_STRUCTURE_COURSE["id"]])
        self.assertEqual(len(database.get_course_tree(DATA_STRUCTURE_COURSE["id"])["chapters"]), 8)
        with database.get_connection() as connection:
            progress = connection.execute(
                "SELECT lesson_id FROM lesson_progress WHERE account_id = ? AND course_id = ?",
                ("20250001", "python-basic"),
            ).fetchall()
        self.assertEqual([row["lesson_id"] for row in progress], ["p1"])
        self.assertEqual(database.get_code_draft("20250001", "lesson", "p1")["code"], "print('saved')")

    def test_upgrade_preserves_teacher_content_progress_and_drafts(self):
        course_id = DATA_STRUCTURE_COURSE["id"]
        with database.get_connection() as connection:
            connection.execute("DELETE FROM chapters WHERE course_id = ? AND id NOT IN ('ds-chapter-1', 'ds-chapter-2')", (course_id,))
            connection.execute("DELETE FROM course_import_versions WHERE course_id = ?", (course_id,))
            for table in ("chapter_handouts", "chapter_handout_previews", "chapter_resources"):
                connection.execute(f"DELETE FROM {table} WHERE course_id = ? AND chapter_id NOT IN ('ds-chapter-1', 'ds-chapter-2')", (course_id,))
            connection.execute("UPDATE courses SET title = '教师修订课程', description = '自定义课程介绍' WHERE id = ?", (course_id,))
            connection.execute("UPDATE lessons SET title = '教师修订知识点', concept = '教师的正文' WHERE id = 'ds-1-1'")
            connection.execute("UPDATE chapters SET title = '教师修订第二章' WHERE id = 'ds-chapter-2'")
            connection.execute("INSERT INTO lesson_progress VALUES (?, ?, ?, ?)", ("20250001", course_id, "ds-1-1", "2026-10-01T00:00:00+00:00"))
        database.save_code_draft("20250001", "lesson", "ds-1-1", "print('保留草稿')", "")
        database.save_chapter_handout(course_id, "ds-chapter-1", "教师修订.pdf", b"%PDF-1.4\n%%EOF")

        database.init_database()
        course = database.get_course_tree(course_id)
        self.assertEqual(len(course["chapters"]), 8)
        self.assertEqual((course["title"], course["description"]), ("教师修订课程", "自定义课程介绍"))
        self.assertEqual(course["chapters"][0]["lessons"][0]["concept"], "教师的正文")
        self.assertEqual(course["chapters"][1]["title"], "教师修订第二章")
        self.assertEqual(course["chapters"][0]["handout_name"], "教师修订.pdf")
        self.assertEqual(database.get_course_progress("20250001", course_id)[0]["lesson_id"], "ds-1-1")
        self.assertEqual(database.get_code_draft("20250001", "lesson", "ds-1-1")["code"], "print('保留草稿')")
        database.init_database()
        self.assertEqual(len(database.get_course_tree(course_id)["chapters"]), 8)

        course["chapters"] = course["chapters"][:-1]
        database.save_course_tree(course)
        database.init_database()
        self.assertEqual(len(database.get_course_tree(course_id)["chapters"]), 7)
        self.assertIsNone(database.get_chapter_resources(course_id, "ds-chapter-8"))

    def test_every_source_resource_and_slide_section_is_covered(self):
        materials = json.loads((ASSET_ROOT / "source-material.json").read_text(encoding="utf-8"))
        self.assertEqual(len(materials), 8)
        self.assertEqual(sum(len(chapter["slides"]) for chapter in materials), 416)
        self.assertEqual(sum(len(chapter["code"]) for chapter in materials), 36)
        for chapter in materials:
            number = chapter["number"]
            with ZipFile(ASSET_ROOT / f"chapter-{number}-resources.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), set(chapter["resources"]))
            self.assertTrue((ASSET_ROOT / f"chapter-{number}.pdf").read_bytes().startswith(b"%PDF-"))
            if number > 1:
                covered = {page for section in SECTIONS[number] for page in range(section[0], section[1] + 1)}
                self.assertTrue(set(range(4, len(chapter["slides"]))).issubset(covered))
        for chapter in DATA_STRUCTURE_COURSE["chapters"]:
            for lesson in chapter["lessons"]:
                self.assertLessEqual(len(lesson["concept"]), 8000)
                self.assertIn(lesson["quiz_answer"], lesson["quiz_options"])

    def test_upgrade_backfills_missing_handouts_without_restoring_later_deletions(self):
        course_id = DATA_STRUCTURE_COURSE["id"]
        with database.get_connection() as connection:
            connection.execute("DELETE FROM course_import_versions WHERE course_id = ?", (course_id,))
            for table in ("chapter_handouts", "chapter_handout_previews"):
                connection.execute(f"DELETE FROM {table} WHERE course_id = ? AND chapter_id = 'ds-chapter-2'", (course_id,))
        database.init_database()
        handout = database.get_chapter_handout(course_id, "ds-chapter-2")
        preview = database.get_chapter_handout_preview(course_id, "ds-chapter-2")
        self.assertEqual(handout["content"], (ASSET_ROOT / "chapter-2.pptx").read_bytes())
        self.assertEqual(preview["content"], (ASSET_ROOT / "chapter-2.pdf").read_bytes())
        database.delete_chapter_handout(course_id, "ds-chapter-2")
        database.init_database()
        self.assertIsNone(database.get_chapter_handout(course_id, "ds-chapter-2"))

    def test_changed_source_handout_invalidates_only_its_generated_preview(self):
        path = Path(__file__).resolve().parents[2] / "tools" / "build_data_structure_assets.py"
        spec = importlib.util.spec_from_file_location("course_asset_builder", path)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        folder = Path(self.temp.name)
        source, destination, preview = (folder / name for name in ("source.pptx", "chapter.pptx", "chapter.pdf"))
        source.write_bytes(b"original")
        destination.write_bytes(b"original")
        preview.write_bytes(b"preview")
        builder.copy_handout(source, destination)
        self.assertEqual(preview.read_bytes(), b"preview")
        source.write_bytes(b"revised")
        builder.copy_handout(source, destination)
        self.assertFalse(preview.exists())
        self.assertEqual(destination.read_bytes(), b"revised")

    def test_standalone_examples_produce_expected_results(self):
        for name, (code, expected) in EXAMPLES.items():
            with self.subTest(example=name):
                result = subprocess.run(
                    [sys.executable, "-I", "-X", "utf8", "-c", code],
                    capture_output=True, text=True, encoding="utf-8", timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)


if __name__ == "__main__":
    unittest.main()
