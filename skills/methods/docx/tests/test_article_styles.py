import importlib.util
import unittest
from pathlib import Path


BUILDER = Path(__file__).resolve().parents[1] / "scripts" / "office" / "build_article_docx.py"
spec = importlib.util.spec_from_file_location("build_article_docx", BUILDER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ArticleStyleTests(unittest.TestCase):
    def test_all_three_heading_levels_are_black_and_left_aligned(self):
        document = module.build_article(
            {
                "title": "知识图谱",
                "blocks": [
                    {"type": "heading", "level": 3, "text": "1.1.1 三级标题"},
                ],
            }
        )
        for style_name in ("Heading 1", "Heading 2", "Heading 3"):
            style = document.styles[style_name]
            self.assertEqual("000000", str(style.font.color.rgb))
            self.assertTrue(style.font.bold)
            self.assertEqual(0, style.paragraph_format.alignment)
        title_run = document.paragraphs[0].runs[0]
        self.assertEqual("黑体", title_run._element.rPr.rFonts.get(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia"
        ))


if __name__ == "__main__":
    unittest.main()
