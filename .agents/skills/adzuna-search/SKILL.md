---
name: adzuna-search
version: 1.0.0
description: >
  Use this skill to search live job listings across any sector and 19 countries
  through Adzuna's official jobs API. Unlike a tech-only aggregator it covers
  healthcare, education, trades, finance, retail, logistics, creative and public
  sector roles as well as technical ones, so it is the right default for most
  people. Needs a free API key. Trigger phrases: find a job, job search, job
  openings, vacancies, hiring, positions open, remote jobs, "are there any
  <role> jobs in <place>".
---

# Adzuna Search

Searches jobs through [Adzuna](https://www.adzuna.com)'s **official public
API**. Adzuna aggregates listings from thousands of job boards, employer career
sites and recruitment agencies.

> This is a country-agnostic worked example of the repo's job-portal-skill
> pattern. It queries a documented JSON API, so results are structured and
> nothing breaks when a website is redesigned.

## Why this is the default portal

- **All sectors.** Nursing, teaching, plumbing, accountancy, warehouse work and
  software all appear. Most aggregators skew technical; this one does not.
- **19 countries**, selected per query.
- **Official API.** Documented, versioned, and intended for programmatic use, so
  there is no markup to parse and no terms to work around.

## Requires a free API key

Adzuna issues keys instantly at
[developer.adzuna.com/signup](https://developer.adzuna.com/signup) with no card.
Set them in your environment, or in your MCP client's `env` block:

```bash
export ADZUNA_APP_ID=your_app_id
export ADZUNA_APP_KEY=your_app_key
```

Check they are picked up:

```bash
bun run cli/src/cli.ts credentials
```

The free tier allows roughly 1,000 calls a month, which is far more than a
personal job search uses. Every command fails with a clear message rather than a
stack trace when the key is missing.

## Commands

### Search

```bash
bun run cli/src/cli.ts search [-q "<keywords>"] [-w "<location>"] [--country us] [--format json|table|plain]
```

| Flag | Meaning |
|---|---|
| `--query`, `-q` | Keywords: title, skill, role |
| `--where`, `-w` | Location: city, region or postcode. Free text |
| `--country`, `-c` | Two-letter market. Default `us` |
| `--jobage <days>` | Only ads posted within N days |
| `--page <n>` | 1-indexed page. Default 1 |
| `--limit`, `-n` | Results per page. Default 25 |
| `--remote` | Folds "remote" into the keyword query (see caveat) |
| `--salary-min <n>` | Minimum salary |
| `--full-time` / `--permanent` | Contract filters |
| `--category <tag>` | Adzuna category, e.g. `it-jobs`, `healthcare-nursing-jobs` |
| `--sort-by <mode>` | `date`, `salary` or `relevance` |
| `--format <fmt>` | `json` (default), `table`, `plain` |

Supported countries: `at au be br ca ch de es fr gb in it mx nl nz pl sg us za`

### Examples

```bash
bun run cli/src/cli.ts search -q "registered nurse" -w "Denver" --country us --format table
bun run cli/src/cli.ts search -q "project manager" --remote --jobage 14 --format table
bun run cli/src/cli.ts search -q "graphic designer" -w "Manchester" --country gb --limit 10
```

## Two caveats worth knowing

**`--remote` is a keyword, not a filter.** Adzuna has no remote facet, so this
folds the word "remote" into the query. It surfaces ads that *say* remote and
misses ones that only imply it. Confirm the work arrangement from the
description text rather than trusting the flag. That is the same rule this repo
applies to every portal's remote filter, none of which are reliable.

**Salaries may be predicted.** When an ad states no salary, Adzuna estimates one
and sets `salary_is_predicted`. Results carry that flag through, and a predicted
band must never be treated as the employer's stated offer.

## Output

`--format json` returns `{count, results[]}`. Each result:

```json
{
  "id": "1234567890",
  "title": "Registered Nurse",
  "company": "Acme Health",
  "location": "Denver, CO",
  "date": "2026-08-20T10:00:00Z",
  "url": "https://www.adzuna.com/details/1234567890",
  "salary_min": 70000,
  "salary_max": 90000,
  "salary_is_predicted": false,
  "contract_type": "permanent",
  "category": "Healthcare & Nursing Jobs",
  "description": "..."
}
```

Descriptions in search results are **snippets**. For the full posting, fetch the
`url`, which redirects to the original advertiser.

## Notes

- Zero runtime dependencies: plain `bun` and `fetch`.
- 429 and 5xx are retried with exponential backoff; 4xx are not, since a bad key
  fails identically every time and retrying only burns the monthly quota.
- Point `ADZUNA_API_URL` elsewhere to use a proxy or a mock in tests.
