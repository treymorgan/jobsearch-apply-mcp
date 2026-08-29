import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.verify_pdf import (
    EM_DASH,
    VerificationError,
    build_parser,
    parse_page_count,
    run_tool,
    verify_pdf,
)


class ParsePageCountTests(unittest.TestCase):
    def test_parses_pdfinfo_page_count(self):
        self.assertEqual(parse_page_count("Title: Example\nPages:          2\n"), 2)

    def test_rejects_output_without_page_count(self):
        with self.assertRaisesRegex(VerificationError, "did not contain a page count"):
            parse_page_count("Title: Example\n")


class VerifyPdfTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pdf = Path(self.temp_dir.name) / "example.pdf"
        self.pdf.touch()

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("tools.verify_pdf.run_tool")
    def test_accepts_expected_pages_and_text(self, mock_run_tool):
        mock_run_tool.side_effect = [
            "Pages:          2\n",
            "Professional\nExperience   [your.email@example.com]\n",
        ]

        verify_pdf(
            self.pdf,
            expected_pages=2,
            min_chars=20,
            required_text=("Professional Experience", "[your.email@example.com]"),
        )

    @patch("tools.verify_pdf.run_tool")
    def test_rejects_wrong_page_count(self, mock_run_tool):
        mock_run_tool.return_value = "Pages:          3\n"

        with self.assertRaisesRegex(VerificationError, "expected 2 page.*found 3"):
            verify_pdf(self.pdf, expected_pages=2)

    @patch("tools.verify_pdf.run_tool")
    def test_rejects_too_little_extractable_text(self, mock_run_tool):
        mock_run_tool.return_value = "short"

        with self.assertRaisesRegex(VerificationError, "expected at least 20"):
            verify_pdf(self.pdf, min_chars=20)

    @patch("tools.verify_pdf.run_tool")
    def test_rejects_missing_required_text(self, mock_run_tool):
        mock_run_tool.return_value = "Readable text, but not the expected section."

        with self.assertRaisesRegex(VerificationError, "Professional Experience"):
            verify_pdf(self.pdf, required_text=("Professional Experience",))

    def test_rejects_missing_pdf(self):
        with self.assertRaisesRegex(VerificationError, "PDF does not exist"):
            verify_pdf(Path(self.temp_dir.name) / "missing.pdf")


class RunToolTests(unittest.TestCase):
    @patch("tools.verify_pdf.subprocess.run", side_effect=FileNotFoundError)
    def test_reports_missing_poppler_command(self, _mock_run):
        with self.assertRaisesRegex(VerificationError, "install poppler-utils"):
            run_tool(["pdftotext", "example.pdf", "-"])

    @patch("tools.verify_pdf.subprocess.run")
    def test_reports_unreadable_pdf(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["pdfinfo", "example.pdf"], stderr="invalid PDF"
        )

        with self.assertRaisesRegex(VerificationError, "invalid PDF"):
            run_tool(["pdfinfo", "example.pdf"])


if __name__ == "__main__":
    unittest.main()


class ForbiddenTextTests(unittest.TestCase):
    """House style rule 1 bans em-dashes. A prompt rule is an instruction to a
    model, not a guarantee - and an em-dash that reaches an employer cannot be
    recalled, so it is checked mechanically against the rendered text layer."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pdf = Path(self.temp_dir.name) / "example.pdf"
        self.pdf.touch()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_em_dash_constant_is_the_real_character(self):
        self.assertEqual(EM_DASH, "\u2014")
        self.assertNotEqual(EM_DASH, "\u2013", "en-dash must not be treated as em-dash")

    @patch("tools.verify_pdf.run_tool")
    def test_rejects_an_em_dash_in_the_text_layer(self, mock_run_tool):
        mock_run_tool.return_value = "I led the team \u2014 and delivered it early."

        with self.assertRaisesRegex(VerificationError, "forbidden em-dash"):
            verify_pdf(self.pdf, forbidden_text=(EM_DASH,))

    @patch("tools.verify_pdf.run_tool")
    def test_allows_an_en_dash_date_range(self, mock_run_tool):
        """moderncv renders legitimate date ranges with en-dashes; banning them
        would fail every CV that has ever listed a job."""
        mock_run_tool.return_value = "Project Coordinator 2022\u20132024 Acme Ltd"

        verify_pdf(self.pdf, forbidden_text=(EM_DASH,))

    @patch("tools.verify_pdf.run_tool")
    def test_error_quotes_the_surrounding_sentence(self, mock_run_tool):
        """A bare 'contains an em-dash' is unactionable in a 2-page CV."""
        mock_run_tool.return_value = "filler " * 20 + "project delivery \u2014 at scale"

        with self.assertRaisesRegex(VerificationError, "project delivery"):
            verify_pdf(self.pdf, forbidden_text=(EM_DASH,))

    @patch("tools.verify_pdf.run_tool")
    def test_empty_forbidden_string_is_ignored(self, mock_run_tool):
        """'' is in every string; an empty --forbid must not fail everything."""
        mock_run_tool.return_value = "Perfectly ordinary text."

        verify_pdf(self.pdf, forbidden_text=("",))

    def test_cli_exposes_forbid_and_no_em_dash(self):
        args = build_parser().parse_args(
            ["x.pdf", "--no-em-dash", "--forbid", "a", "--forbid", "b"]
        )
        self.assertTrue(args.no_em_dash)
        self.assertEqual(args.forbid, ["a", "b"])
