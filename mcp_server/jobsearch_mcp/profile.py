"""Candidate profile access.

The profile markdown files are the same ones the local agent workflows treat as
the source of truth for facts. The server reads them so a phone or a chat client
can answer "who am I / what have I done" without the repo checked out.

The server is the **source of truth** for these files when it is hosted: an edit
made from a phone must not be silently destroyed by the next code deploy, so
`deploy.sh` pulls rather than pushes by default.

Writes are deliberately shaped so the safe operation is the easy one. Appending
a fact cannot destroy anything; replacing a whole section snapshots the previous
version first and is reversible. That matters because this file set is the
grounding source for CV drafting: a fabricated claim written here would be
treated as fact by every future draft.

Reads and writes use different directories on purpose. The shipped
`.claude/skills/job-application-assistant/` files are blank *templates* tracked
in git. The user's real, populated profile lives in `profile/` at the workspace
root, which is gitignored, so forking this project cannot leak a name,
employment history or salary expectation. Reads fall back to the templates when
`profile/` is empty; writes never touch them.
"""
from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from . import config
from .paths import workspace_root

TEMPLATE_DIR = workspace_root() / ".claude" / "skills" / "job-application-assistant"

# Filenames the profile is made of. Defined before profile_dir()
# because that function looks for them on disk.
FILES = {
    "candidate": "01-candidate-profile.md",
    "behavioral": "02-behavioral-profile.md",
    "writing_style": "03-writing-style.md",
    "evaluation": "04-job-evaluation.md",
    "cv_templates": "05-cv-templates.md",
    "interview": "07-interview-prep.md",
    "star_examples": "StarExamples.md",
    "overview": "CLAUDE.md",
}


