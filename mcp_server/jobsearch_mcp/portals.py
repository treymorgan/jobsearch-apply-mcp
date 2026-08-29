"""Portal adapters: shell out to the bun CLIs and normalize their output.

Portals emit different shapes - some carry a structured work-mode field, others
carry nothing but a location string. Everything is flattened to one schema here
so the MCP tools never leak per-portal quirks to the caller.

**Sanctioned sources only.** This project deliberately does not scrape job
boards whose terms of service prohibit automated access. Portals here either
expose an official API or explicitly permit programmatic use. A portal that
requires evading a ToS does not belong in this file, however useful its data.
"""
from __future__ import annotations

import os
import json
import logging
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config
from .paths import workspace_root

log = logging.getLogger("jobsearch-mcp.portals")

# Throttle. A default search fans out to 14 back-to-back portal requests, and
# LinkedIn's own SKILL.md says to keep volume low - automated access is against
# its ToS and is only defensible as low-rate personal use. The manual scrape this
# server replaced slept 3s between calls; without an equivalent here the server
# is strictly more abusive than the thing it automated, and the failure mode is
# an IP block that takes the whole tool offline.
_MIN_INTERVAL = float(os.environ.get("PORTAL_MIN_INTERVAL", "3.0"))
_throttle_lock = threading.Lock()
_last_call = 0.0


def _throttle():
    global _last_call
    with _throttle_lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            log.debug("throttling portal call for %.1fs", wait)
            time.sleep(wait)
        _last_call = time.monotonic()

def _find_bun() -> str:
    """Locate the bun runtime.

    Bun is not on PATH in every environment - macOS installs it to ~/.bun/bin,
    Windows to %USERPROFILE%\\.bun\\bin, and neither is inherited by a GUI-launched
    MCP client. Falling back to the bare name lets PATH work when it does, and
    produces a readable "not found" rather than a mystery failure when it does not.
    """
    explicit = os.environ.get("BUN_PATH")
    if explicit:
        return explicit
    found = shutil.which("bun")
    if found:
        return found
    for cand in (Path.home() / ".bun" / "bin" / "bun",
                 Path.home() / ".bun" / "bin" / "bun.exe",
                 Path("/usr/local/bin/bun"),
                 Path("/opt/homebrew/bin/bun")):
        if cand.is_file():
            return str(cand)
    return "bun"


BUN = _find_bun()

# Where the portal search CLIs live. Defaults to the repo's .agents/skills
# directory so a local checkout works with no configuration; the container
# image overrides it to /app/portals.
PORTAL_DIR = os.environ.get(
    "PORTAL_DIR", str(workspace_root() / ".agents" / "skills"))


def portals_available() -> tuple[bool, str]:
    """Whether the portal CLIs can actually run, and why not if they cannot."""
    if not Path(PORTAL_DIR).is_dir():
        return False, f"portal directory not found: {PORTAL_DIR}"
    if not (shutil.which(BUN) or Path(BUN).is_file()):
        return False, ("bun runtime not found - install it from https://bun.sh "
                       "or set BUN_PATH to its full path")
    return True, "ok"


# Phrasings that establish a role is remote. The list is deliberately long:
# employers describe remote work in prose, not with a checkbox. One real posting
# said only "performed in the colleague's home" - unmistakably remote to a human
# reader, but classified `unconfirmed` until that phrasing was added here.
REMOTE_POS = ("fully remote", "100% remote", "work from anywhere", "remote-first",
              "remote first", "distributed team", "telecommute", "work remotely",
              "remote position", "remote role", "remote opportunity",
              "work from home", "home-based", "home based",
              "performed in the colleague's home", "in the colleague's home",
              "employee's home", "your home office", "remote (us", "us-remote",
              "remote - us", "anywhere in the us", "anywhere in the united states",
              # ATS boilerplate. Some systems render the remote flag as
              # "Location : Address Remote" plus a "Remote Work Notification"
              # block listing ineligible states, never saying "fully remote".
              "location : address remote", "location: remote",
              "location : remote", "remote work notification",
              "work location: remote", "remote location",
              "unable to offer remote work to residents",
              "position is remote", "role is remote")
# Onsite/hybrid signals. These must be WORK-ARRANGEMENT phrases, never bare
# words. A bare "hybrid" produced two false negatives in one day: it matched
# "hybrid cloud environment" and "traditional and hybrid" in postings that were
# both fully remote. A false negative here is the dangerous direction - it
# silently vetoes a qualifying job, whereas a false positive only costs a
# manual check.
REMOTE_NEG = (
    "hybrid work", "hybrid role", "hybrid position", "hybrid schedule",
    "hybrid model", "hybrid arrangement", "hybrid environment - ",
    "is hybrid", "this role is hybrid", "hybrid (", "work model: hybrid",
    "days in office", "days per week in the office", "days a week in the office",
    "days per week onsite", "days a week onsite", "in-office days",
    "onsite position", "onsite role", "fully onsite", "100% onsite",
    "onsite employment", "onsite at the", "on-site employment",
    "on-site position", "on-site role", "required to be onsite",
    "required to be in the office", "must be located in", "must reside in",
    "in the office 3", "in the office 4", "in the office 5",
    "relocation is required", "no remote", "not a remote",
)


