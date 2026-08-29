"""Guards for the settings.json shape allowlist.

`tools/security_guards.py` originally validated only the *values* inside
`permissions.allow` and the hooks block. That misses the settings which are
dangerous precisely because this repo never mentions them:
`"defaultMode": "bypassPermissions"` disables the approval prompt for every
tool call, which is strictly worse than anything a single allowlist entry could
do, and it passed the guard cleanly.

SECURITY.md tells users the check "fails any change that widens that
allowlist". These tests keep that claim true by pinning the *shape* of the file:
unknown top-level keys and unknown `permissions` sub-keys are rejected, so a new
setting has to be reviewed before it can ship.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SETTINGS = REPO / ".claude" / "settings.json"
GUARD = REPO / "tools" / "security_guards.py"


def run_guard() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GUARD)],
        cwd=REPO, capture_output=True, text=True,
    )


class SettingsGuardTestCase(unittest.TestCase):
    """Mutates the real settings.json, then always restores it byte for byte."""

    def setUp(self):
        self.original = SETTINGS.read_bytes()

    def tearDown(self):
        SETTINGS.write_bytes(self.original)

    def write(self, data: dict):
        SETTINGS.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def settings(self) -> dict:
        return json.loads(self.original.decode("utf-8"))


class TestGuardRejectsUnreviewedSettings(SettingsGuardTestCase):
    def test_baseline_settings_pass(self):
        """Guard must pass as shipped, or the failures below prove nothing."""
        result = run_guard()
        self.assertEqual(
            result.returncode, 0,
            f"shipped settings.json must pass the guard:\n{result.stdout}"
        )

    def test_bypass_permissions_default_mode_fails(self):
        """The exact bypass that used to slip through."""
        self.write({"permissions": {"allow": [], "defaultMode": "bypassPermissions"}})
        result = run_guard()
        self.assertNotEqual(
            result.returncode, 0,
            "defaultMode=bypassPermissions disables the approval prompt for "
            "every tool call and must fail the guard",
        )
        self.assertIn("defaultMode", result.stdout)

    def test_unknown_permissions_key_fails(self):
        self.write({"permissions": {"allow": [], "someFutureKey": True}})
        result = run_guard()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("someFutureKey", result.stdout)

    def test_unknown_top_level_key_fails(self):
        self.write({"permissions": {"allow": []},
                    "enableAllProjectMcpServers": True})
        result = run_guard()
        self.assertNotEqual(
            result.returncode, 0,
            "a top-level key can grant tool access without appearing in the "
            "permissions allowlist",
        )
        self.assertIn("enableAllProjectMcpServers", result.stdout)

    def test_widening_the_allow_list_still_fails(self):
        """The original value-level guard must keep working."""
        data = self.settings()
        data["permissions"]["allow"].append("Bash(curl:*)")
        self.write(data)
        result = run_guard()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("curl", result.stdout)


class TestForbiddenConfigFiles(unittest.TestCase):
    def test_guard_names_the_forbidden_files(self):
        text = GUARD.read_text(encoding="utf-8")
        for name in (".mcp.json", ".claude/settings.local.json"):
            self.assertIn(
                name, text,
                f"{name} configures tool access outside the reviewed "
                "settings.json and must be checked for",
            )

    def test_forbidden_files_are_absent_from_the_tree(self):
        for name in (".mcp.json", ".claude/settings.local.json"):
            self.assertFalse(
                (REPO / name).exists(),
                f"{name} must not be committed; a fork would inherit an "
                "unreviewed tool configuration",
            )

    def test_guard_fails_when_a_forbidden_file_appears(self):
        probe = REPO / ".mcp.json"
        probe.write_text('{"mcpServers": {}}', encoding="utf-8")
        try:
            result = run_guard()
            self.assertNotEqual(
                result.returncode, 0,
                "a committed .mcp.json must fail the guard",
            )
            self.assertIn(".mcp.json", result.stdout)
        finally:
            probe.unlink()


if __name__ == "__main__":
    unittest.main()
