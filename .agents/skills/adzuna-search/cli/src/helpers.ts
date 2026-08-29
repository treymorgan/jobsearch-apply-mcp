// Shared helpers for the Adzuna CLI. Zero runtime dependencies: plain fetch,
// plain JSON, so the skill runs on a fresh clone with nothing but `bun`.
//
// Adzuna publishes an official JSON API, so unlike a markup-parsing portal
// there is nothing to scrape and nothing that breaks when the site is
// redesigned. It does require a free key, which is the trade.

export const API_BASE = process.env.ADZUNA_API_URL ?? "https://api.adzuna.com/v1/api"

export interface Credentials {
  appId: string
  appKey: string
}

/**
 * Read API credentials from the environment.
 *
 * Returns null rather than throwing so the caller can emit one actionable
 * message. "Get a free key here" is a far more useful failure than a stack
 * trace or an opaque 401 from the API.
 */
export function credentials(): Credentials | null {
  const appId = (process.env.ADZUNA_APP_ID ?? "").trim()
  const appKey = (process.env.ADZUNA_APP_KEY ?? "").trim()
  if (!appId || !appKey) return null
  return { appId, appKey }
}

export const CREDENTIALS_HELP =
  "Adzuna needs a free API key. Register at https://developer.adzuna.com/signup " +
  "(instant, no card), then set ADZUNA_APP_ID and ADZUNA_APP_KEY in your " +
  "environment or in your MCP client's env block."

/** Country codes Adzuna serves. A wrong code returns 404 rather than an error. */
export const COUNTRIES = [
  "at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "gb",
  "in", "it", "mx", "nl", "nz", "pl", "sg", "us", "za",
]

export interface AdzunaJob {
  id?: string
  title?: string
  description?: string
  created?: string
  redirect_url?: string
  salary_min?: number
  salary_max?: number
  salary_is_predicted?: string
  contract_type?: string
  contract_time?: string
  company?: { display_name?: string }
  location?: { display_name?: string; area?: string[] }
  category?: { label?: string; tag?: string }
}

/** The flattened shape every portal skill in this repo returns. */
export interface Result {
  id: string | null
  title: string | null
  company: string | null
  location: string | null
  date: string | null
  url: string | null
  salary_min: number | null
  salary_max: number | null
  salary_is_predicted: boolean
  contract_type: string | null
  category: string | null
  description: string | null
}

function stripTags(s: string): string {
  return s.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim()
}

/** Map Adzuna's JSON onto the portal-skill result contract. */
export function normalize(job: AdzunaJob): Result {
  return {
    id: job.id ?? null,
    title: job.title ? stripTags(job.title) : null,
    company: job.company?.display_name ?? null,
    location: job.location?.display_name ?? null,
    // Adzuna returns ISO 8601 already; kept verbatim so callers can date-filter.
    date: job.created ?? null,
    url: job.redirect_url ?? null,
    salary_min: typeof job.salary_min === "number" ? Math.round(job.salary_min) : null,
    salary_max: typeof job.salary_max === "number" ? Math.round(job.salary_max) : null,
    // Adzuna predicts a salary when the ad states none. Flagged rather than
    // dropped, because a predicted band must never be mistaken for the
    // employer's stated offer by a deal-breaker check.
    salary_is_predicted: String(job.salary_is_predicted ?? "0") === "1",
    contract_type: job.contract_type ?? job.contract_time ?? null,
    category: job.category?.label ?? null,
    description: job.description ? stripTags(job.description) : null,
  }
}

export class ApiError extends Error {
  code: string
  constructor(message: string, code = "API_ERROR") {
    super(message)
    this.code = code
  }
}

/**
 * GET with a timeout and bounded retries.
 *
 * 429 and 5xx are retried with exponential backoff; 4xx are not, since a bad
 * key or a bad country code fails identically every time and retrying only
 * burns the free tier's monthly call budget.
 */
export async function fetchJSON(
  url: string,
  { timeoutMs = 20000, retries = 2 }: { timeoutMs?: number; retries?: number } = {},
): Promise<any> {
  let lastErr: Error | null = null

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const res = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: "application/json", "User-Agent": "jobsearch-apply-mcp" },
      })

      if (res.status === 401 || res.status === 403) {
        throw new ApiError(`Adzuna rejected the credentials (HTTP ${res.status}). ${CREDENTIALS_HELP}`, "AUTH")
      }
      if (res.status === 404) {
        throw new ApiError("Adzuna returned 404 - usually an unsupported country code.", "NOT_FOUND")
      }
      if (res.status === 429 || res.status >= 500) {
        throw new ApiError(`Adzuna returned HTTP ${res.status}`, res.status === 429 ? "RATE_LIMIT" : "SERVER")
      }
      if (!res.ok) {
        throw new ApiError(`Adzuna returned HTTP ${res.status}`, "HTTP")
      }
      return await res.json()
    } catch (e) {
      const err = e instanceof Error ? e : new Error(String(e))
      lastErr = err
      const code = err instanceof ApiError ? err.code : ""
      const retryable = code === "RATE_LIMIT" || code === "SERVER" || err.name === "AbortError"
      if (!retryable || attempt === retries) break
      await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, attempt)))
    } finally {
      clearTimeout(timer)
    }
  }

  throw lastErr ?? new ApiError("request failed")
}
