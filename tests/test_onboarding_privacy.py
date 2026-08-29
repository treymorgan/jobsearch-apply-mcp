"""Guards for the onboarding privacy model.

Upstream (issue #345) these tests pinned a warning next to `gh repo fork`,
because forks of public repos cannot be made private and /setup wrote
personal data into TRACKED files. That threat model has since been
inverted rather than removed: personal data now goes to `profile/` and
`jobsearch.config.json`, both gitignored, and the files under
`.claude/skills/job-application-assistant/` are blank templates that stay
tracked.

That is a stronger guarantee, but only while three things hold, which is
what these tests pin:

(a) the ignore rules for the personal-data locations really exist;
(b) the docs name which locations hold the user's data and say they are
    not tracked, so "can I publish this fork?" has a checkable answer;
(c) /setup writes to those ignored locations and never into the tracked
    templates, and says so before it writes anything.

If (c) regresses, nothing else fails loudly: setup would quietly populate
tracked files and the next push would publish a name, phone number,
employment history and salary floor.
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
SECURITY = REPO / "SECURITY.md"
GITIGNORE = REPO / ".gitignore"
SETUP_COMMAND = REPO / ".claude" / "commands" / "setup.md"
TEMPLATE_DIR = REPO / ".claude" / "skills" / "job-application-assistant"

# The only locations /setup may write personal data to.
PERSONAL_DATA_PATHS = ("profile/", "jobsearch.config.json")


def step3_body(text: str) -> str:
    start = text.index("## Step 3: Generate Profile Files")
    rest = text[start:]
    end = rest.index("## Step 4")
    return rest[:end]


class TestPersonalDataLocationsAreIgnored(unittest.TestCase):
    def test_gitignore_covers_every_personal_data_location(self):
        text = GITIGNORE.read_text(encoding="utf-8")
        for needle in ("profile/*", "jobsearch.config.json"):
            self.assertIn(
                needle,
                text,
                f".gitignore must ignore {needle!r}: /setup writes the user's "
                "real profile and search settings there, and this project is "
                "meant to be forked publicly",
            )

    def test_templates_stay_tracked(self):
        """A fresh clone needs the blank structure to start from."""
        self.assertTrue(
            (TEMPLATE_DIR / "01-candidate-profile.md").is_file(),
            "the profile templates must exist and stay tracked",
        )


class TestDocsExplainWherePersonalDataLives(unittest.TestCase):
    def test_readme_names_the_gitignored_locations(self):
        text = README.read_text(encoding="utf-8")
        for needle in PERSONAL_DATA_PATHS:
            self.assertIn(
                needle,
                text,
                "the README must name the locations holding personal data, "
                "not just gesture at 'your profile'",
            )
        self.assertRegex(
            text,
            re.compile(r"gitignored|not committed", re.IGNORECASE),
            "the README must state that personal data is not committed",
        )

    def test_security_doc_states_the_fork_rule(self):
        text = SECURITY.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            re.compile(r"fork", re.IGNORECASE),
            "SECURITY.md must address forking, the question every user asks",
        )
        for needle in PERSONAL_DATA_PATHS:
            self.assertIn(
                needle,
                text,
                "SECURITY.md must name the personal-data locations it claims "
                "are safe, so the claim is checkable",
            )


class TestSetupWritesOnlyToIgnoredLocations(unittest.TestCase):
    def setUp(self):
        self.text = SETUP_COMMAND.read_text(encoding="utf-8")

    def test_setup_declares_its_write_destination_before_writing(self):
        declaration = self.text.find("profile/")
        generate_at = self.text.index("## Step 3: Generate Profile Files")
        self.assertNotEqual(
            declaration, -1, "/setup must say where it writes personal data"
        )
        self.assertLess(
            declaration,
            generate_at,
            "the write destination must be stated before any file is written; "
            "a note that fires afterwards cannot inform the decision",
        )

    def test_setup_targets_the_ignored_profile_directory(self):
        body = step3_body(self.text)
        for name in (
            "profile/01-candidate-profile.md",
            "profile/02-behavioral-profile.md",
            "profile/04-job-evaluation.md",
            "profile/07-interview-prep.md",
        ):
            self.assertIn(
                name,
                body,
                f"/setup must write {name}, not the tracked template of the "
                "same name",
            )

    def test_setup_never_writes_into_the_tracked_template_directory(self):
        offenders = re.findall(
            r"(?:Populate|Update|Write|Generate)\s+`(\.claude/skills/"
            r"job-application-assistant/[^`]+)`",
            step3_body(self.text),
        )
        self.assertEqual(
            offenders,
            [],
            "Step 3 instructs a write into the tracked template directory: "
            f"{offenders}. Those files must stay blank so the project can be "
            "shared publicly; personal answers belong in profile/.",
        )

    def test_setup_does_not_edit_the_shipped_cv_sample(self):
        self.assertNotRegex(
            step3_body(self.text),
            re.compile(r"(?:Populate|Update|Write)\s+`cv/main_example\.tex`"),
            "cv/main_example.tex is the tracked sample CV; the user's real CV "
            "belongs in the gitignored cv/main_<name>.tex",
        )

    def test_setup_writes_the_search_config(self):
        self.assertIn(
            "jobsearch.config.json",
            self.text,
            "/setup must create jobsearch.config.json, or portal search "
            "returns nothing and the user has no way to know why",
        )

    def test_no_fork_instructions_survive_anywhere(self):
        """A `gh repo fork` walkthrough would predate the current model."""
        for path in (README, SECURITY):
            self.assertNotIn(
                "gh repo fork",
                path.read_text(encoding="utf-8"),
                f"{path.name} should not script a fork; the safety claim is "
                "about what is ignored, not how the fork was made",
            )


if __name__ == "__main__":
    unittest.main()
