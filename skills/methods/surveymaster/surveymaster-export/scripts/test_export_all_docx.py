import tempfile
import unittest
import zipfile
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))

import export_all


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def wt(name: str) -> str:
    return f"{{{W}}}{name}"


def paragraph(text: str, outline_level: str | None = None) -> ET.Element:
    p = ET.Element(wt("p"))
    if outline_level is not None:
        p_pr = ET.SubElement(p, wt("pPr"))
        ET.SubElement(p_pr, wt("outlineLvl"), {wt("val"): outline_level})
    r = ET.SubElement(p, wt("r"))
    t = ET.SubElement(r, wt("t"))
    t.text = text
    return p


def one_cell_table(text: str) -> ET.Element:
    tbl = ET.Element(wt("tbl"))
    tr = ET.SubElement(tbl, wt("tr"))
    tc = ET.SubElement(tr, wt("tc"))
    tc.append(paragraph(text))
    return tbl


def is_visible_superscript_text_run(run: ET.Element, text: str) -> bool:
    if any(node.tag in {wt("fldChar"), wt("instrText")} for node in run.iter()):
        return False
    if "".join(node.text or "" for node in run.iter(wt("t"))) != text:
        return False
    vertical_align = run.find(f"{wt('rPr')}/{wt('vertAlign')}")
    return vertical_align is not None and vertical_align.attrib.get(wt("val")) == "superscript"


def has_superscript_text_run(paragraph: ET.Element, text: str) -> bool:
    return any(is_visible_superscript_text_run(run, text) for run in paragraph.iter(wt("r")))


def run_is_superscript(run: ET.Element) -> bool:
    vertical_align = run.find(f"{wt('rPr')}/{wt('vertAlign')}")
    return vertical_align is not None and vertical_align.attrib.get(wt("val")) == "superscript"


def toc(caption_text: str) -> ET.Element:
    sdt = ET.Element(wt("sdt"))
    sdt_pr = ET.SubElement(sdt, wt("sdtPr"))
    gallery = ET.SubElement(sdt_pr, wt("docPartObj"))
    ET.SubElement(gallery, wt("docPartGallery"), {wt("val"): "Table of Contents"})
    content = ET.SubElement(sdt, wt("sdtContent"))
    instr_p = ET.SubElement(content, wt("p"))
    instr_r = ET.SubElement(instr_p, wt("r"))
    begin = ET.SubElement(instr_r, wt("fldChar"))
    begin.set(wt("fldCharType"), "begin")
    instr = ET.SubElement(instr_r, wt("instrText"))
    instr.text = r'TOC \o "1-3" \h \z \u'
    separate = ET.SubElement(instr_r, wt("fldChar"))
    separate.set(wt("fldCharType"), "separate")
    content.append(paragraph("1 Introduction"))
    nested = ET.SubElement(content, wt("hyperlink"))
    nested.append(paragraph(caption_text))
    end_p = ET.SubElement(content, wt("p"))
    end_r = ET.SubElement(end_p, wt("r"))
    end = ET.SubElement(end_r, wt("fldChar"))
    end.set(wt("fldCharType"), "end")
    return sdt


