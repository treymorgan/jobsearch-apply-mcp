"""User configuration for the job search server.

Everything that describes *a particular job search* lives here rather than in
the code: which search terms to run, which cities count as commutable, what
salary is too low to bother with, which titles are noise. The code ships with
neutral defaults that filter nothing and veto nothing, so an unconfigured
server is useless-but-harmless rather than silently applying someone else's
preferences.

Resolution order, first hit wins:

1. ``JOBSEARCH_CONFIG`` - explicit path to a JSON file.
2. ``jobsearch.config.json`` in the current working directory.
3. ``jobsearch.config.json`` at the workspace root (see ``paths.py``).
4. ``/config/jobsearch.config.json`` - the container mount point.
5. Built-in neutral defaults.

Start from ``jobsearch.config.example.json`` in the repository root.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import workspace_root

log = logging.getLogger("jobsearch-mcp.config")

CONFIG_FILENAME = "jobsearch.config.json"

# Title tokens that imply scope over people or direction, used only when the
# user turns the individual-contributor flag on. Kept in code rather than in
# the config file because they are English job-title grammar, not a preference.
DEFAULT_LEADERSHIP_TERMS = [
    "director", "manager", "head of", "vp", "vice president", "chief",
    "lead", "leader", "principal", "staff", "distinguished", "fellow",
    "owner", "supervisor",
]
DEFAULT_IC_TERMS = [
    "architect", "engineer", "analyst", "specialist", "consultant",
    "developer", "scientist", "administrator", "technician", "designer",
    "writer", "coordinator",
]


def _compile_any(terms: list[str]) -> re.Pattern | None:
    """One case-insensitive alternation over whole words. None when empty.

    A None pattern is the "no opinion" signal every caller checks for. Building
    an empty alternation instead would produce a regex that matches the empty
    string everywhere, so every title would look like a hit.
    """
    cleaned = [t.strip() for t in terms if t and t.strip()]
    if not cleaned:
        return None
    # Terms are treated as literals, not regexes: a user writing "C++" or
    # "node.js" in their config should not have it silently reinterpreted.
    parts = []
    for t in cleaned:
        esc = re.escape(t.lower())
        # Word boundaries only where the term actually starts/ends with a word
        # character, otherwise "\bC++\b" never matches.
        lead = r"\b" if t[0].isalnum() else ""
        tail = r"\b" if t[-1].isalnum() else ""
        parts.append(f"{lead}{esc}{tail}")
    return re.compile("|".join(parts), re.I)


@dataclass
class SearchConfig:
    queries: list[str] = field(default_factory=list)
    remote_location: str = "United States"
    remote_filter: str = "remote"
    remote_region: str = "us"
    local_location: str = ""
    local_metro: list[str] = field(default_factory=list)
    default_days: int = 14
    default_limit: int = 20

    @property
    def has_local_lane(self) -> bool:
        return bool(self.local_location or self.local_metro)


@dataclass
class FilterConfig:
    relevance_terms: list[str] = field(default_factory=list)
    exclude_terms: list[str] = field(default_factory=list)
    exclude_override_terms: list[str] = field(default_factory=list)
    flag_individual_contributor: bool = False
    leadership_terms: list[str] = field(default_factory=lambda: list(DEFAULT_LEADERSHIP_TERMS))
    ic_terms: list[str] = field(default_factory=lambda: list(DEFAULT_IC_TERMS))


@dataclass
class DealBreakerConfig:
    salary_floor: int = 0
    currency: str = "USD"
    currency_symbol: str = "$"
    require_remote: bool = True


@dataclass
class Config:
    search: SearchConfig = field(default_factory=SearchConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    deal_breakers: DealBreakerConfig = field(default_factory=DealBreakerConfig)
    source_path: str | None = None

    # Compiled once at load; None means "no opinion, do not filter".
    def __post_init__(self):
        self.relevance_re = _compile_any(self.filters.relevance_terms)
        self.exclude_re = _compile_any(self.filters.exclude_terms)
        self.exclude_override_re = _compile_any(self.filters.exclude_override_terms)
        self.leadership_re = _compile_any(self.filters.leadership_terms)
        self.ic_re = _compile_any(self.filters.ic_terms)
        self.local_metro_re = _compile_any(self.search.local_metro)

    # ---------------- derived helpers ----------------

    def is_relevant(self, title: str | None) -> bool:
        """Should this title be shown, or is it noise from a broad query?

        With no filters configured everything is relevant - the safe default,
        because silently hiding a real match is worse than showing noise.
        """
        t = title or ""
        if self.exclude_re and self.exclude_re.search(t):
            # An override term rescues a title the exclude list would drop,
            # e.g. excluding "finance" but keeping "Cloud Finance Manager".
            return bool(self.exclude_override_re and self.exclude_override_re.search(t))
        if self.relevance_re is None:
            return True
        return bool(self.relevance_re.search(t))

    def is_ic_only(self, title: str | None) -> bool:
        """True when a title reads as individual contributor with no scope.

        Off unless the user opts in: most people are not filtering for
        leadership, and flagging every engineer role would be noise.
        """
        if not self.filters.flag_individual_contributor:
            return False
        t = title or ""
        if self.leadership_re and self.leadership_re.search(t):
            return False
        return bool(self.ic_re and self.ic_re.search(t))

    def is_local(self, location: str | None) -> bool:
        if not location or self.local_metro_re is None:
            return False
        return bool(self.local_metro_re.search(location))

    def money(self, amount: int) -> str:
        return f"{self.deal_breakers.currency_symbol}{amount:,}"


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def _candidate_paths() -> list[Path]:
    paths = []
    explicit = os.environ.get("JOBSEARCH_CONFIG")
    if explicit:
        paths.append(Path(explicit).expanduser())
    paths.append(Path.cwd() / CONFIG_FILENAME)
    paths.append(workspace_root() / CONFIG_FILENAME)
    paths.append(Path("/config") / CONFIG_FILENAME)
    return paths


def _subset(cls, data: dict):
    """Build a dataclass from a dict, ignoring keys it does not define.

    Unknown keys are warned about rather than raised on: a typo in a hand-edited
    config should not take the whole server down, but it must not be silent
    either or the user will believe a setting is active when it is not.
    """
    known = {f.name for f in cls.__dataclass_fields__.values()}
    # Keys beginning with "_" are documentation comments in the example file.
    # JSON has no comment syntax, so this is the convention that lets the
    # shipped example explain itself without tripping the unknown-key warning.
    data = {k: v for k, v in data.items() if not k.startswith("_")}
    unknown = set(data) - known
    if unknown:
        log.warning("ignoring unknown %s keys: %s", cls.__name__, ", ".join(sorted(unknown)))
    return cls(**{k: v for k, v in data.items() if k in known})


def load(path: str | os.PathLike | None = None) -> Config:
    """Load configuration, falling back to neutral defaults."""
    paths = [Path(path).expanduser()] if path else _candidate_paths()
    for p in paths:
        try:
            if not p.is_file():
                continue
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # A malformed config is a real error worth shouting about, but
            # falling back keeps the server answering health checks so the
            # user can see the message.
            log.error("could not read config at %s: %s", p, exc)
            continue
        cfg = Config(
            search=_subset(SearchConfig, raw.get("search", {})),
            filters=_subset(FilterConfig, raw.get("filters", {})),
            deal_breakers=_subset(DealBreakerConfig, raw.get("deal_breakers", {})),
            source_path=str(p),
        )
        log.info("loaded config from %s", p)
        return cfg
    log.warning(
        "no %s found - using neutral defaults (no search terms, no filters, "
        "no salary floor). Copy jobsearch.config.example.json to get started.",
        CONFIG_FILENAME)
    return Config()


_active: Config | None = None


def get() -> Config:
    """Process-wide configuration singleton."""
    global _active
    if _active is None:
        _active = load()
    return _active


def reload(path: str | os.PathLike | None = None) -> Config:
    global _active
    _active = load(path)
    return _active
