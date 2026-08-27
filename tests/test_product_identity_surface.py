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
            "<title>Automoat | Local AI that compounds your private advantage</title>",
            self.html,
        )
        self.assertIn(
            'content="Run AI on consumer hardware you control, measure the token economics, '
            'and turn private workflows, corrections, and outcomes into a moat you can prove."',
            self.html,
        )
        headings = re.findall(r"<h1>(.*?)</h1>", self.html, flags=re.DOTALL)
        self.assertEqual(
            headings,
            ["Run AI locally. Build what only your business can know."],
        )

    def test_two_pillars_and_core_gates_precede_capabilities(self) -> None:
        ordered_markers = [
            'id="identity" data-product-identity',
            'id="entry-points" data-product-entry-points',
            'id="terminal"',
            'id="local-run"',
            'id="whole-record"',
            'id="release-notes"',
        ]
        positions = [self.html.index(marker) for marker in ordered_markers]
        self.assertEqual(positions, sorted(positions))

        identity = self.html[positions[0]:positions[1]]
        self.assertIn("Local AI on hardware you control", identity)
        self.assertIn("A harness for building your moat", identity)
        self.assertIn("Token economics", identity)
        self.assertIn("Privacy boundary", identity)
        self.assertIn("Task lift", identity)

        local_run = self.html[positions[3]:positions[4]]
        local_run_text = re.sub(r"\s+", " ", local_run)
        self.assertIn("Current initiative · Local Run Receipt", local_run_text)
        self.assertIn("Prompt, completion, and total tokens", local_run_text)
        self.assertIn("refuses remote inference without an explicit opt-in", local_run_text)

        whole_record = self.html[positions[4]:positions[5]]
        self.assertIn("Released capability · Moat Builder", whole_record)
        self.assertIn("Whole-Record Check", whole_record)
        self.assertIn("Dallas validation set", whole_record)
        self.assertIn("not the full Automoat product", whole_record)

    def test_dflash_is_an_example_not_a_shipped_speed_claim(self) -> None:
        html_text = re.sub(r"\s+", " ", self.html)
        self.assertIn("DFlash2 is one example", html_text)
        self.assertIn("not a bundled Automoat", html_text)
        self.assertIn("not a universal speed claim", html_text)
        self.assertNotIn("3× faster on consumer hardware", html_text)
        self.assertNotIn("free tokens", html_text.lower())

    def test_runtime_cockpit_is_evidence_not_the_product_identity(self) -> None:
        self.assertIn("Build and runtime evidence", self.html)
        self.assertIn("not the product\n                  identity", self.html)
        self.assertIn("render codex relay", self.html)
        self.assertNotIn("render codex live", self.html)
        self.assertNotIn("Live product surface", self.html)
        self.assertNotIn("the product surface", self.html.lower())

    def test_runtime_badge_fails_closed_on_degraded_or_stale_relay_health(self) -> None:
        self.assertIn('status.cockpit_ok === true && reported === "live"', self.html)
        self.assertIn('status.cockpit_health_label === "string"', self.html)
        self.assertIn('meta.dataset.state = health.state', self.html)
        self.assertIn('.terminal-meta[data-state="live"] .terminal-live-dot', self.html)
        self.assertIn('meta.dataset.state = "error"', self.html)

    def test_public_release_notes_record_the_identity_correction(self) -> None:
        release_notes_start = self.html.index('id="release-notes"')
        release_notes = self.html[release_notes_start:]
        self.assertIn("2026-08-27", release_notes)
        self.assertIn("measurable local AI on consumer", release_notes)
        self.assertIn("Local Run Receipt contract", release_notes)
        self.assertIn("2026-08-19", release_notes)
        self.assertIn("Restored Automoat's durable product hierarchy", release_notes)
        self.assertIn("case rather than the product identity", release_notes)

    def test_readme_keeps_the_release_subordinate(self) -> None:
        local_ai = self.readme.index("Local AI on consumer hardware")
        moat_harness = self.readme.index("A harness for building the user's moat")
        local_receipt = self.readme.index("Current Initiative: Local Run Receipt")
        whole_record = self.readme.index("Released Moat Builder Capability: Whole-Record Check")
        self.assertLess(local_ai, local_receipt)
        self.assertLess(moat_harness, local_receipt)
        self.assertLess(local_receipt, whole_record)
        self.assertIn("Token cost and privacy are core product gates", self.readme)
        self.assertIn("not Automoat's product identity", self.readme)


if __name__ == "__main__":
    unittest.main()
