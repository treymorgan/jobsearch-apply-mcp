# Configuration

Everything about *your* job search lives in one file: `jobsearch.config.json`.
Nothing about it is baked into the code, and the shipped defaults filter
nothing and reject nothing.

Get started by copying the example:

```bash
cp jobsearch.config.example.json jobsearch.config.json
```

Then edit it in any text editor. **Every field is optional.** Anything you
leave out is simply not applied.

To see what the server actually loaded, ask your AI assistant to run the
`config_status` tool. That is the fastest way to check a change took effect.

---

## Where the file is looked for

First match wins:

1. The path in the `JOBSEARCH_CONFIG` environment variable
2. `jobsearch.config.json` in the folder you are working from
3. `jobsearch.config.json` at the root of this project
4. `/config/jobsearch.config.json` (used by the Docker setup)

If none exists the server starts with neutral defaults and says so in its log.

> JSON has no comments. Any key starting with `_` is ignored, which is how the
> example file explains itself. You can delete those lines or leave them.

---

## `search`

Controls what gets searched.

```json
"search": {
  "queries": ["product manager", "senior product manager"],
  "remote_location": "United States",
  "remote_filter": "remote",
  "remote_region": "us",
  "local_location": "Manchester, England, United Kingdom",
  "local_metro": ["manchester", "salford", "stockport"],
  "default_days": 14,
  "default_limit": 20
}
```

| Field | Meaning |
|---|---|
| `queries` | The searches run when you do not name one. Use the job titles that actually appear in postings you want, not your ideal title. |
| `remote_location` | The market for the remote lane, as the job board words it. `"United States"`, `"United Kingdom"`, `"Germany"`. |
| `remote_filter` | Passed to the board's remote filter. Usually `"remote"`. Set to `""` to skip it. |
| `remote_region` | Region code for boards that use one. Usually `"us"`, `"eu"` or `"uk"`. |
| `local_location` | Optional. A second search for roles you could commute to, worded as the job board expects. |
| `local_metro` | Optional. Town and city names that count as commutable. Lowercase, matched against the posting's location. |
| `default_days` | How far back to look, in days. |
| `default_limit` | Results per search term. |

### The two lanes

Searches run in up to two "lanes":

- **remote** searches `remote_location` with the remote filter on
- **local** searches `local_location`, and any hit inside `local_metro` is
  treated as acceptable regardless of whether it is onsite, hybrid or remote

Leave `local_metro` empty and the local lane is skipped entirely, which is what
you want if you are only interested in remote work.

The reason `local_metro` is a separate list from `local_location` is that job
boards word locations differently from the postings themselves. A board might
want `"Manchester, England, United Kingdom"` while postings say
`"Salford Quays"`. The list is what actually decides whether a role is
commutable.

---

## `filters`

Optional noise control. Broad searches return a lot of near-misses, and these
lists let you hide them. **Leave the lists empty and nothing is hidden.**

```json
"filters": {
  "relevance_terms": ["product", "program"],
  "exclude_terms": ["intern", "graduate"],
  "exclude_override_terms": [],
  "flag_individual_contributor": false
}
```

| Field | Meaning |
|---|---|
| `relevance_terms` | A title must contain at least one of these to be shown. Empty means show everything. |
| `exclude_terms` | A title containing any of these is hidden. |
| `exclude_override_terms` | Rescues a title the exclude list would have hidden. |
| `flag_individual_contributor` | Set `true` only if you specifically want roles with leadership scope. Adds a note to titles that read as individual-contributor. |

Nothing is ever deleted. Filtered postings are still stored, and asking for
`all_results` shows them. That is deliberate: a title-only filter cannot always
tell a real match from a near-miss, so hiding is reversible and discarding is
not.

`exclude_override_terms` exists for the common case where a word is usually
noise but not always. If you exclude `"finance"` but still want
`"Technical Finance Manager"`, put `"technical"` in the override list.

Terms are matched as plain text, case-insensitively, on whole words. They are
not regular expressions, so `C++` and `node.js` work as written.

---

## `deal_breakers`

Your hard limits. Checked by the `check_deal_breakers` tool, which returns a
deterministic `PASS`, `FLAG` or `FAIL` rather than asking the AI to re-read
your preferences every time.

```json
"deal_breakers": {
  "salary_floor": 65000,
  "currency": "GBP",
  "currency_symbol": "£",
  "require_remote": true
}
```

| Field | Meaning |
|---|---|
| `salary_floor` | Below this, a role fails. `0` disables the check. |
| `currency` / `currency_symbol` | Used for display only. |
| `require_remote` | When `true`, a role outside your commutable area must state that it is remote. Set `false` if you do not care where the job is. |

### How the checks behave

**Salary is judged on the top of the band**, because that is what is
negotiable. A band whose ceiling is under your floor cannot be negotiated into
range, so it fails. A band that straddles your floor is flagged, not failed.

**Location** passes automatically inside `local_metro`. Elsewhere the posting
text has to confirm remote work. When it says nothing either way the result is
`FLAG`, never a silent pass or a silent rejection, because guessing in either
direction loses you jobs or wastes your time.

Both checks are opt-in. With nothing configured, nothing is vetoed.

---

## Environment variables

You will rarely need these. They matter mostly for hosted setups.

| Variable | Default | Purpose |
|---|---|---|
| `JOBSEARCH_HOME` | auto-detected | Where this project lives. Set it when your AI app launches the server from a different folder. |
| `JOBSEARCH_CONFIG` | auto-detected | Full path to your config file. |
| `JOBSEARCH_STATE_DIR` | OS data folder | Where the database, audit log and profile snapshots go. |
| `JOBSEARCH_DB` | inside the state dir | Database file path. |
| `PROFILE_DIR` | `profile/` in the project, falling back to the blank templates in `.claude/skills/job-application-assistant` when it is empty | Your profile markdown. |
| `PORTAL_DIR` | `.agents/skills` | The portal search tools. |
| `BUN_PATH` | auto-detected | Full path to `bun`, if it is not on your PATH. |
| `ADZUNA_APP_ID` | unset | Adzuna API id. Free from [developer.adzuna.com/signup](https://developer.adzuna.com/signup). Without it, search falls back to technical roles only. |
| `ADZUNA_APP_KEY` | unset | Adzuna API key. |
| `PORTAL_MIN_INTERVAL` | `3.0` | Seconds between portal requests. Please do not lower this. |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http`. |
| `LOG_LEVEL` | `INFO` | Set to `DEBUG` when diagnosing a problem. |

Hosting and authentication variables are covered in
[HOSTING.md](HOSTING.md).

### Default state directory

| OS | Location |
|---|---|
| Windows | `%LOCALAPPDATA%\jobsearch-mcp` |
| macOS / Linux | `~/.local/share/jobsearch-mcp` |

---

## Your profile

The config file covers *what to search for*. Your background, experience and
interview stories live separately, as markdown in the `profile/` folder at the
top of the project.

The files under `.claude/skills/job-application-assistant/` are the blank
**templates** those are built from. They stay tracked in git; your populated
copies in `profile/` are gitignored.

The intended way to fill them in is to run the `/setup` workflow with your AI
assistant, which interviews you and writes the files. You can also edit them by
hand. See [WORKFLOWS.md](WORKFLOWS.md).

`profile/` is gitignored, so your details are never committed even if you fork
this project publicly.
