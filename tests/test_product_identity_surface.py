"""Static contracts for Automoat's durable product hierarchy."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
GENERATED_LANDING = ROOT / "generated" / "landing.html"
PUBLIC_INDEX = ROOT / "index.html"
README = ROOT / "README.md"
PLANNER_SCRIPT = ROOT / "assets" / "moat-planner.js"


class ProductIdentitySurfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generated_bytes = GENERATED_LANDING.read_bytes()
        cls.public_bytes = PUBLIC_INDEX.read_bytes()
        cls.html = cls.public_bytes.decode("utf-8")
        cls.readme = README.read_text(encoding="utf-8")
        cls.planner_script = PLANNER_SCRIPT.read_text(encoding="utf-8")

    def test_generated_landing_is_the_exact_public_index(self) -> None:
        self.assertEqual(self.generated_bytes, self.public_bytes)

    def test_metadata_and_h1_lead_with_the_product_questionnaire(self) -> None:
        self.assertIn(
            "<title>Automoat | Put your local tokens to useful work</title>",
            self.html,
        )
        headings = re.findall(r"<h1[^>]*>(.*?)</h1>", self.html, flags=re.DOTALL)
        self.assertEqual(
            headings,
            ["Put your local tokens to useful work."],
        )

    def test_planner_leads_the_product_before_evidence_and_release_history(self) -> None:
        ordered_markers = [
            'id="planner"',
            'id="how-it-works"',
            'id="examples"',
            'id="terminal"',
            'id="local-run"',
            'id="whole-record"',
            'id="release-notes"',
        ]
        positions = [self.html.index(marker) for marker in ordered_markers]
        self.assertEqual(positions, sorted(positions))

        planner = self.html[positions[0]:positions[1]]
        self.assertIn("Put your local tokens to useful work", planner)
        self.assertIn("moat", planner.lower())

        local_run = self.html[positions[4]:positions[5]]
        local_run_text = re.sub(r"\s+", " ", local_run)
        self.assertIn("Current initiative · Local Run Receipt", local_run_text)
        self.assertIn("Prompt, completion, and total tokens", local_run_text)
        self.assertIn("refuses remote inference without an explicit opt-in", local_run_text)

        whole_record = self.html[positions[5]:positions[6]]
        self.assertIn("Released capability · Moat Builder", whole_record)
        self.assertIn("Whole-Record Check", whole_record)
        self.assertIn("Dallas validation set", whole_record)
        self.assertIn("not the full Automoat product", whole_record)

    def test_product_questionnaire_has_four_steps_and_the_full_input_contract(self) -> None:
        planner_start = self.html.index('id="planner"')
        how_it_works_start = self.html.index('id="how-it-works"')
        planner = self.html[planner_start:how_it_works_start]

        self.assertIn("data-moat-planner", planner)
        self.assertIn("data-planner-form", planner)
        self.assertEqual(
            len(re.findall(r"\bdata-planner-step(?:\s|=|>)", planner)),
            4,
        )
        for field_name in [
            "hardwareIntent",
            "platform",
            "memoryGb",
            "schedule",
            "hoursPerDay",
            "resourceCeiling",
            "workCategories",
            "moatMode",
            "idea",
            "privateContext",
            "usefulResult",
            "goal",
            "network",
            "autonomy",
            "verifier",
            "useHostedPlanner",
        ]:
            self.assertRegex(planner, rf'name=["\']{field_name}["\']')

        self.assertIn('name="memoryGb" value="24"', planner)
        self.assertIn('name="memoryGb" value="48"', planner)
        self.assertGreaterEqual(planner.count('role="group" aria-labelledby='), 7)
        self.assertIn("data-planner-cancel", planner)
        self.assertIn("data-plan-boundary-network", planner)
        self.assertIn("data-plan-boundary-capacity", planner)

    def test_questionnaire_discloses_the_hosted_planning_boundary(self) -> None:
        planner_start = self.html.index('id="planner"')
        how_it_works_start = self.html.index('id="how-it-works"')
        planner_text = re.sub(
            r"\s+",
            " ",
            re.sub(r"<[^>]+>", " ", self.html[planner_start:how_it_works_start]),
        ).lower()
        for disclosure in [
            "planning answers",
            "hosted model",
            "no files",
            "local workloads",
            "secrets",
        ]:
            self.assertIn(disclosure, planner_text)

    def test_planner_client_posts_to_the_api_and_renders_model_text_safely(self) -> None:
        self.assertIn('src="/assets/moat-planner.js"', self.html)
        self.assertIn('fetch("/api/moat-plan"', self.planner_script)
        self.assertIn('method: "POST"', self.planner_script)
        self.assertIn(".textContent", self.planner_script)
        self.assertNotRegex(self.planner_script, r"\binnerHTML\b")

    def test_hosted_tailoring_is_explicit_and_browser_only_mode_skips_the_api(self) -> None:
        self.assertIn("Tailor with hosted AI", self.html)
        self.assertIn("browser-only rule-based starter", self.html)
        self.assertIn('if (!field("useHostedPlanner").checked)', self.planner_script)
        self.assertIn('fallback_reason: "hosted_planner_opted_out"', self.planner_script)
        self.assertIn('inference_scope: "browser_only"', self.planner_script)
        self.assertIn(
            'idea: checkedValue("moatMode") === "shape" ? field("idea").value.trim() : ""',
            self.planner_script,
        )

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