class PortalError(RuntimeError):
    pass


def _run(args: list[str], timeout: int = 120) -> dict:
    ok, why = portals_available()
    if not ok:
        raise PortalError(why)
    _throttle()
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise PortalError(f"portal call timed out after {timeout}s") from exc
    except FileNotFoundError as exc:
        raise PortalError(
            f"could not launch the portal CLI ({args[0]}). Install bun from "
            "https://bun.sh, or set BUN_PATH to its full path.") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:400]
        raise PortalError(f"portal CLI exited {proc.returncode}: {detail}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise PortalError(f"portal CLI returned non-JSON: {proc.stdout[:200]}") from exc


def _normalize(text: str) -> str:
    """Lowercase and fold typographic punctuation to ASCII.

    Job postings are copy-pasted out of Word, so apostrophes are usually U+2019,
    not '. A pattern written with a straight apostrophe silently fails to match:
    a posting reading "performed in the colleague\u2019s home" stayed `unconfirmed`
    even after that exact phrase was added to REMOTE_POS.
    """
    return (text.lower()
            .replace("\u2019", "'").replace("\u2018", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u2013", "-").replace("\u2014", "-")
            .replace("\u00a0", " "))


def classify_remote(location: str | None, description: str | None) -> str:
    """Classify a posting's work arrangement from its own text.

    Returns one of: local, remote-confirmed, onsite-or-hybrid, unconfirmed.

    `local` means the posting sits inside the commutable area configured in
    `search.local_metro`, where onsite and hybrid are both acceptable, so no
    remote proof is needed. Everything else must prove remote from the
    description. A portal's own remote filter is deliberately not consulted:
    LinkedIn's returns city-based rows for remote roles and its search results
    carry no workplace-type field at all.
    """
    if config.get().is_local(location):
        return "local"
    if not description:
        return "unconfirmed"
    low = _normalize(description)
    if any(p in low for p in REMOTE_POS):
        return "remote-confirmed"
    if any(n in low for n in REMOTE_NEG):
        return "onsite-or-hybrid"
    return "unconfirmed"


def is_relevant(title: str | None) -> bool:
    """Delegates to the user's configured relevance filter (default: allow all)."""
    return config.get().is_relevant(title)


def is_ic_only(title: str | None) -> bool:
    """Delegates to the user's configured leadership-scope flag (default: off)."""
    return config.get().is_ic_only(title)


# Salary formats seen in the wild. A pattern that only matches "$148,700"
# silently returns "no salary stated" for three common real-world shapes:
# "US, TX, Dallas - 148,700.00 - 201,200.00 USD annually" (no currency symbol),
# "$200K - $253K" (abbreviated), and prose hiring-range wording. A missed band
# is not cosmetic - the deal-breaker check then cannot enforce the salary floor,
# so an under-paying role passes as merely "unstated".
_SALARY_PATTERNS = (
    # $148,700 / $148,700.00
    re.compile(r"\$\s?(\d{2,3},\d{3})(?:\.\d{2})?"),
    # $200K / $200k / $200 K
    re.compile(r"\$\s?(\d{2,3})\s?[kK]\b"),
    # bare 148,700.00 - only with a currency or pay-context word nearby, so
    # random comma numbers (headcount, revenue) are not mistaken for pay
    re.compile(
        r"(?:USD|salary|pay|compensation|range|annually|per year|/yr|base)"
        r"[^\n]{0,80}?(\d{2,3},\d{3})(?:\.\d{2})?",
        re.I),
    # Same, but with the currency/period word AFTER the figures. Postings that
    # read "US, TX, Dallas - 148,700.00 - 201,200.00 USD annually" never fire a
    # context-word-first pattern. This must capture BOTH ends
    # of the range: a single non-greedy group consumes the whole span and
    # returns only the lower figure, which would silently halve the band and
    # let an under-paying role clear the floor check.
    re.compile(
        r"(\d{2,3},\d{3})(?:\.\d{2})?\s*(?:-|\u2013|\u2014|to)\s*"
        r"(\d{2,3},\d{3})(?:\.\d{2})?[^\n]{0,40}?"
        r"(?:USD|annually|per year|/yr|a year)",
        re.I),
)


def extract_salary(text: str | None) -> tuple[int | None, int | None]:
    """Best-effort salary band. Returns (min, max) or (None, None)."""
    if not text:
        return None, None
    nums: list[int] = []
    for pat in _SALARY_PATTERNS:
        for m in pat.findall(text):
            # A multi-group pattern yields a tuple; single-group yields a str.
            for raw in ((m,) if isinstance(m, str) else m):
                if not raw:
                    continue
                raw = raw.replace(",", "")
                nums.append(int(raw) * 1000 if len(raw) <= 3 else int(raw))
    # Plausible annual salaries only. Filters out equity counts, headcount,
    # revenue figures and the "401(k)" style noise that survives the patterns.
    nums = [n for n in nums if 30_000 <= n <= 1_500_000]
    return (min(nums), max(nums)) if nums else (None, None)


def _within_days(iso: str | None, days: int | None) -> bool:
    if not days or not iso:
        return True
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return d >= datetime.now(timezone.utc) - timedelta(days=days)


# ---------------- Adzuna ----------------

def adzuna_configured() -> bool:
    return bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY"))


def adzuna_search(query: str, location: str = "", country: str = "",
                  remote_only: bool = False, days: int = 14,
                  limit: int = 20) -> list[dict]:
    """Search Adzuna's official API.

    `location` is free text (city, region, postcode). `country` is a two-letter
    market; when omitted it is derived from the configured remote_region, since
    a user searching "United States" wants the `us` market.
    """
    cfg = config.get()
    country = (country or cfg.search.remote_region or "us").lower()
    args = [BUN, "run", f"{PORTAL_DIR}/adzuna-search/cli/src/cli.ts", "search",
            "--country", country, "--format", "json", "--limit", str(limit)]
    if query:
        args += ["--query", query]
    if location:
        args += ["--where", location]
    if days:
        args += ["--jobage", str(days)]
    if remote_only:
        args += ["--remote"]
    if cfg.deal_breakers.salary_floor:
        args += ["--salary-min", str(cfg.deal_breakers.salary_floor)]
    data = _run(args)
    out = []
    for j in data.get("results", []):
        # A predicted salary is Adzuna's estimate, not the employer's offer.
        # Dropping it keeps the deal-breaker check honest: it reports "no salary
        # stated" rather than vetoing a job on a number nobody published.
        predicted = bool(j.get("salary_is_predicted"))
        out.append({
            "portal": "adzuna", "job_id": j.get("id"),
            "url": (j.get("url") or "").split("?")[0],
            "title": j.get("title"), "company": j.get("company"),
            "location": j.get("location"), "posted_date": j.get("date"),
            "description": j.get("description"),
            "salary_min": None if predicted else j.get("salary_min"),
            "salary_max": None if predicted else j.get("salary_max"),
        })
    return out


def adzuna_detail(job_id: str) -> dict:
    """Adzuna returns descriptions inline with search results.

    There is no per-ad detail endpoint, so this deliberately returns nothing and
    lets the caller fall back to what was already stored. Fetching the ad's own
    URL is how the full text is obtained, which is what the /apply workflow does
    anyway with a posting URL the user supplied.
    """
    return {}


# ---------------- freehire ----------------

def freehire_search(query: str, region: str = "us", days: int = 14,
                    limit: int = 20, with_description: bool = False) -> list[dict]:
    args = [BUN, "run", f"{PORTAL_DIR}/freehire-search/cli/src/cli.ts", "search",
            "--region", region, "--format", "json", "--limit", str(limit)]
    if query:
        args += ["--query", query]
    if days:
        args += ["--jobage", str(days)]
    if not with_description:
        args += ["--no-description"]
    data = _run(args)
    out = []
    for j in data.get("results", []):
        if not _within_days(j.get("date"), days):
            continue
        desc = j.get("description")
        lo, hi = extract_salary(desc)
        out.append({
            "portal": "freehire", "job_id": j.get("id"),
            "url": (j.get("url") or "").split("?")[0],
            "title": j.get("title"), "company": j.get("company"),
            "location": j.get("location"), "posted_date": j.get("date"),
            "work_mode": j.get("work_mode"), "skills": j.get("skills"),
            "description": desc, "salary_min": lo, "salary_max": hi,
        })
    return out


def freehire_detail(slug: str) -> dict:
    data = _run([BUN, "run", f"{PORTAL_DIR}/freehire-search/cli/src/cli.ts",
                 "detail", slug, "--format", "json"])
    return {
        "description": data.get("description"),
        "work_mode": data.get("work_mode"),
        "skills": data.get("skills"),
        "seniority": data.get("seniority"),
    }


PORTALS = {"adzuna": (adzuna_search, adzuna_detail),
           "freehire": (freehire_search, freehire_detail)}
