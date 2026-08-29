import {
  API_BASE, COUNTRIES, CREDENTIALS_HELP, credentials, fetchJSON, normalize,
  type Result,
} from "../helpers.js"

export interface SearchOpts {
  query?: string
  where?: string
  country: string
  jobage?: number
  page: number
  limit: number
  format: "json" | "table" | "plain"
  remote: boolean
  salaryMin?: number
  fullTime: boolean
  permanent: boolean
  category?: string
  sortBy?: string
}

function fail(error: string, code: string): number {
  process.stderr.write(JSON.stringify({ error, code }) + "\n")
  return 1
}

export function buildUrl(opts: SearchOpts, appId: string, appKey: string): string {
  const url = new URL(`${API_BASE}/jobs/${opts.country}/search/${opts.page}`)
  const p = url.searchParams
  p.set("app_id", appId)
  p.set("app_key", appKey)
  p.set("results_per_page", String(opts.limit))
  p.set("content-type", "application/json")

  // Adzuna has no remote facet, so "remote" is folded into the keyword query.
  // That is a genuine weakness of the source, not something this CLI can fix:
  // it surfaces ads that *say* remote, and misses ones that only imply it. The
  // caller is expected to confirm work arrangement from the description text
  // rather than trusting this filter, which is the same rule that applies to
  // every portal's remote flag.
  const what = [opts.query, opts.remote ? "remote" : ""].filter(Boolean).join(" ").trim()
  if (what) p.set("what", what)
  if (opts.where) p.set("where", opts.where)
  if (opts.jobage) p.set("max_days_old", String(opts.jobage))
  if (opts.salaryMin) p.set("salary_min", String(opts.salaryMin))
  if (opts.fullTime) p.set("full_time", "1")
  if (opts.permanent) p.set("permanent", "1")
  if (opts.category) p.set("category", opts.category)
  if (opts.sortBy) p.set("sort_by", opts.sortBy)
  return url.toString()
}

function renderTable(rows: Result[]): string {
  if (!rows.length) return "(no results)\n"
  const lines = rows.map((r) => {
    const sal =
      r.salary_min || r.salary_max
        ? `${r.salary_min ?? "?"}-${r.salary_max ?? "?"}${r.salary_is_predicted ? " (est)" : ""}`
        : ""
    return [
      (r.title ?? "").slice(0, 48).padEnd(48),
      (r.company ?? "").slice(0, 26).padEnd(26),
      (r.location ?? "").slice(0, 24).padEnd(24),
      (r.date ?? "").slice(0, 10).padEnd(10),
      sal,
    ].join("  ")
  })
  return lines.join("\n") + "\n"
}

export async function runSearch(opts: SearchOpts): Promise<number> {
  if (!COUNTRIES.includes(opts.country)) {
    return fail(
      `--country must be one of: ${COUNTRIES.join(", ")} (got "${opts.country}")`,
      "BAD_ARG",
    )
  }

  const creds = credentials()
  if (!creds) return fail(CREDENTIALS_HELP, "NO_CREDENTIALS")

  let data: any
  try {
    data = await fetchJSON(buildUrl(opts, creds.appId, creds.appKey))
  } catch (e) {
    const err = e as any
    return fail(err?.message ?? String(e), err?.code ?? "API_ERROR")
  }

  const raw = Array.isArray(data?.results) ? data.results : []
  const results: Result[] = raw.map(normalize)

  if (opts.format === "table") {
    process.stdout.write(renderTable(results))
    return 0
  }
  if (opts.format === "plain") {
    process.stdout.write(
      results.map((r) => `${r.title} | ${r.company} | ${r.location} | ${r.url}`).join("\n") + "\n",
    )
    return 0
  }

  process.stdout.write(
    JSON.stringify(
      { count: typeof data?.count === "number" ? data.count : results.length, results },
      null,
      2,
    ) + "\n",
  )
  return 0
}
