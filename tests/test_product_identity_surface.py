"""Static contracts for Automoat's durable product hierarchy."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
GENERATED_LANDING = ROOT / "generated" / "landing.html"
PUBLIC_INDEX = ROOT / "index.html"
README = ROOT / "README.md"


class ProductIdentitySurfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generated_bytes = GENERATED_LANDING.read_bytes()
        cls.public_bytes = PUBLIC_INDEX.read_bytes()
        cls.html = cls.public_bytes.decode("utf-8")
        cls.readme = README.read_text(encoding="utf-8")

    def test_generated_landing_is_the_exact_public_index(self) -> None:
        self.assertEqual(self.generated_bytes, self.public_bytes)

    def test_metadata_and_h1_lead_with_the_durable_product_job(self) -> None:
        self.assertIn(
            "<title>Automoat | Turn proprietary work into a durable moat</title>",
            self.html,
        )
        self.assertIn(
            'content="Automoat is a local-first workbench for discovering, defining, '
            'proving, and operationalizing a moat from proprietary workflows, decisions, '
            'outcomes, and datasets."',
            self.html,
        )
        headings = re.findall(r"<h1>(.*?)</h1>", self.html, flags=re.DOTALL)
        self.assertEqual(
            headings,
            [
                "Discover, define, prove, and operationalize the moat already inside "
                "your business."
            ],
        )

    def test_identity_and_both_entry_points_precede_the_current_initiative(self) -> None:
        ordered_markers = [
            'id="identity" data-product-identity',
            'id="entry-points" data-product-entry-points',
            'id="terminal"',
            'id="whole-record"',
            'id="release-notes"',
        ]
        positions = [self.html.index(marker) for marker in ordered_markers]
        self.assertEqual(positions, sorted(positions))

        initiative_start = positions[3]
        release_notes_start = positions[4]
        initiative = self.html[initiative_start:release_notes_start]
        self.assertIn("Current initiative · Released", initiative)
        self.assertIn("Whole-Record Check", initiative)
        self.assertIn("Dallas validation set", initiative)
        self.assertIn("not the full Automoat product", initiative)

    def test_runtime_cockpit_is_evidence_not_the_product_identity(self) -> None:
        self.assertIn("Build and runtime evidence", self.html)
        self.assertIn("not the product\n                  identity", self.html)
        self.assertNotIn("Live product surface", self.html)
        self.assertNotIn("the product surface", self.html.lower())

    def test_public_release_notes_record_the_identity_correction(self) -> None:
        release_notes_start = self.html.index('id="release-notes"')
        release_notes = self.html[release_notes_start:]
        self.assertIn("2026-08-19", release_notes)
        self.assertIn("Restored Automoat's durable product hierarchy", release_notes)
        self.assertIn("case rather than the product identity", release_notes)

    def test_readme_keeps_the_release_subordinate(self) -> None:
        identity = self.readme.index("discover, define, prove, and operationalize")
        business_first = self.readme.index("Business-first discovery")
        dataset_first = self.readme.index("Dataset-first build + eval")
        initiative = self.readme.index("Current Initiative: Whole-Record Check")
        self.assertLess(identity, business_first)
        self.assertLess(business_first, initiative)
        self.assertLess(dataset_first, initiative)
        self.assertIn("not Automoat's product identity", self.readme)


if __name__ == "__main__":
    unittest.main()
