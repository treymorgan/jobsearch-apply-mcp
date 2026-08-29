"""SQLite state for the job search MCP server.

Owns the two pieces of state that used to live as files on the laptop:
seen jobs (the scrape/rank pipeline) and applications (the tracker). The
server is the source of truth for both so a phone and a laptop cannot
disagree about what has already been seen or applied to.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date
from pathlib import Path

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    url             TEXT PRIMARY KEY,
    job_id          TEXT,
    portal          TEXT NOT NULL,
    title           TEXT NOT NULL,
    company         TEXT,
    location        TEXT,
    posted_date     TEXT,
    first_seen      TEXT NOT NULL,
    remote_status   TEXT,
    salary_min      INTEGER,
    salary_max      INTEGER,
    deadline        TEXT,
    fit             TEXT,
    status          TEXT NOT NULL DEFAULT 'new',
    rank_score      INTEGER,
    rank_verdict    TEXT,
    rank_date       TEXT,
    location_verdict TEXT,
    strengths       TEXT,
    gaps            TEXT,
    description     TEXT,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_fit    ON jobs(fit);

CREATE TABLE IF NOT EXISTS profile_revisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    section     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    action      TEXT NOT NULL,
    source      TEXT,
    note        TEXT,
    bytes_before INTEGER,
    bytes_after  INTEGER,
    backup_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_rev_section ON profile_revisions(section);

CREATE TABLE IF NOT EXISTS applications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    company     TEXT NOT NULL,
    role        TEXT NOT NULL,
    sector      TEXT,
    role_type   TEXT,
    channel     TEXT,
    status      TEXT NOT NULL DEFAULT 'drafted',
    contact_person TEXT,
    fit_rating  INTEGER,
    notes       TEXT,
    cv_file     TEXT,
    cover_letter_file TEXT,
    source      TEXT,
    deadline    TEXT,
    UNIQUE(company, role)
);
"""

FINAL_STATUSES = {"hired", "rejected", "no_response", "offer_declined", "withdrawn"}


