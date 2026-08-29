#!/usr/bin/env python3
"""Verify that a generated PDF has the expected pages, extractable text, and
no forbidden characters (em-dashes, by house style).

The em-dash check is deliberately mechanical. `03-writing-style.md` rule 1
bans em-dashes, but a prompt rule is an instruction to a model, not a
guarantee - and an em-dash that reaches an employer cannot be recalled. This
checks the rendered text layer, which is what the reader actually sees.

En-dashes (U+2013) are NOT forbidden: moderncv renders legitimate date
ranges with them.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


class VerificationError(Exception):
    """Raised when a generated PDF does not satisfy its checks."""


def run_tool(command):
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except FileNotFoundError as exc:
        raise VerificationError(
            f"required command '{command[0]}' was not found. "
            "Install poppler-utils (macOS: brew install poppler, "
            "Debian/Ubuntu: apt install poppler-utils, Windows: choco install poppler)"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or (exc.stdout or "").strip()
        detail = detail or "command failed"
        raise VerificationError(f"{command[0]} could not read the PDF: {detail}") from exc


def parse_page_count(pdfinfo_output):
    match = re.search(r"^Pages:\s+(\d+)\s*$", pdfinfo_output, re.MULTILINE)
    if not match:
        raise VerificationError("pdfinfo output did not contain a page count")
    return int(match.group(1))


def normalize_text(text):
    return " ".join(text.split())


EM_DASH = "\u2014"


def verify_pdf(
    pdf_path,
    expected_pages=None,
    min_chars=1,
    required_text=(),
    forbidden_text=(),
):
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise VerificationError(f"PDF does not exist: {pdf_path}")

    if expected_pages is not None:
        actual_pages = parse_page_count(run_tool(["pdfinfo", str(pdf_path)]))
        if actual_pages != expected_pages:
            raise VerificationError(
                f"expected {expected_pages} page(s), found {actual_pages}"
            )

    extracted_text = normalize_text(
        run_tool(["pdftotext", "-layout", str(pdf_path), "-"])
    )
    if len(extracted_text) < min_chars:
        raise VerificationError(
            f"text layer has {len(extracted_text)} character(s); expected at least {min_chars}"
        )

    for required in required_text:
        if normalize_text(required) not in extracted_text:
            raise VerificationError(f"text layer is missing required text: {required!r}")

    for forbidden in forbidden_text:
        if forbidden and forbidden in extracted_text:
            index = extracted_text.index(forbidden)
            context = extracted_text[max(0, index - 60) : index + 60]
            label = "em-dash" if forbidden == EM_DASH else repr(forbidden)
            raise VerificationError(
                f"text layer contains forbidden {label}: ...{context}..."
            )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Verify a PDF's page count and ATS-readable text layer."
    )
    parser.add_argument("pdf", type=Path, help="PDF file to verify")
    parser.add_argument("--pages", type=int, help="required exact page count")
    parser.add_argument(
        "--min-chars",
        type=int,
        default=1,
        help="minimum non-whitespace text-layer characters (default: 1)",
    )
    parser.add_argument(
        "--contains",
        action="append",
        default=[],
        help="text that must appear after whitespace normalization; repeatable",
    )
    parser.add_argument(
        "--forbid",
        action="append",
        default=[],
        help="text that must NOT appear in the text layer; repeatable",
    )
    parser.add_argument(
        "--no-em-dash",
        action="store_true",
        help="fail if the text layer contains an em-dash (house style rule 1)",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    forbidden = list(args.forbid)
    if args.no_em_dash:
        forbidden.append(EM_DASH)
    try:
        verify_pdf(args.pdf, args.pages, args.min_chars, args.contains, forbidden)
    except VerificationError as exc:
        print(f"Error: {args.pdf}: {exc}", file=sys.stderr)
        return 1
    print(f"Verified {args.pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