def styles() -> bytes:
    root = ET.Element(wt("styles"))
    style = ET.SubElement(root, wt("style"), {wt("styleId"): "Caption"})
    ET.SubElement(style, wt("name"), {wt("val"): "Caption"})
    p_pr = ET.SubElement(style, wt("pPr"))
    ET.SubElement(p_pr, wt("outlineLvl"), {wt("val"): "2"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def settings() -> bytes:
    root = ET.Element(wt("settings"))
    ET.SubElement(root, wt("zoom"), {wt("percent"): "170"})
    ET.SubElement(root, wt("characterSpacingControl"), {wt("val"): "compressPunctuation"})
    ET.SubElement(root, wt("footnotePr"))
    ET.SubElement(root, wt("endnotePr"))
    ET.SubElement(root, wt("compat"))
    ET.SubElement(root, wt("rsids"))
    ET.SubElement(root, wt("themeFontLang"), {wt("val"): "en-US", wt("eastAsia"): "zh-CN"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_minimal_docx(path: Path, document_xml: bytes) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", styles())
        archive.writestr("word/settings.xml", settings())


class MarkDocxFieldsDirtyTest(unittest.TestCase):
    def test_marks_toc_and_reference_fields_dirty(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        toc_node = toc("Appendix")
        body.append(toc_node)
        body.append(paragraph("Prior work [1]."))

        citation_run = list(body)[1].find(wt("r"))
        self.assertIsNotNone(citation_run)
        citation_run.clear()
        begin = ET.SubElement(citation_run, wt("fldChar"))
        begin.set(wt("fldCharType"), "begin")
        instr = ET.SubElement(citation_run, wt("instrText"))
        instr.text = " REF _Ref1 \\h "
        separate = ET.SubElement(citation_run, wt("fldChar"))
        separate.set(wt("fldCharType"), "separate")
        text = ET.SubElement(citation_run, wt("t"))
        text.text = "1"
        end = ET.SubElement(citation_run, wt("fldChar"))
        end.set(wt("fldCharType"), "end")

        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            write_minimal_docx(docx_path, document_xml)

            error = export_all.mark_docx_fields_dirty(docx_path)

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                updated = ET.fromstring(archive.read("word/document.xml"))

        dirty_fields = [
            field
            for field in updated.iter(wt("fldChar"))
            if field.attrib.get(wt("fldCharType")) == "begin"
        ]
        self.assertEqual(len(dirty_fields), 2)
        self.assertTrue(all(field.attrib.get(wt("dirty")) == "true" for field in dirty_fields))


class EnableDocxUpdateFieldsTest(unittest.TestCase):
    def test_inserts_update_fields_in_settings_schema_order(self) -> None:
        root = ET.Element(wt("document"))
        ET.SubElement(root, wt("body"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            write_minimal_docx(docx_path, document_xml)

            error = export_all.enable_docx_update_fields_on_open(docx_path)

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                updated_settings = ET.fromstring(archive.read("word/settings.xml"))

        child_names = [child.tag for child in list(updated_settings)]
        update_index = child_names.index(wt("updateFields"))
        self.assertLess(child_names.index(wt("characterSpacingControl")), update_index)
        self.assertLess(update_index, child_names.index(wt("footnotePr")))
        update_fields = updated_settings.find(wt("updateFields"))
        self.assertIsNotNone(update_fields)
        self.assertEqual(update_fields.attrib.get(wt("val")), "true")

    def test_repositions_existing_update_fields_in_settings_schema_order(self) -> None:
        root = ET.Element(wt("document"))
        ET.SubElement(root, wt("body"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        settings_root = ET.fromstring(settings())
        misplaced_update_fields = ET.Element(wt("updateFields"), {wt("val"): "false"})
        settings_root.insert(0, misplaced_update_fields)
        bad_settings = ET.tostring(settings_root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("word/document.xml", document_xml)
                archive.writestr("word/styles.xml", styles())
                archive.writestr("word/settings.xml", bad_settings)

            error = export_all.enable_docx_update_fields_on_open(docx_path)

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                updated_settings = ET.fromstring(archive.read("word/settings.xml"))

        child_names = [child.tag for child in list(updated_settings)]
        update_indices = [idx for idx, name in enumerate(child_names) if name == wt("updateFields")]
        self.assertEqual(len(update_indices), 1)
        update_index = update_indices[0]
        self.assertLess(child_names.index(wt("characterSpacingControl")), update_index)
        self.assertLess(update_index, child_names.index(wt("footnotePr")))
        update_fields = updated_settings.find(wt("updateFields"))
        self.assertIsNotNone(update_fields)
        self.assertEqual(update_fields.attrib.get(wt("val")), "true")


class RawHtmlMetadataLeakTest(unittest.TestCase):
    def test_docx_reports_raw_metadata_tags(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        body.append(paragraph("参考文献"))
        body.append(paragraph("[1] Cheng M. <scp>CD8</scp> <sup>+</sup> T Cells[J]."))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        issues = export_all.check_docx_document_structure(
            document_xml,
            source_tex="",
            bib_exists=True,
        )

        self.assertIn("DOCX_RAW_HTML_TAG_LEAK", issues)

    def test_docx_clean_metadata_does_not_report_raw_tags(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        body.append(paragraph("参考文献"))
        body.append(paragraph("[1] Cheng M. CD8+ T Cells[J]."))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        issues = export_all.check_docx_document_structure(
            document_xml,
            source_tex="",
            bib_exists=True,
        )

        self.assertNotIn("DOCX_RAW_HTML_TAG_LEAK", issues)


class PreventDocxCaptionsInTocTest(unittest.TestCase):
    def test_table_reference_sentence_is_not_treated_as_caption(self) -> None:
        self.assertTrue(export_all.is_docx_float_caption_paragraph(paragraph("表 1. 降解机制归纳")))
        self.assertTrue(export_all.is_docx_float_caption_paragraph(paragraph("Table 1. Degradation mechanisms")))
        self.assertFalse(export_all.is_docx_float_caption_paragraph(paragraph("表 1 归纳了六类主要降解机制的诱因。")))
        self.assertFalse(export_all.is_docx_float_caption_paragraph(paragraph("Table 1 summarizes six degradation mechanisms.")))

    def test_removes_caption_toc_entries_and_outline_levels(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        body.append(toc("图 1. System overview"))
        body.append(paragraph("图 1. System overview", outline_level="2"))
        body.append(paragraph("表 1. Dataset summary", outline_level="2"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            write_minimal_docx(docx_path, document_xml)

            error = export_all.prevent_docx_captions_in_toc(docx_path)
            style_error = export_all.prevent_docx_caption_styles_in_toc(docx_path)

            self.assertIsNone(error)
            self.assertIsNone(style_error)
            with zipfile.ZipFile(docx_path) as archive:
                updated = ET.fromstring(archive.read("word/document.xml"))
                updated_styles = ET.fromstring(archive.read("word/styles.xml"))

        body = updated.find(wt("body"))
        self.assertIsNotNone(body)
        toc_node = next(child for child in body if export_all.is_docx_toc(child))
        toc_text = export_all.element_text(toc_node)
        self.assertIn("1 Introduction", toc_text)
        self.assertNotIn("图 1. System overview", toc_text)
        instr_text = "".join(node.text or "" for node in toc_node.iter(wt("instrText")))
        self.assertNotIn(r"\u", instr_text)

        caption_paragraphs = [
            p for p in updated.iter(wt("p"))
            if export_all.is_docx_float_caption_paragraph(p)
        ]
        self.assertEqual(len(caption_paragraphs), 2)
        for caption in caption_paragraphs:
            self.assertIsNone(caption.find(f"{wt('pPr')}/{wt('outlineLvl')}"))

        caption_style = next(
            style for style in updated_styles.iter(wt("style"))
            if style.attrib.get(wt("styleId")) == "Caption"
        )
        self.assertIsNone(caption_style.find(f"{wt('pPr')}/{wt('outlineLvl')}"))


class AddDocxFloatCrossrefsTest(unittest.TestCase):
    def test_adds_bookmarks_and_ref_fields_for_float_refs(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        ref_para = paragraph("图 1 展示框架，")
        citation_run = ET.SubElement(ref_para, wt("r"))
        begin = ET.SubElement(citation_run, wt("fldChar"))
        begin.set(wt("fldCharType"), "begin")
        instr = ET.SubElement(citation_run, wt("instrText"))
        instr.text = " REF _Ref1 \\h "
        separate = ET.SubElement(citation_run, wt("fldChar"))
        separate.set(wt("fldCharType"), "separate")
        text = ET.SubElement(citation_run, wt("t"))
        text.text = "1"
        end = ET.SubElement(citation_run, wt("fldChar"))
        end.set(wt("fldCharType"), "end")
        tail_run = ET.SubElement(ref_para, wt("r"))
        tail_text = ET.SubElement(tail_run, wt("t"))
        tail_text.text = "，表 1 总结机制。"
        body.append(ref_para)
        body.append(paragraph("图 1. Framework"))
        body.append(paragraph("表 1. Mechanisms"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            write_minimal_docx(docx_path, document_xml)

            error = export_all.add_docx_float_crossrefs(docx_path, "zh")

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                xml = archive.read("word/document.xml").decode("utf-8")
                updated = ET.fromstring(xml.encode("utf-8"))

        self.assertIn("REF _Fig1 \\h", xml)
        self.assertIn("REF _Tab1 \\h", xml)
        bookmark_names = {
            node.attrib.get(wt("name"))
            for node in updated.iter(wt("bookmarkStart"))
        }
        self.assertIn("_Fig1", bookmark_names)
        self.assertIn("_Tab1", bookmark_names)

    def test_caption_bookmark_is_inserted_after_paragraph_properties(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        body.append(paragraph("图 1. Framework", outline_level="2"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            write_minimal_docx(docx_path, document_xml)

            error = export_all.add_docx_float_crossrefs(docx_path, "zh")

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                updated = ET.fromstring(archive.read("word/document.xml"))

        caption = next(p for p in updated.iter(wt("p")) if export_all.element_text(p).startswith("图 1"))
        self.assertEqual(list(caption)[0].tag, wt("pPr"))
        self.assertEqual(list(caption)[1].tag, wt("bookmarkStart"))


class NormalizeDocxXmlOrderTest(unittest.TestCase):
    def test_moves_paragraph_properties_first_and_sorts_table_borders(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        p = ET.SubElement(body, wt("p"))
        ET.SubElement(p, wt("bookmarkStart"), {wt("id"): "1", wt("name"): "_Fig1"})
        p_pr = ET.SubElement(p, wt("pPr"))
        ET.SubElement(p_pr, wt("outlineLvl"), {wt("val"): "2"})
        r = ET.SubElement(p, wt("r"))
        t = ET.SubElement(r, wt("t"))
        t.text = "图 1. Framework"

        tbl = ET.SubElement(body, wt("tbl"))
        tbl_pr = ET.SubElement(tbl, wt("tblPr"))
        tbl_borders = ET.SubElement(tbl_pr, wt("tblBorders"))
        ET.SubElement(tbl_borders, wt("bottom"))
        ET.SubElement(tbl_borders, wt("top"))
        ET.SubElement(tbl_pr, wt("tblStyle"))

        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            write_minimal_docx(docx_path, document_xml)

            error = export_all.normalize_docx_xml_order(docx_path)

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                updated = ET.fromstring(archive.read("word/document.xml"))

        updated_p = next(updated.iter(wt("p")))
        self.assertEqual(list(updated_p)[0].tag, wt("pPr"))

        updated_tbl_pr = next(updated.iter(wt("tblPr")))
        self.assertEqual([child.tag for child in list(updated_tbl_pr)], [wt("tblStyle"), wt("tblBorders")])
        updated_borders = next(updated.iter(wt("tblBorders")))
        self.assertEqual([child.tag for child in list(updated_borders)], [wt("top"), wt("bottom")])


class NormalizeDocxStylesXmlTest(unittest.TestCase):
    def test_sorts_style_children_and_removes_undeclared_ignorable_prefix(self) -> None:
        root = ET.Element(wt("document"))
        ET.SubElement(root, wt("body"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        bad_styles = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            'mc:Ignorable="w14">'
            '<w:style w:styleId="BadStyle">'
            '<w:name w:val="Bad Style"/>'
            '<w:qFormat/>'
            '<w:uiPriority w:val="1"/>'
            '<w:pPr/>'
            '</w:style>'
            '</w:styles>'
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("word/document.xml", document_xml)
                archive.writestr("word/styles.xml", bad_styles)
                archive.writestr("word/settings.xml", settings())

            error = export_all.normalize_docx_styles_xml(docx_path)

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                styles_xml = archive.read("word/styles.xml")
                updated_styles = ET.fromstring(styles_xml)

        self.assertNotIn(b'Ignorable="w14"', styles_xml)
        style = next(updated_styles.iter(wt("style")))
        child_names = [child.tag for child in list(style)]
        self.assertLess(child_names.index(wt("uiPriority")), child_names.index(wt("qFormat")))

    def test_normalizes_known_style_complex_script_sizes(self) -> None:
        root = ET.Element(wt("document"))
        ET.SubElement(root, wt("body"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        bad_styles = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:style w:styleId="56">'
            '<w:name w:val="Image Caption"/>'
            '<w:rPr><w:sz w:val="20"/><w:szCs w:val="32"/></w:rPr>'
            '</w:style>'
            '<w:style w:styleId="15">'
            '<w:name w:val="Heading 1 Char"/>'
            '<w:rPr><w:sz w:val="30"/><w:szCs w:val="44"/></w:rPr>'
            '</w:style>'
            '</w:styles>'
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("word/document.xml", document_xml)
                archive.writestr("word/styles.xml", bad_styles)
                archive.writestr("word/settings.xml", settings())

            error = export_all.normalize_docx_styles_xml(docx_path)

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                updated_styles = ET.fromstring(archive.read("word/styles.xml"))

        image_caption = next(
            style for style in updated_styles.iter(wt("style"))
            if style.attrib.get(wt("styleId")) == "56"
        )
        heading_char = next(
            style for style in updated_styles.iter(wt("style"))
            if style.attrib.get(wt("styleId")) == "15"
        )
        for style, expected in ((image_caption, "20"), (heading_char, "28")):
            self.assertEqual(style.find(f"{wt('rPr')}/{wt('sz')}").attrib[wt("val")], expected)
            self.assertEqual(style.find(f"{wt('rPr')}/{wt('szCs')}").attrib[wt("val")], expected)


class NormalizeDocxSettingsXmlTest(unittest.TestCase):
    def test_sorts_update_fields_after_early_settings(self) -> None:
        root = ET.Element(wt("document"))
        ET.SubElement(root, wt("body"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        bad_settings = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:proofState/>'
            '<w:stylePaneFormatFilter/>'
            '<w:updateFields w:val="true"/>'
            '<w:footnotePr/>'
            '<w:savePreviewPicture/>'
            '<w:characterSpacingControl/>'
            '</w:settings>'
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("word/document.xml", document_xml)
                archive.writestr("word/styles.xml", styles())
                archive.writestr("word/settings.xml", bad_settings)

            error = export_all.normalize_docx_settings_xml(docx_path)

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                updated_settings = ET.fromstring(archive.read("word/settings.xml"))

        child_names = [child.tag for child in list(updated_settings)]
        self.assertLess(child_names.index(wt("proofState")), child_names.index(wt("updateFields")))
        self.assertLess(child_names.index(wt("stylePaneFormatFilter")), child_names.index(wt("updateFields")))
        self.assertLess(child_names.index(wt("characterSpacingControl")), child_names.index(wt("updateFields")))
        self.assertLess(child_names.index(wt("savePreviewPicture")), child_names.index(wt("updateFields")))
        self.assertLess(child_names.index(wt("updateFields")), child_names.index(wt("footnotePr")))


class DocxTableBorderStyleTest(unittest.TestCase):
    def _table_docx(self, path: Path) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        tbl = ET.SubElement(body, wt("tbl"))
        for row_index in range(2):
            tr = ET.SubElement(tbl, wt("tr"))
            for col_index in range(2):
                tc = ET.SubElement(tr, wt("tc"))
                tc.append(paragraph(f"{row_index},{col_index}"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        write_minimal_docx(path, document_xml)

    def _table_borders(self, docx_path: Path) -> ET.Element:
        with zipfile.ZipFile(docx_path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        return next(root.iter(wt("tblBorders")))

    def test_generic_docx_tables_keep_three_line_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            self._table_docx(docx_path)

            error = export_all.apply_docx_table_borders(docx_path, economics_style=False)

            self.assertIsNone(error)
            borders = self._table_borders(docx_path)
            self.assertEqual(borders.find(wt("insideH")).attrib[wt("val")], "nil")
            self.assertEqual(borders.find(wt("insideV")).attrib[wt("val")], "nil")

    def test_economics_docx_tables_keep_internal_rules_and_verticals(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            self._table_docx(docx_path)

            error = export_all.apply_docx_table_borders(docx_path, economics_style=True)

            self.assertIsNone(error)
            borders = self._table_borders(docx_path)
            self.assertEqual(borders.find(wt("top")).attrib[wt("sz")], "12")
            self.assertEqual(borders.find(wt("bottom")).attrib[wt("sz")], "12")
            self.assertEqual(borders.find(wt("insideH")).attrib[wt("val")], "single")
            self.assertEqual(borders.find(wt("insideV")).attrib[wt("val")], "single")
            self.assertEqual(borders.find(wt("insideH")).attrib[wt("sz")], "4")
            self.assertEqual(borders.find(wt("insideV")).attrib[wt("sz")], "4")


class EconomicsSurveyDetectionTest(unittest.TestCase):
    def test_computer_science_constraints_do_not_trigger_economics_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            survey_dir = Path(tmpdir)
            (survey_dir / "writing_constraints.json").write_text(
                json.dumps(
                    {
                        "subject": "computer science",
                        "topic": "multimodal knowledge graphs and retrieval augmented generation",
                        "venue_style_notes": "Computer science survey style with architecture diagrams.",
                    }
                ),
                encoding="utf-8",
            )

            self.assertFalse(export_all.is_economics_empirical_survey(survey_dir))

    def test_broad_domain_keywords_do_not_trigger_economics_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            survey_dir = Path(tmpdir)
            (survey_dir / "writing_constraints.json").write_text(
                json.dumps(
                    {
                        "subject": "computer science for finance and management",
                        "topic": "policy reasoning over supply-chain knowledge graphs",
                        "venue_style_notes": "Computer science survey style.",
                    }
                ),
                encoding="utf-8",
            )

            self.assertFalse(export_all.is_economics_empirical_survey(survey_dir))

    def test_economics_template_constraints_trigger_economics_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            survey_dir = Path(tmpdir)
            (survey_dir / "writing_constraints.json").write_text(
                json.dumps(
                    {
                        "constraint_source": {
                            "name": "bundled economics empirical-style review template"
                        },
                        "venue_style_notes": "Economics empirical-style review.",
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(export_all.is_economics_empirical_survey(survey_dir))

    def test_economics_subject_triggers_economics_style_without_template_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            survey_dir = Path(tmpdir)
            (survey_dir / "writing_constraints.json").write_text(
                json.dumps(
                    {
                        "subject": "经济学/金融学",
                        "topic": "供应链金融与中小企业融资",
                        "venue_style_notes": "无特定期刊投稿要求，采用通用学术综述格式",
                        "constraint_source": {"name": "default", "url": None},
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(export_all.is_economics_empirical_survey(survey_dir))


class RenderFloatRefsForPlainExportTest(unittest.TestCase):
    def test_collapses_duplicate_zh_float_prefixes(self) -> None:
        latex = (
            "表 \\autoref{tab:strategy} 对比了不同策略。\n"
            "图 \\autoref{fig:workflow} 展示了流程。\n"
            "\\begin{table}\\caption{策略对比\\label{tab:strategy}}\\begin{tabular}{ll}A&B\\end{tabular}\\end{table}\n"
            "\\begin{figure}\\caption{流程图\\label{fig:workflow}}\\end{figure}\n"
        )

        rendered = export_all.render_float_refs_for_plain_export(latex, "zh")

        self.assertIn("表 1 对比了不同策略。", rendered)
        self.assertIn("图 1 展示了流程。", rendered)
        self.assertNotIn("表 表", rendered)
        self.assertNotIn("图 图", rendered)

    def test_collapses_duplicate_en_float_prefixes(self) -> None:
        latex = (
            "Table \\autoref{tab:strategy} compares strategies.\n"
            "Figure \\autoref{fig:workflow} shows the workflow.\n"
            "\\begin{table}\\caption{Strategy comparison\\label{tab:strategy}}\\begin{tabular}{ll}A&B\\end{tabular}\\end{table}\n"
            "\\begin{figure}\\caption{Workflow\\label{fig:workflow}}\\end{figure}\n"
        )

        rendered = export_all.render_float_refs_for_plain_export(latex, "en")

        self.assertIn("Table 1 compares strategies.", rendered)
        self.assertIn("Figure 1 shows the workflow.", rendered)
        self.assertNotIn("Table Table", rendered)
        self.assertNotIn("Figure Figure", rendered)


class GbtBibliographyCleanupTest(unittest.TestCase):
    def test_docx_bibliography_drops_ol_from_journal_and_conference_labels(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        body.append(paragraph("Body [1]."))
        body.append(paragraph("参考文献"))
        body.append(paragraph("[1] Zhang X. Journal paper[J/OL]. Journal, 2024."))
        body.append(paragraph("[2] Li X. Conference paper[C/OL]. Proceedings, 2024."))
        body.append(paragraph("[3] Web resource[EB/OL]. 2024."))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            docx_path = tmp / "sample.docx"
            bib_path = tmp / "refs.bib"
            csl_path = tmp / "china-national-standard-gb-t-7714-2015-numeric.csl"
            write_minimal_docx(docx_path, document_xml)
            bib_path.write_text("@article{zhang2024, author={Zhang, X}, title={T}, year={2024}}\n", encoding="utf-8")
            csl_path.write_text("<style/>", encoding="utf-8")

            error = export_all.fix_gbt_bilingual_in_docx(docx_path, bib_path, csl_path, "zh")

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                xml = archive.read("word/document.xml").decode("utf-8")

        self.assertIn("Journal paper[J].", xml)
        self.assertIn("Conference paper[C].", xml)
        self.assertIn("Web resource[EB/OL].", xml)


class CheckDocxOpenXmlConformanceTest(unittest.TestCase):
    def test_reports_residual_openxml_conformance_errors(self) -> None:
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:p><w:r><w:t>word ' + ("content " * 60) + '</w:t></w:r></w:p>'
            '<w:p><w:r><w:rPr><w:bCs/><w:b/></w:rPr><w:t>Bold</w:t></w:r></w:p>'
            '</w:body></w:document>'
        ).encode("utf-8")
        numbering_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            'mc:Ignorable="w14 wp14">'
            '<w:abstractNum w:abstractNumId="990"><w:nsid w:val="0000A990"/></w:abstractNum></w:numbering>'
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("word/document.xml", document_xml)
                archive.writestr("word/styles.xml", styles())
                archive.writestr("word/settings.xml", settings())
                archive.writestr("word/numbering.xml", numbering_xml)

            issues = export_all.check_docx(docx_path)

        self.assertIn("DOCX_OPENXML_RPR_B_ORDER:word/document.xml", issues)
        self.assertIn("DOCX_OPENXML_UNDEFINED_IGNORABLE:word/numbering.xml:w14,wp14", issues)

    def test_reports_docx_structure_regressions_from_manual_pandoc_fallback(self) -> None:
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:p><w:r><w:t>摘要：' + ("内容 " * 20) + '</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>关键词：供应链金融；中小企业融资</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>如[tab:lit_comparison]所示，|L|L|L|L| 文献 &amp; 视角 &amp; 发现 &amp; 含义。</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>已有研究[1]指出相关机制。</w:t></w:r></w:p>'
            '</w:body></w:document>'
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            docx_path = tmp / "sample.docx"
            write_minimal_docx(docx_path, document_xml)
            (tmp / "mainbody.tex").write_text(
                "\\begin{abstract}内容\\end{abstract}\n"
                "\\keywords{供应链金融；中小企业融资}\n"
                "\\section{比较}\n"
                "如\\autoref{tab:lit_comparison}所示。\\cite{a2024}\n"
                "\\begin{table}\\caption{比较\\label{tab:lit_comparison}}"
                "\\begin{tabular}{llll}A&B&C&D\\\\\\end{tabular}\\end{table}\n",
                encoding="utf-8",
            )
            (tmp / "references.bib").write_text("@article{a2024,title={T},author={A},year={2024}}\n", encoding="utf-8")

            issues = export_all.check_docx(docx_path)

        self.assertIn("DOCX_RAW_LATEX_TABLE_LEAK", issues)
        self.assertIn("DOCX_RAW_LABEL_LEAK", issues)
        self.assertIn("DOCX_NO_WORD_TABLES_WHEN_SOURCE_HAS_TABLE", issues)
        self.assertIn("DOCX_REFERENCES_HEADING_MISSING", issues)
        self.assertIn("DOCX_REF_FIELDS_MISSING", issues)

    def test_docx_input_rejects_tabularx_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            survey_dir = Path(tmpdir)
            (survey_dir / "mainbody.tex").write_text(
                "\\begin{abstract}内容\\end{abstract}\n"
                "\\keywords{供应链金融}\n"
                "\\maketitle\n\\tableofcontents\n"
                "\\section{比较}\n"
                "\\begin{table}\\caption{比较\\label{tab:a}}"
                "\\begin{tabularx}{\\textwidth}{|L|L|}A&B\\\\\\end{tabularx}\\end{table}\n",
                encoding="utf-8",
            )

            input_tex, warnings = export_all.assemble_docx_input(survey_dir, "sample", "zh")

        self.assertIsNone(input_tex)
        self.assertIn("DOCX_INPUT_UNSUPPORTED_TABULARX: use tabular in mainbody.tex; tabularx is reserved for TeX/PDF export", warnings)


class DocxNumericReferenceCrossrefTest(unittest.TestCase):
    def test_adds_reference_bookmarks_and_ref_fields(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        body.append(export_all.make_docx_bookmark_start(1, "ExistingHeading"))
        body.append(export_all.make_docx_bookmark_end(1))
        body.append(paragraph("Prior work [1, 2] remains separate from unknown [99]."))
        body.append(paragraph("References"))
        body.append(paragraph("[1] First source."))
        body.append(paragraph("[2] Second source."))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            write_minimal_docx(docx_path, document_xml)

            error = export_all.add_docx_numeric_reference_crossrefs(docx_path, "en")

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                xml = archive.read("word/document.xml").decode("utf-8")
                updated = ET.fromstring(xml.encode("utf-8"))

        self.assertIn("REF _Ref1 \\h", xml)
        self.assertIn("REF _Ref2 \\h", xml)
        self.assertNotIn("REF _Ref99 \\h", xml)

        bookmark_names = [
            node.attrib.get(wt("name"))
            for node in updated.iter(wt("bookmarkStart"))
        ]
        self.assertEqual(bookmark_names, ["ExistingHeading", "_Ref1", "_Ref2"])
        bookmark_ids = [
            node.attrib.get(wt("id"))
            for node in updated.iter(wt("bookmarkStart"))
        ]
        self.assertEqual(len(bookmark_ids), len(set(bookmark_ids)))

        first_para = next(
            p for p in updated.iter(wt("p"))
            if "Prior work" in export_all.element_text(p)
        )
        first_para_text = "".join(node.text or "" for node in first_para.iter(wt("t")))
        self.assertIn("[1, 2]", first_para_text)
        self.assertIn("[99]", first_para_text)

    def test_numeric_citations_can_be_superscript_ref_fields(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        body.append(paragraph("呈上升趋势[1]。"))
        body.append(paragraph("参考文献"))
        body.append(paragraph("[1] 第一篇文献。"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            write_minimal_docx(docx_path, document_xml)

            error = export_all.add_docx_numeric_reference_crossrefs(
                docx_path,
                "en",
                superscript_citations=True,
            )

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                xml = archive.read("word/document.xml").decode("utf-8")
                updated = ET.fromstring(xml.encode("utf-8"))

        self.assertIn("REF _Ref1 \\h", xml)
        citation_para = next(
            p for p in updated.iter(wt("p"))
            if "呈上升趋势" in export_all.element_text(p)
        )
        self.assertTrue(has_superscript_text_run(citation_para, "["))
        self.assertTrue(has_superscript_text_run(citation_para, "1"))
        self.assertTrue(has_superscript_text_run(citation_para, "]"))
        field_runs = [
            run
            for run in citation_para.iter(wt("r"))
            if any(node.tag in {wt("fldChar"), wt("instrText")} for node in run.iter())
        ]
        self.assertTrue(field_runs)
        self.assertTrue(all(run_is_superscript(run) for run in field_runs))

    def test_superscript_template_from_pandoc_citation_does_not_leak_to_body_text(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        citation_para = ET.SubElement(body, wt("p"))
        text_run = ET.SubElement(citation_para, wt("r"))
        ET.SubElement(text_run, wt("t")).text = "正文"
        for token in ("[", "1", "]"):
            run = ET.SubElement(citation_para, wt("r"))
            export_all.apply_run_superscript(run)
            ET.SubElement(run, wt("t")).text = token
        tail_run = ET.SubElement(citation_para, wt("r"))
        ET.SubElement(tail_run, wt("t")).text = "后文"
        body.append(paragraph("参考文献"))
        body.append(paragraph("[1] 第一篇文献。"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            write_minimal_docx(docx_path, document_xml)

            error = export_all.add_docx_numeric_reference_crossrefs(
                docx_path,
                "zh",
                superscript_citations=True,
            )

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                updated = ET.fromstring(archive.read("word/document.xml"))

        updated_para = next(
            p for p in updated.iter(wt("p"))
            if "正文" in export_all.element_text(p)
        )
        self.assertFalse(has_superscript_text_run(updated_para, "正文"))
        self.assertFalse(has_superscript_text_run(updated_para, "后文"))
        self.assertTrue(has_superscript_text_run(updated_para, "["))
        self.assertTrue(has_superscript_text_run(updated_para, "1"))
        self.assertTrue(has_superscript_text_run(updated_para, "]"))
        field_runs = [
            run
            for run in updated_para.iter(wt("r"))
            if any(node.tag in {wt("fldChar"), wt("instrText")} for node in run.iter())
        ]
        self.assertTrue(field_runs)
        self.assertTrue(all(run_is_superscript(run) for run in field_runs))

    def test_adds_superscript_ref_fields_inside_table_cells(self) -> None:
        root = ET.Element(wt("document"))
        body = ET.SubElement(root, wt("body"))
        body.append(paragraph("正文引用[1]。"))
        body.append(one_cell_table("表格证据来自[1, 2]。"))
        body.append(paragraph("参考文献"))
        body.append(paragraph("[1] 第一篇文献。"))
        body.append(paragraph("[2] 第二篇文献。"))
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            write_minimal_docx(docx_path, document_xml)

            error = export_all.add_docx_numeric_reference_crossrefs(
                docx_path,
                "zh",
                superscript_citations=True,
            )

            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                xml = archive.read("word/document.xml").decode("utf-8")
                updated = ET.fromstring(xml.encode("utf-8"))

        self.assertGreaterEqual(xml.count("REF _Ref1 \\h"), 2)
        self.assertIn("REF _Ref2 \\h", xml)
        table = next(updated.iter(wt("tbl")))
        table_xml = ET.tostring(table, encoding="unicode")
        self.assertIn("REF _Ref1 \\h", table_xml)
        self.assertIn("REF _Ref2 \\h", table_xml)
        self.assertTrue(any(is_visible_superscript_text_run(run, "1") for run in table.iter(wt("r"))))
        self.assertTrue(any(is_visible_superscript_text_run(run, "2") for run in table.iter(wt("r"))))


class NormalizeDocxPackageIntegrityTest(unittest.TestCase):
    def test_removes_directory_parts_and_normalizes_ooxml_metadata(self) -> None:
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:tbl>'
            '<w:tr><w:trPr><w:tblHeader w:val="true"/></w:trPr></w:tr>'
            '<w:tr><w:trPr><w:tblHeader w:val="1"/></w:trPr></w:tr>'
            '<w:p><w:r><w:rPr><w:bCs/><w:b/></w:rPr><w:t>Bold</w:t></w:r></w:p>'
            '</w:tbl></w:body>'
            '</w:document>'
        ).encode("utf-8")
        styles_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:style w:styleId="Broken"><w:rPr><w:bCs/><w:b/></w:rPr></w:style></w:styles>'
        ).encode("utf-8")
        numbering_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            'mc:Ignorable="w14 wp14">'
            '<w:abstractNum w:abstractNumId="990"><w:nsid w:val="A990"/></w:abstractNum></w:numbering>'
        ).encode("utf-8")
        content_types = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Override PartName="/word/media/" ContentType="application/octet-stream"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("[Content_Types].xml", content_types)
                archive.writestr("word/document.xml", document_xml)
                archive.writestr("word/styles.xml", styles_xml)
                archive.writestr("word/numbering.xml", numbering_xml)
                archive.writestr("word/media/", b"")
            error = export_all.normalize_docx_package_integrity(docx_path)
            self.assertIsNone(error)
            with zipfile.ZipFile(docx_path) as archive:
                self.assertNotIn("word/media/", archive.namelist())
                updated_content_types_xml = archive.read("[Content_Types].xml")
                updated_content_types = ET.fromstring(updated_content_types_xml)
                updated_document = ET.fromstring(archive.read("word/document.xml"))
                updated_styles = ET.fromstring(archive.read("word/styles.xml"))
                updated_numbering = ET.fromstring(archive.read("word/numbering.xml"))
        self.assertFalse(any(part.attrib.get("PartName", "").endswith("/") for part in updated_content_types))
        self.assertIn(b"<Types xmlns=", updated_content_types_xml)
        self.assertEqual([child.tag for child in list(next(updated_styles.iter(wt("rPr"))))], [wt("b"), wt("bCs")])
        self.assertTrue(all(wt("val") not in tbl_header.attrib for tbl_header in updated_document.iter(wt("tblHeader"))))
        document_run_properties = [
            run_properties for run_properties in updated_document.iter(wt("rPr"))
            if {child.tag for child in list(run_properties)} == {wt("b"), wt("bCs")}
        ]
        self.assertTrue(document_run_properties)
        self.assertEqual([child.tag for child in list(document_run_properties[0])], [wt("b"), wt("bCs")])
        self.assertEqual(next(updated_numbering.iter(wt("nsid"))).attrib.get(wt("val")), "0000A990")
        self.assertNotIn(f"{{{export_all._MC_NS}}}Ignorable", updated_numbering.attrib)


if __name__ == "__main__":
    unittest.main()
