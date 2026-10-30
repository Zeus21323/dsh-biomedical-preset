import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import resolve_volume_pages


class ParseWarnKeysTest(unittest.TestCase):
    def test_parses_grouped_warn_lines_with_showing_count(self) -> None:
        text = (
            "WARN: the following records are missing volume/pages/number — "
            "use DOI/title lookup to complete metadata before final export:\n"
            "  missing_volume (2, showing 2): zhang2024, li2025\n"
            "  missing_pages_and_number (1, showing 1): wang2026\n"
        )

        self.assertEqual(
            resolve_volume_pages.parse_warn_keys(text),
            ["zhang2024", "li2025", "wang2026"],
        )


if __name__ == "__main__":
    unittest.main()
