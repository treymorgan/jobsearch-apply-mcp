"""Guards for profile directory resolution.

The shipped files under `.claude/skills/job-application-assistant/` are blank
templates tracked in git; the user's real profile is written to `profile/`,
which is gitignored. Reads prefer `profile/` and fall back to the templates so
a fresh checkout still answers rather than erroring.

The bug these tests exist for: resolving that choice **once at import** meant
`/setup` could populate `profile/` while the server was already running and
every subsequent read would keep returning the blank template until a restart.
Nothing surfaced it, so the user would finish onboarding and then have every CV
drafted from an empty profile, silently. The grounding audit that is supposed to
catch fabricated claims cannot help here, because an empty profile grounds
nothing at all.

So resolution must happen per read, and a blank-template fallback must be
visible to the caller rather than looking like a real but sparse profile.
"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "mcp_server"))


class ProfileResolutionTestCase(unittest.TestCase):
    """Each test gets an isolated workspace with template and profile dirs."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        # .resolve() matters on macOS, where /var is a symlink to /private/var
        # and workspace_root() returns the resolved form.
        self.home = Path(self._tmp.name).resolve()
        self.templates = (self.home / ".claude" / "skills"
                          / "job-application-assistant")
        self.templates.mkdir(parents=True)
        (self.templates / "01-candidate-profile.md").write_text(
            "# Candidate Profile\n- **Name:** [Your Name]\n", encoding="utf-8")
        self.user_profile = self.home / "profile"
        self.user_profile.mkdir()

        self._saved = {k: os.environ.get(k) for k in
                       ("JOBSEARCH_HOME", "PROFILE_DIR", "PROFILE_BACKUPS",
                        "JOBSEARCH_STATE_DIR")}
        os.environ["JOBSEARCH_HOME"] = str(self.home)
        os.environ["JOBSEARCH_STATE_DIR"] = str(self.home / "state")
        os.environ.pop("PROFILE_DIR", None)
        os.environ.pop("PROFILE_BACKUPS", None)

        # Reimport so module-level state is built against this workspace.
        for mod in ("jobsearch_mcp.profile", "jobsearch_mcp.paths"):
            sys.modules.pop(mod, None)
        self.profile = importlib.import_module("jobsearch_mcp.profile")

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        sys.modules.pop("jobsearch_mcp.profile", None)
        self._tmp.cleanup()


class TestProfileIsResolvedPerRead(ProfileResolutionTestCase):
    def test_falls_back_to_templates_when_profile_is_empty(self):
        self.assertIn("[Your Name]", self.profile.get_section("candidate"))
        self.assertTrue(self.profile.using_templates())

    def test_file_created_after_import_is_picked_up_without_restart(self):
        """The regression. /setup writes during a live session."""
        # Import-time state says "templates".
        self.assertTrue(self.profile.using_templates())

        (self.user_profile / "01-candidate-profile.md").write_text(
            "# Candidate Profile\n- **Name:** Real User\n", encoding="utf-8")

        got = self.profile.get_section("candidate")
        self.assertIn(
            "Real User",
            got,
            "a profile written after server start must be visible without a "
            "restart; resolving the directory once at import silently serves "
            "the blank template for the rest of the session",
        )
        self.assertNotIn("[Your Name]", got)
        self.assertFalse(self.profile.using_templates())

    def test_module_attribute_also_reflects_the_change(self):
        """Anything still reading profile.PROFILE_DIR must get a live answer."""
        self.assertEqual(self.profile.PROFILE_DIR, self.profile.TEMPLATE_DIR)
        (self.user_profile / "01-candidate-profile.md").write_text(
            "# Candidate Profile\nReal\n", encoding="utf-8")
        self.assertEqual(self.profile.PROFILE_DIR, self.user_profile)

    def test_search_profile_sees_late_writes_too(self):
        (self.user_profile / "01-candidate-profile.md").write_text(
            "# Candidate Profile\nDistinctiveTokenXYZ\n", encoding="utf-8")
        hits = self.profile.search_profile("DistinctiveTokenXYZ")
        self.assertTrue(hits, "search must read through the same live resolution")


class TestWritesNeverTouchTrackedTemplates(ProfileResolutionTestCase):
    def test_append_writes_to_profile_dir_not_templates(self):
        before = (self.templates / "01-candidate-profile.md").read_text(
            encoding="utf-8")

        self.profile.append_fact("candidate", "A confirmed new fact")

        self.assertEqual(
            (self.templates / "01-candidate-profile.md").read_text(
                encoding="utf-8"),
            before,
            "the tracked template must never be modified; a fork would publish "
            "the user's personal data",
        )
        written = (self.user_profile / "01-candidate-profile.md").read_text(
            encoding="utf-8")
        self.assertIn("A confirmed new fact", written)

    def test_replace_writes_to_profile_dir_not_templates(self):
        before = (self.templates / "01-candidate-profile.md").read_text(
            encoding="utf-8")

        self.profile.replace_section("candidate", "# Mine\n" + "x" * 100)

        self.assertEqual(
            (self.templates / "01-candidate-profile.md").read_text(
                encoding="utf-8"),
            before,
            "replace_section must not overwrite the tracked template",
        )
        self.assertIn(
            "# Mine",
            (self.user_profile / "01-candidate-profile.md").read_text(
                encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
