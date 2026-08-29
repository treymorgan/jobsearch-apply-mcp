#!/usr/bin/env bun
// Self-contained CLI for Adzuna's official jobs API. No CLI framework and zero
// runtime dependencies, so it runs anywhere `bun` is available with nothing
// installed beyond the repo clone.
//
// Adzuna publishes a documented JSON API and issues free keys instantly, so
// this portal covers every sector rather than only technical roles, and it does
// not break when a website is redesigned.

import { runSearch, type SearchOpts } from "./commands/search.js"
import { COUNTRIES, CREDENTIALS_HELP, credentials } from "./helpers.js"

interface Flags {
  _: string[]
  [k: string]: string | boolean | string[]
}

const ALIAS: Record<string, string> = { q: "query", n: "limit", w: "where", c: "country" }

function parseFlags(argv: string[]): Flags {
  const flags: Flags = { _: [] }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (!a.startsWith("-")) {
      ;(flags._ as string[]).push(a)
      continue
    }
    const name = a.replace(/^-+/, "")
    const key = ALIAS[name] ?? name
    const next = argv[i + 1]
    let value: string | boolean = true
    if (next !== undefined && !next.startsWith("-")) {
      value = next
      i++
    }
    flags[key] = value
  }
  return flags
}

const HELP = `adzuna-cli — search jobs via Adzuna's official API (all sectors, 19 countries)

USAGE
  bun run src/cli.ts search [-q "<keywords>"] [-w "<location>"] [--country us] [--format json|table|plain]

SEARCH FLAGS
  --query, -q <text>     Keywords (title, skill, role).
  --where, -w <text>     Location: city, region or postcode. Free text.
  --country, -c <code>   Two-letter market. Default us.
                         ${COUNTRIES.join(", ")}
  --jobage <days>        Only ads posted within N days (max_days_old).
  --page <n>             1-indexed page. Default 1.
  --limit, -n <n>        Results per page. Default 25.
  --remote               Fold "remote" into the keyword query. Adzuna has no
                         remote facet, so confirm from the description text.
  --salary-min <n>       Minimum salary.
  --full-time            Full-time only.
  --permanent            Permanent only.
  --category <tag>       Adzuna category tag, e.g. it-jobs, healthcare-nursing-jobs.
  --sort-by <mode>       date | salary | relevance (Adzuna default: relevance).
  --format <fmt>         json (default) | table | plain.

CREDENTIALS
  ${CREDENTIALS_HELP}

EXAMPLES
  bun run src/cli.ts search -q "registered nurse" -w "Denver" --country us --format table
  bun run src/cli.ts search -q "project manager" --remote --jobage 14 --format table
  bun run src/cli.ts search -q "graphic designer" -w "Manchester" --country gb --limit 10
`

const KNOWN_FLAGS: Record<string, Set<string>> = {
  search: new Set([
    "query", "where", "country", "jobage", "page", "limit", "remote",
    "salary-min", "full-time", "permanent", "category", "sort-by", "format",
    "help", "h",
  ]),
}

function parseIntFlag(name: string, raw: unknown): number | null {
  const val = parseInt(raw as string, 10)
  if (isNaN(val)) {
    process.stderr.write(
      JSON.stringify({ error: `--${name} must be a number, got "${raw}"`, code: "BAD_ARG" }) + "\n",
    )
    return null
  }
  return val
}

async function main(): Promise<number> {
  const argv = process.argv.slice(2)
  const flags = parseFlags(argv)
  const cmd = (flags._ as string[])[0]

  if (!cmd || flags.help || flags.h) {
    process.stdout.write(HELP)
    return cmd ? 0 : 1
  }

  // Unknown flags are rejected rather than ignored: a silently discarded filter
  // changes what the search returns with no error, which is far worse than a
  // hard failure. add-portal.md's contract requires exit 1 with JSON on stderr.
  const known = KNOWN_FLAGS[cmd]
  if (known) {
    for (const key of Object.keys(flags)) {
      if (key === "_" || known.has(key)) continue
      process.stderr.write(
        JSON.stringify({
          error: `unknown flag --${key} for '${cmd}' - flags are never silently ignored, because a discarded filter changes what the search returns; see --help`,
          code: "UNKNOWN_FLAG",
        }) + "\n",
      )
      return 1
    }
  }

  if (cmd === "credentials") {
    const ok = credentials() !== null
    process.stdout.write(JSON.stringify({ configured: ok, help: ok ? null : CREDENTIALS_HELP }) + "\n")
    return ok ? 0 : 1
  }

  if (cmd === "search") {
    for (const name of ["jobage", "page", "limit", "salary-min"] as const) {
      if (flags[name] !== undefined && flags[name] !== true) {
        const v = parseIntFlag(name, flags[name])
        if (v === null) return 1
        flags[name] = String(v)
      }
    }
    const fmt = (flags.format as string) || "json"
    const opts: SearchOpts = {
      query: typeof flags.query === "string" ? flags.query : undefined,
      where: typeof flags.where === "string" ? flags.where : undefined,
      country: (typeof flags.country === "string" ? flags.country : "us").toLowerCase(),
      jobage: flags.jobage ? parseInt(flags.jobage as string, 10) : undefined,
      page: flags.page ? Math.max(1, parseInt(flags.page as string, 10)) : 1,
      limit: flags.limit ? Math.max(1, parseInt(flags.limit as string, 10)) : 25,
      format: (["json", "table", "plain"].includes(fmt) ? fmt : "json") as SearchOpts["format"],
      remote: flags.remote === true || flags.remote === "true",
      salaryMin: flags["salary-min"] ? parseInt(flags["salary-min"] as string, 10) : undefined,
      fullTime: flags["full-time"] === true,
      permanent: flags.permanent === true,
      category: typeof flags.category === "string" ? flags.category : undefined,
      sortBy: typeof flags["sort-by"] === "string" ? (flags["sort-by"] as string) : undefined,
    }
    return runSearch(opts)
  }

  process.stderr.write(JSON.stringify({ error: `Unknown command "${cmd}"`, code: "BAD_CMD" }) + "\n")
  return 1
}

main()
  .then((code) => process.exit(code))
  .catch((e) => {
    process.stderr.write(
      JSON.stringify({
        error: e instanceof Error ? e.message : String(e),
        code: "INTERNAL_ERROR",
      }) + "\n",
    )
    process.exit(1)
  })
