"""Guards for bundled font licensing.

This repository redistributes 19 font binaries (Lato and Raleway) under
`cover_letters/OpenFonts/`. Both families are licensed under the SIL Open Font
License 1.1, whose condition 2 requires that every redistributed copy carry the
copyright notice and the licence text. A repository whose only licence file is
the root MIT `LICENSE` implies the fonts are MIT, which they are not, and
publishing in that state is a licence violation.

The failure mode is silent: the fonts compile fine and nothing warns. So these
tests pin the three things that keep redistribution lawful:

(a) an OFL.txt exists beside each font family and carries its copyright notice;
(b) those files are actually tracked by git, not swallowed by an ignore rule
    (the fonts sit under a directory that .gitignore excludes and then
    re-includes with a negation, so this is easy to break by accident);
(c) the root LICENSE tells a reader that the fonts are covered separately.
"""
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONT_ROOT = REPO / "cover_letters" / "OpenFonts" / "fonts"

# family directory -> a distinctive substring of its required copyright notice
FAMILIES = {
    "lato": "tyPoland Lukasz Dziedzic",
    "raleway": "Matt McInerney",
}

FONT_SUFFIXES = (".ttf", ".otf")


class TestBundledFontsCarryTheirLicence(unittest.TestCase):
    def test_every_font_family_directory_has_an_ofl(self):
        families = sorted(
            d.name for d in FONT_ROOT.iterdir()
            if d.is_dir() and any(f.suffix.lower() in FONT_SUFFIXES
                                  for f in d.iterdir())
        )
        self.assertTrue(families, "no bundled font families found")
        for family in families:
            self.assertIn(
                family, FAMILIES,
                f"font family {family!r} is bundled but this test does not know "
                "its licence. Add it here with its copyright notice, and ship "
                "the corresponding licence file.",
            )
            self.assertTrue(
                (FONT_ROOT / family / "OFL.txt").is_file(),
                f"cover_letters/OpenFonts/fonts/{family}/OFL.txt is missing. "
                "The SIL OFL requires the copyright notice and licence to ship "
                "with any redistribution of the fonts.",
            )

    def test_each_ofl_carries_its_copyright_notice_and_the_licence_body(self):
        for family, holder in FAMILIES.items():
            text = (FONT_ROOT / family / "OFL.txt").read_text(encoding="utf-8")
            self.assertIn(
                holder, text,
                f"{family}/OFL.txt must carry the copyright notice naming "
                f"{holder}; the licence text alone does not satisfy OFL 1.1",
            )
            self.assertIn(
                "SIL OPEN FONT LICENSE Version 1.1", text,
                f"{family}/OFL.txt must contain the full licence text, not just "
                "a link to it",
            )
            self.assertIn(
                'Reserved Font Name', text,
                f"{family}/OFL.txt must preserve the Reserved Font Name "
                "declaration",
            )

    def test_licence_files_are_tracked_by_git(self):
        """A licence file that is gitignored does not ship, so it does not count.

        The font directory is excluded by the image ignore rules and re-included
        by a negation, which makes an accidental exclusion here plausible.
        """
        tracked = subprocess.run(
            ["git", "ls-files", "cover_letters/OpenFonts/"],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.split()
        for family in FAMILIES:
            rel = f"cover_letters/OpenFonts/fonts/{family}/OFL.txt"
            self.assertIn(
                rel, tracked,
                f"{rel} is not tracked by git, so it would not reach anyone who "
                "cloned or downloaded this project, and the fonts would ship "
                "without their licence",
            )

    def test_fonts_themselves_are_tracked(self):
        """If the fonts stopped shipping, the licence requirement would change."""
        tracked = subprocess.run(
            ["git", "ls-files", "cover_letters/OpenFonts/"],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.split()
        fonts = [f for f in tracked if f.lower().endswith(FONT_SUFFIXES)]
        self.assertTrue(
            fonts,
            "no font binaries are tracked. If the fonts were removed "
            "deliberately, drop the OFL files and this test with them.",
        )


class TestLicenceDisclosure(unittest.TestCase):
    def setUp(self):
        self.licence = (REPO / "LICENSE").read_text(encoding="utf-8")
        self.notices = (REPO / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")

    def test_licence_keeps_the_upstream_mit_copyright(self):
        """MIT requires the original copyright notice be retained."""
        self.assertIn(
            "Mads Lorentzen", self.licence,
            "the upstream author's MIT copyright must be retained; removing it "
            "is a licence violation",
        )

    def test_licence_stays_recognizable_as_mit(self):
        """Appended text breaks GitHub's licence detection.

        A repository whose licence reads as NOASSERTION tells every visitor
        nothing about their rights, so third-party notices live in their own
        file rather than being appended here.
        """
        self.assertTrue(
            self.licence.rstrip().endswith("SOFTWARE."),
            "LICENSE must contain only the MIT text; put third-party notices "
            "in THIRD-PARTY-NOTICES.md so licence detection keeps working",
        )

    def test_notices_disclose_the_font_licensing(self):
        self.assertIn(
            "SIL Open Font License", self.notices,
            "THIRD-PARTY-NOTICES.md must disclose that bundled fonts are "
            "licensed separately; MIT alone implies they are MIT, which they "
            "are not",
        )
        for family in FAMILIES:
            self.assertIn(
                f"fonts/{family}/OFL.txt", self.notices,
                f"THIRD-PARTY-NOTICES.md must point at the {family} licence file",
            )

    def test_readme_points_at_the_notices(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "THIRD-PARTY-NOTICES", readme,
            "a reader deciding whether they can reuse this needs the font "
            "caveat linked from the README, not buried",
        )


if __name__ == "__main__":
    unittest.main()