class Store:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            # WAL: readers do not block the writer and vice versa. With Grok and
            # Copilot CLI both connected, the default rollback journal serialises
            # them and a long search_jobs write would block every read.
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA busy_timeout=10000")
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        with _LOCK:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=10000")
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    # ---------- jobs ----------

    def upsert_jobs(self, jobs: list[dict]) -> dict:
        """Insert new jobs, skip ones already seen. Returns counts.

        Deduplication is by URL. An already-seen job is never overwritten -
        that would clobber a rank score or a status the user set.
        """
        today = date.today().isoformat()
        added = skipped = 0
        with self._conn() as c:
            for j in jobs:
                url = (j.get("url") or "").split("?")[0]
                if not url:
                    continue
                exists = c.execute("SELECT 1 FROM jobs WHERE url=?", (url,)).fetchone()
                if exists:
                    skipped += 1
                    continue
                c.execute(
                    """INSERT INTO jobs (url, job_id, portal, title, company, location,
                       posted_date, first_seen, remote_status, salary_min, salary_max,
                       fit, status, description)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (url, j.get("job_id"), j.get("portal", "unknown"), j.get("title", "?"),
                     j.get("company"), j.get("location"), j.get("posted_date"), today,
                     j.get("remote_status"), j.get("salary_min"), j.get("salary_max"),
                     j.get("fit"), j.get("status", "new"), j.get("description")),
                )
                added += 1
        return {"added": added, "already_seen": skipped}

    def list_jobs(self, status=None, fit=None, company=None, min_score=None,
                  search=None, limit=50) -> list[dict]:
        q = "SELECT * FROM jobs WHERE 1=1"
        p: list = []
        if status:
            q += " AND status=?"; p.append(status)
        if fit:
            q += " AND fit=?"; p.append(fit)
        if company:
            q += " AND company LIKE ?"; p.append(f"%{company}%")
        if min_score is not None:
            q += " AND rank_score >= ?"; p.append(min_score)
        if search:
            q += " AND (title LIKE ? OR company LIKE ?)"; p += [f"%{search}%", f"%{search}%"]
        q += " ORDER BY COALESCE(rank_score,-1) DESC, first_seen DESC LIMIT ?"
        p.append(limit)
        with self._conn() as c:
            return [dict(r) for r in c.execute(q, p).fetchall()]

    def get_job(self, url: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM jobs WHERE url=? OR job_id=?", (url, url)).fetchone()
            return dict(r) if r else None

    def update_job(self, url: str, **fields) -> bool:
        allowed = {"fit", "status", "rank_score", "rank_verdict", "rank_date",
                   "location_verdict", "strengths", "gaps", "notes", "deadline",
                   "remote_status", "salary_min", "salary_max", "description"}
        sets, vals = [], []
        for k, v in fields.items():
            if k in allowed and v is not None:
                if k in ("strengths", "gaps") and isinstance(v, list):
                    v = json.dumps(v)
                sets.append(f"{k}=?"); vals.append(v)
        if not sets:
            return False
        vals += [url, url]
        with self._conn() as c:
            cur = c.execute(
                f"UPDATE jobs SET {','.join(sets)} WHERE url=? OR job_id=?", vals)
            return cur.rowcount > 0

    def known_urls(self) -> set[str]:
        with self._conn() as c:
            return {r[0] for r in c.execute("SELECT url FROM jobs").fetchall()}

    def stats(self) -> dict:
        with self._conn() as c:
            rows = c.execute(
                "SELECT status, COUNT(*) n FROM jobs GROUP BY status").fetchall()
            fits = c.execute(
                "SELECT fit, COUNT(*) n FROM jobs WHERE fit IS NOT NULL GROUP BY fit").fetchall()
            apps = c.execute(
                "SELECT status, COUNT(*) n FROM applications GROUP BY status").fetchall()
        return {
            "jobs_by_status": {r["status"]: r["n"] for r in rows},
            "jobs_by_fit": {r["fit"]: r["n"] for r in fits},
            "applications_by_status": {r["status"]: r["n"] for r in apps},
        }

    # ---------- applications ----------

    def list_applications(self, status=None, open_only=False) -> list[dict]:
        q, p = "SELECT * FROM applications WHERE 1=1", []
        if status:
            q += " AND status=?"; p.append(status)
        if open_only:
            marks = ",".join("?" * len(FINAL_STATUSES))
            q += f" AND status NOT IN ({marks})"
            p += sorted(FINAL_STATUSES)
        q += " ORDER BY date DESC"
        with self._conn() as c:
            return [dict(r) for r in c.execute(q, p).fetchall()]

    def upsert_application(self, company: str, role: str, **f) -> dict:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM applications WHERE lower(company)=lower(?) AND lower(role)=lower(?)",
                (company, role)).fetchone()
            if row and row["status"] not in FINAL_STATUSES:
                sets, vals = [], []
                for k, v in f.items():
                    if v is not None and k in {
                        "sector", "role_type", "channel", "status", "contact_person",
                        "fit_rating", "notes", "cv_file", "cover_letter_file",
                        "source", "deadline", "date"}:
                        sets.append(f"{k}=?"); vals.append(v)
                if sets:
                    vals.append(row["id"])
                    c.execute(f"UPDATE applications SET {','.join(sets)} WHERE id=?", vals)
                return {"action": "updated", "id": row["id"]}
            cur = c.execute(
                """INSERT INTO applications (date, company, role, sector, role_type, channel,
                   status, contact_person, fit_rating, notes, cv_file, cover_letter_file,
                   source, deadline) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (f.get("date") or date.today().isoformat(), company, role, f.get("sector"),
                 f.get("role_type"), f.get("channel"), f.get("status", "drafted"),
                 f.get("contact_person"), f.get("fit_rating"), f.get("notes"),
                 f.get("cv_file"), f.get("cover_letter_file"), f.get("source"),
                 f.get("deadline")))
            return {"action": "created", "id": cur.lastrowid}

    def applied_pairs(self) -> set[tuple[str, str]]:
        with self._conn() as c:
            return {(r["company"].lower(), r["role"].lower())
                    for r in c.execute("SELECT company, role FROM applications").fetchall()}

    # ---------- profile revisions ----------

    def add_revision(self, section: str, action: str, source: str | None,
                     note: str | None, bytes_before: int, bytes_after: int,
                     backup_path: str | None) -> int:
        from datetime import datetime
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO profile_revisions
                   (section, created_at, action, source, note,
                    bytes_before, bytes_after, backup_path)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (section, datetime.now().isoformat(timespec="seconds"), action,
                 source, note, bytes_before, bytes_after, backup_path))
            return cur.lastrowid

    def list_revisions(self, section: str | None = None, limit: int = 30) -> list[dict]:
        q = "SELECT * FROM profile_revisions WHERE 1=1"
        p: list = []
        if section:
            q += " AND section=?"; p.append(section)
        q += " ORDER BY id DESC LIMIT ?"; p.append(limit)
        with self._conn() as c:
            return [dict(r) for r in c.execute(q, p).fetchall()]

    def get_revision(self, rev_id: int) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM profile_revisions WHERE id=?", (rev_id,)).fetchone()
            return dict(r) if r else None