def _write_dir() -> Path:
    """Where the user's real profile is written.

    Never the tracked template directory: writes must not be able to land in
    files that git is watching, or a fork would publish them.
    """
    explicit = os.environ.get("PROFILE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    return workspace_root() / "profile"


def profile_dir() -> Path:
    """Where profile reads come from, resolved on **every** call.

    Deliberately a function, not a module constant. `/setup` populates
    `profile/` while the server is already running, and a value captured at
    import would keep serving the blank template for the rest of the session:
    the user would finish onboarding and then have every CV silently drafted
    from an empty profile, with nothing to indicate why. Resolving per call
    costs one `is_file()` check and removes the need to restart after setup.
    """
    explicit = os.environ.get("PROFILE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    user_dir = workspace_root() / "profile"
    if any((user_dir / name).is_file() for name in FILES.values()):
        return user_dir
    return TEMPLATE_DIR


def using_templates() -> bool:
    """True when no populated profile exists yet, so reads fall back to blanks.

    Callers surface this rather than letting a blank profile look like a real
    but empty one.
    """
    return profile_dir() == TEMPLATE_DIR


# Backwards-compatible module attributes. Resolved through a module __getattr__
# so anything still reading `profile.PROFILE_DIR` gets a live answer instead of
# an import-time snapshot.
def __getattr__(name: str):
    if name == "PROFILE_DIR":
        return profile_dir()
    if name == "PROFILE_WRITE_DIR":
        return _write_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


BACKUP_DIR = Path(os.environ.get(
    "PROFILE_BACKUPS",
    str(Path(os.environ.get("JOBSEARCH_STATE_DIR", ".")) / "profile_revisions")))

MANAGED_HEADING = "## Added via MCP"


def _read(name: str) -> str:
    p = profile_dir() / name
    if not p.is_file():
        return f"[missing: {name}]"
    return p.read_text(encoding="utf-8")


def get_section(section: str = "candidate") -> str:
    if section not in FILES:
        return (f"Unknown section '{section}'. Available: {', '.join(sorted(FILES))}")
    return _read(FILES[section])


def list_sections() -> list[str]:
    return sorted(FILES)


def search_profile(query: str, context: int = 300) -> list[dict]:
    """Grep the profile files. Cheaper than shipping whole documents to the model."""
    hits = []
    needle = query.lower()
    for key, fname in FILES.items():
        text = _read(fname)
        low = text.lower()
        start = 0
        while (i := low.find(needle, start)) != -1:
            a, b = max(0, i - context // 2), min(len(text), i + context)
            hits.append({"section": key, "excerpt": text[a:b].strip()})
            start = i + len(needle)
            if len(hits) >= 25:
                return hits
    return hits


def star_examples(competency: str | None = None) -> list[dict]:
    """Split StarExamples.md into its numbered competency blocks."""
    text = _read(FILES["star_examples"])
    blocks, current = [], None
    for line in text.splitlines():
        # Competency headings are the only UNINDENTED numbered lines. The file
        # nests numbered scenarios and lettered S/T/A/R steps beneath them, so
        # stripping before matching would start a new block on every scenario
        # and leave every competency with empty content.
        m = re.match(r"^(\d+)\.\s+(.+)$", line)
        if m:
            if current:
                blocks.append(current)
            current = {"competency": m.group(2).strip(), "content": ""}
        elif current is not None:
            current["content"] += line + "\n"
    if current:
        blocks.append(current)
    if competency:
        c = competency.lower()
        blocks = [b for b in blocks if c in b["competency"].lower()
                  or c in b["content"].lower()]
    return blocks


def check_deal_breakers(location: str | None = None, remote_status: str | None = None,
                        salary_min: int | None = None,
                        salary_max: int | None = None) -> dict:
    """Deterministic pass/fail against the hard constraints in your config.

    Deliberately a function, not a prompt: these are the rules that should never
    drift between a phone session and a laptop session. Both checks are opt-in -
    an unconfigured server reports FLAG ("no rule set") rather than inventing a
    veto on the user's behalf.
    """
    cfg = config.get()
    db = cfg.deal_breakers
    verdicts: list[tuple[str, str, str]] = []

    # ---- location ----
    if cfg.is_local(location) or remote_status == "local":
        verdicts.append(("location", "PASS",
                         "inside your commutable area - onsite or hybrid both acceptable"))
    elif not db.require_remote:
        verdicts.append(("location", "PASS", "no location rule configured"))
    elif remote_status == "remote-confirmed":
        verdicts.append(("location", "PASS", "remote confirmed in the posting text"))
    elif remote_status == "onsite-or-hybrid":
        verdicts.append(("location", "FAIL",
                         "posting states onsite or hybrid and the site is outside "
                         "your commutable area"))
    else:
        verdicts.append(("location", "FLAG",
                         "remote status not stated in the posting - verify before applying"))

    # ---- salary ----
    # Judged on the TOP of the band, because that is what is negotiable. A band
    # whose ceiling is under the floor cannot be negotiated into range.
    floor = db.salary_floor
    if not floor:
        verdicts.append(("salary", "PASS", "no salary floor configured"))
    elif salary_max is not None:
        if salary_max < floor:
            verdicts.append(("salary", "FAIL",
                             f"band tops out at {cfg.money(salary_max)}, below your "
                             f"{cfg.money(floor)} floor"))
        elif salary_min is not None and salary_min < floor <= salary_max:
            verdicts.append(("salary", "FLAG",
                             f"band {cfg.money(salary_min)}-{cfg.money(salary_max)} "
                             f"straddles your {cfg.money(floor)} floor - negotiable, "
                             "not automatic"))
        else:
            verdicts.append(("salary", "PASS", f"band clears {cfg.money(floor)}"))
    else:
        verdicts.append(("salary", "FLAG", "no salary stated in the posting"))

    overall = "FAIL" if any(v[1] == "FAIL" for v in verdicts) else \
              "FLAG" if any(v[1] == "FLAG" for v in verdicts) else "PASS"
    reasons = [f"{n}: {v} - {w}" for n, v, w in verdicts]
    return {"verdict": overall, "checks": [
        {"rule": n, "verdict": v, "reason": w} for n, v, w in verdicts],
        "summary": "; ".join(reasons)}


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------

def _path(section: str) -> Path:
    if section not in FILES:
        raise ValueError(
            f"Unknown section '{section}'. Available: {', '.join(sorted(FILES))}")
    # Seed from the template on first write so the user starts from the
    # structure rather than an empty file.
    target = _write_dir() / FILES[section]
    if not target.is_file():
        template = TEMPLATE_DIR / FILES[section]
        if template.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template, target)
    return target


def _backup(section: str, path: Path) -> tuple[str | None, int]:
    """Snapshot the current file before a destructive write.

    The filename must be unique. A second-granular timestamp is not: a replace
    followed immediately by a restore collided on the same name, so the restore's
    own safety snapshot overwrote the very revision it was about to read, and the
    rollback silently returned the corrupted content. Microseconds plus an
    explicit never-clobber loop close that.
    """
    if not path.is_file():
        return None, 0
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
    dest = BACKUP_DIR / f"{section}.{stamp}.md"
    n = 0
    while dest.exists():
        n += 1
        dest = BACKUP_DIR / f"{section}.{stamp}.{n}.md"
    shutil.copy2(path, dest)
    return str(dest), path.stat().st_size


def append_fact(section: str, text: str, source: str | None = None) -> dict:
    """Append a dated, attributed fact. Never destroys existing content."""
    path = _path(section)
    before = path.stat().st_size if path.is_file() else 0
    body = path.read_text(encoding="utf-8") if path.is_file() else ""

    stamp = datetime.now().strftime("%Y-%m-%d")
    attribution = f" (source: {source})" if source else ""
    entry = f"- {text.strip()}  \n  *added {stamp} via MCP{attribution}*\n"

    if MANAGED_HEADING in body:
        body = body.rstrip() + "\n" + entry
    else:
        body = body.rstrip() + f"\n\n{MANAGED_HEADING}\n\n" + entry
    path.write_text(body, encoding="utf-8")
    return {"section": section, "action": "append", "bytes_before": before,
            "bytes_after": path.stat().st_size, "entry": entry.strip()}


def replace_section(section: str, content: str) -> dict:
    """Replace a whole profile document, snapshotting the previous version."""
    path = _path(section)
    backup, before = _backup(section, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return {"section": section, "action": "replace", "bytes_before": before,
            "bytes_after": path.stat().st_size, "backup_path": backup}


def restore(section: str, backup_path: str) -> dict:
    """Restore a snapshot, snapshotting the current version first."""
    src = Path(backup_path)
    if not src.is_file():
        raise FileNotFoundError(f"revision file missing: {backup_path}")
    # Read the revision into memory BEFORE writing anything. Even if a future
    # naming change reintroduced a collision, the content to restore is already
    # held and cannot be clobbered by our own safety snapshot.
    payload = src.read_bytes()
    path = _path(section)
    new_backup, before = _backup(section, path)
    path.write_bytes(payload)
    return {"section": section, "action": "restore", "bytes_before": before,
            "bytes_after": path.stat().st_size, "backup_path": new_backup,
            "restored_from": backup_path}


def diff_against(section: str, backup_path: str) -> str:
    """Unified diff between a stored revision and the current file."""
    import difflib
    old = Path(backup_path)
    if not old.is_file():
        return f"[revision file missing: {backup_path}]"
    cur = _path(section)
    a = old.read_text(encoding="utf-8").splitlines(keepends=True)
    b = cur.read_text(encoding="utf-8").splitlines(keepends=True) if cur.is_file() else []
    return "".join(difflib.unified_diff(a, b, fromfile="revision",
                                        tofile="current", n=2))[:6000]
