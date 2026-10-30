import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


CSL_NS = {"csl": "http://purl.org/net/xbiblio/csl"}
CSL_DIR = Path(__file__).resolve().parents[1] / "csl"
GBT_STYLES = [
    "china-national-standard-gb-t-7714-2015-numeric.csl",
    "china-national-standard-gb-t-7714-2015-author-date.csl",
    "china-national-standard-gb-t-7714-2015-note.csl",
]


class GbtCslRulesTest(unittest.TestCase):
    def test_english_initials_use_periods(self) -> None:
        for filename in GBT_STYLES:
            with self.subTest(filename=filename):
                root = ET.parse(CSL_DIR / filename).getroot()
                self.assertEqual(root.get("initialize-with"), ". ")

    def test_ol_medium_is_auto_added_for_online_eb_resources(self) -> None:
        for filename in GBT_STYLES:
            with self.subTest(filename=filename):
                root = ET.parse(CSL_DIR / filename).getroot()
                medium = root.find(".//csl:macro[@name='medium-id']/csl:choose", CSL_NS)
                self.assertIsNotNone(medium)
                ol_branches = [
                    node for node in medium.findall("csl:else-if", CSL_NS)
                    if node.find("csl:text[@value='OL']", CSL_NS) is not None
                ]
                self.assertEqual(len(ol_branches), 1)
                self.assertEqual(ol_branches[0].get("type"), "post post-weblog webpage")
                self.assertEqual(ol_branches[0].get("variable"), "URL DOI")
                self.assertEqual(ol_branches[0].get("match"), "any")
                medium_branches = [
                    node for node in medium.findall("csl:if", CSL_NS)
                    if node.find("csl:text[@variable='medium']", CSL_NS) is not None
                ]
                self.assertEqual(len(medium_branches), 1)
                self.assertEqual(medium_branches[0].get("type"), "post post-weblog webpage")

    def test_ol_medium_is_not_added_for_journals_or_conferences(self) -> None:
        forbidden_types = {"article-journal", "article", "paper-conference"}
        for filename in GBT_STYLES:
            with self.subTest(filename=filename):
                root = ET.parse(CSL_DIR / filename).getroot()
                medium = root.find(".//csl:macro[@name='medium-id']/csl:choose", CSL_NS)
                self.assertIsNotNone(medium)
                ol_branches = [
                    node for node in list(medium)
                    if node.find("csl:text[@value='OL']", CSL_NS) is not None
                ]
                for branch in ol_branches:
                    branch_types = set((branch.get("type") or "").split())
                    self.assertTrue(forbidden_types.isdisjoint(branch_types))

    def test_access_is_suppressed(self) -> None:
        for filename in GBT_STYLES:
            with self.subTest(filename=filename):
                root = ET.parse(CSL_DIR / filename).getroot()
                access = root.find(".//csl:macro[@name='access']", CSL_NS)
                self.assertIsNotNone(access)
                self.assertEqual(list(access), [])


if __name__ == "__main__":
    unittest.main()
