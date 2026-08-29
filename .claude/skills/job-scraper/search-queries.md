# Search Queries for Job Scraper

<!-- SETUP: Customize these queries based on your skills, target roles, and location -->

## Purpose

This file is a guide for choosing search queries. The active query list belongs in `jobsearch.config.json`, under `search.queries`. The `/setup` workflow should help the user fill that config from their own profile and market.

Do not hardcode a user's private job-search goals here. Keep this file reusable, public, and neutral.

## Installed portal CLIs, primary for `/scrape`

`/scrape` discovers every portal skill under `.agents/skills/*/SKILL.md` and runs its CLI first. The shipped CLI is `freehire-search`; any skill you add with `/add-portal` is included the same way. You do **not** need a matching `site:` line below for those CLIs to run.

The `site:` query templates in this file are the **WebSearch fallback**: for portals without a CLI, company career pages, or when a CLI fails.

## Market Scope

The market scope comes from `jobsearch.config.json`:

- `search.remote_location`, `search.remote_filter`, and `search.remote_region` define the remote lane.
- `search.local_location` and `search.local_metro` define an optional local lane for onsite or hybrid roles in a commutable area.
- An empty `search.local_metro` means remote-only.
- `deal_breakers.require_remote` and salary settings are applied by the server and evaluation workflow, not by hardcoded text in this guide.

When a portal supports location and workplace filters, run configured queries once through the remote lane and, if configured, once through the local lane. For WebSearch fallback queries, combine the user's query with the configured remote location or local place names.

Portal remote filters are only a first-pass scope. Always verify workplace type and geographic restrictions from detail text before presenting a posting as in-scope.

## Search Sites

Primary:
- Installed portal CLIs under `.agents/skills/`, especially broad aggregators and any market-specific portals added with `/add-portal`.

Fallback:
- `site:` searches for portals without a CLI.
- Employer career-site searches when a search result points to a listing page instead of a specific posting.
- General WebSearch only when no structured portal result is available.

## Query Strategy

### Organize by function, not just title

The same underlying work carries different titles across employers. Group related work into priority tiers by function, then list several plausible title variants inside each tier.

Example, using neutral placeholders:

```text
Priority 1: <primary target function>
- "<your target title>"
- "<senior variant of your target title>"
- "<management or lead variant, if relevant>"

Priority 2: <adjacent target function>
- "<adjacent title>"
- "<alternate market title>"
- "<specialist variant>"

Priority 3: <broader fallback function>
- "project manager"  # sample only, replace with your own title
- "operations manager"  # sample only, replace with your own title
- "business analyst"  # sample only, replace with your own title
```

### Prefer distinctive terms

Good queries use terms that appear in real postings and separate signal from noise. Distinctive terms might include:

- A role title or title fragment.
- A domain noun from the user's profile.
- A required tool, platform, method, license, or certification.
- A seniority marker, only if that seniority is truly desired.
- A business function or industry term, when the user wants that industry.

Avoid queries that are so broad they return unrelated work. Avoid queries that are so narrow they only match one employer's wording.

### Use exact phrases carefully

Quoted phrases are useful for title searches, but too many quotes can hide relevant postings. Start with one exact phrase plus one broad keyword. Add more quoted variants only when results are noisy.

Examples:

```text
site:<job-board-domain> "<your job title>" remote "<remote location>"
site:<job-board-domain> "project manager" "<industry keyword>" "<remote location>"  # sample only
site:<portal-domain>/jobs "<your distinctive keyword>" "<local place name>"
```

### Add fallback `site:` templates

Use `site:` fallback queries when a portal has no CLI or when a CLI fails. Keep them generic and easy to adapt:

```text
site:<job-board-domain>/jobs "<your job title>" "<remote location>"
site:<job-board-domain>/jobs "<your distinctive keyword>" remote
site:<company-careers-domain> "<your job title>" "jobs"
site:<company-careers-domain> "<your distinctive keyword>" "careers"
```

Do not list private target employers in this public guide. Put user-specific companies, if any, in the user's private config or notes.

## Placeholder Query List

Fill this section through `/setup`, then copy the final active terms into `jobsearch.config.json` under `search.queries`.

```json
{
  "search": {
    "queries": [
      "<primary target title>",
      "<alternate target title>",
      "<adjacent target title>"
    ]
  }
}
```

Suggested structure for the user's private query notes:

```text
Priority 1: <best-fit function>
- <query 1>
- <query 2>
- <query 3>

Priority 2: <adjacent function>
- <query 4>
- <query 5>

Priority 3: <broader fallback function>
- <query 6>
- <query 7>
```

## Location Filter

Use `jobsearch.config.json` as the source of truth:

- Remote lane: accept postings that are genuinely remote and include the configured `search.remote_location` or `search.remote_region`.
- Local lane: if `search.local_metro` is non-empty, accept onsite or hybrid postings whose detail location is inside that configured list.
- Empty local lane: treat onsite and hybrid postings as out of scope unless the user changes the config.
- Restricted remote postings: exclude or flag postings whose allowed regions do not include the configured remote market.
- Unconfirmed remote status: flag clearly instead of assuming.

## Language Filter

Working languages and levels are in CLAUDE.md's Languages table. When filtering scraped results, apply `04-job-evaluation.md`'s Language Gate: a posting requiring a language the user has not declared at all is excluded; a posting requiring a higher level than declared is not excluded, but it must be flagged clearly. Postings simply written in a language the user does not work in, with no on-the-job language requirement, are acceptable if the user can evaluate them safely.

## Date Filter

Only include jobs posted within the configured recency window, or with an application deadline that has not yet passed. If a posting date cannot be determined, include it but flag as "date unknown".

## Adapting Queries

If the user specifies a focus area, select configured queries from the matching category and generate 2-3 custom variants for that focus. For example:

- `/scrape <focus area>` -> relevant configured queries plus custom focus-specific queries.
- `/scrape broad` -> all configured tiers, plus safe fallback templates when useful.
- `/scrape health` -> no query expansion, only portal health checks.
