# MCP tools reference

These are the tools your AI assistant can call. You do not need to memorise
them: ask for what you want in plain language and the assistant picks the right
one. This page is for when you want to know exactly what happened, or to ask
for something specific.

Start with **`config_status`** whenever results look wrong.

---

## Finding jobs

### `search_jobs`
Searches job boards and stores everything new.

| Argument | Default | Meaning |
|---|---|---|
| `query` | your configured terms | A single search term. |
| `lane` | `both` | `remote`, `local`, or `both`. The local lane is skipped when no commutable area is configured. |
| `days` | from config | How far back to look. |
| `limit` | from config | Results per term. |
| `portal` | auto | Which board to search. Empty picks Adzuna when a key is configured, otherwise freehire. |
| `all_results` | `false` | Include postings hidden by your filters. |

Postings already seen on a previous run are counted but not returned again, so
running it daily shows you only what is new.

**Remote status is not resolved here.** Search results carry no reliable
work-arrangement field, so anything promising needs `job_detail`.

### `job_detail`
Fetches a posting's full text, works out whether it is genuinely remote, pulls
out any salary band, and runs the deal-breaker check. Results are saved back to
the stored job, so this is how a posting earns a trustworthy remote status.

Takes a stored URL or a job id.

### `ingest_jobs`
Adds postings you found some other way. Useful when portal search is
unavailable, or when another tool hands you a batch. Deduplicated against
everything already stored, so re-adding the same batch is safe.

Each item needs at least a `url` and a `title`.

### `list_jobs`
Queries what is already stored, by status, fit, company, minimum score or free
text. Use this rather than searching again.

### `update_job`
Records your decision about a job: fit, status, score, verdict, notes,
deadline.

### `job_stats`
Counts across the pipeline: jobs by status and fit, applications by status.

---

## Tracking applications

### `list_applications`
Lists tracked applications. `open_only` hides resolved ones.

### `record_application`
Creates or advances an application record.

An existing **open** application for the same company and role is updated. One
that already reached a final status is left alone and a new row is created
instead, so re-applying somewhere never overwrites an earlier outcome.

---

## Your profile

These read and write the markdown files in
`.claude/skills/job-application-assistant/`. They are the grounding source for
CV drafting, which is why the write tools are shaped the way they are.

### `get_profile`
Reads one profile document. Sections: `candidate`, `behavioral`,
`writing_style`, `evaluation`, `cv_templates`, `interview`, `star_examples`,
`overview`.

### `search_profile`
Searches all the profile documents for a term and returns matching excerpts.
Cheaper than reading a whole document when you only need to check one fact.

### `get_star_examples`
Your interview stories, optionally filtered by competency or keyword.

### `add_profile_fact`
**Appends** a new fact. Dated and attributed. Cannot destroy anything.

This is the safe default and covers almost every real edit: a new
certification, a metric, a project, a corrected scope. Prefer it.

### `update_profile_section`
**Replaces** a whole document. Destructive but reversible: the previous version
is snapshotted first, and near-empty content is refused. Use it for a wholesale
refresh, such as importing a new resume.

### `list_profile_revisions` / `diff_profile_revision`
The edit history, and what changed in a given revision.

### `restore_profile_revision`
Rolls a document back to a snapshot. Only revisions created by
`update_profile_section` have one; appends destroyed nothing, so there is
nothing to roll back to.

> **Only record facts you have actually confirmed.** Anything written here is
> treated as true by every future CV draft. An invented metric becomes
> "grounded" permanently and will propagate silently.

---

## Checks

### `check_deal_breakers`
Tests a role against the hard limits in your config: location and salary floor.
Returns `PASS`, `FLAG` or `FAIL` with reasons.

Deliberately a function rather than a prompt rule, so the answer cannot drift
between one session and the next. Both checks are opt-in; with nothing
configured, nothing is vetoed.

### `config_status`
What the server is currently configured to do, and where its files are. The
first thing to check when something looks wrong.

### `health`
Liveness and dependency check.

---

## What these tools deliberately do not do

They own **data and state**. They do not draft.

Fit-evaluation prose, CV and cover letter writing, LaTeX compilation and PDF
inspection all stay in the local workflows described in
[WORKFLOWS.md](WORKFLOWS.md), because they need a model in the loop, your
document folder, and a look at a rendered page.

That split is why the server is useful from a phone while the serious writing
still happens at a desk.
