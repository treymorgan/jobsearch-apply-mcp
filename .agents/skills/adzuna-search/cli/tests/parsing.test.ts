import { describe, expect, test } from "bun:test"
import { buildUrl } from "../src/commands/search.js"
import { COUNTRIES, normalize } from "../src/helpers.js"

const base = {
  country: "us",
  page: 1,
  limit: 25,
  format: "json" as const,
  remote: false,
  fullTime: false,
  permanent: false,
}

describe("buildUrl", () => {
  test("includes credentials and paging", () => {
    const u = new URL(buildUrl({ ...base }, "ID", "KEY"))
    expect(u.pathname).toBe("/v1/api/jobs/us/search/1")
    expect(u.searchParams.get("app_id")).toBe("ID")
    expect(u.searchParams.get("app_key")).toBe("KEY")
    expect(u.searchParams.get("results_per_page")).toBe("25")
  })

  test("omits empty optional params rather than sending blanks", () => {
    const u = new URL(buildUrl({ ...base }, "ID", "KEY"))
    for (const k of ["what", "where", "max_days_old", "salary_min", "full_time"]) {
      expect(u.searchParams.has(k)).toBe(false)
    }
  })

  test("folds --remote into the keyword query", () => {
    const u = new URL(buildUrl({ ...base, query: "nurse", remote: true }, "ID", "KEY"))
    expect(u.searchParams.get("what")).toBe("nurse remote")
  })

  test("remote alone still produces a usable query", () => {
    const u = new URL(buildUrl({ ...base, remote: true }, "ID", "KEY"))
    expect(u.searchParams.get("what")).toBe("remote")
  })

  test("passes filters through", () => {
    const u = new URL(
      buildUrl(
        { ...base, query: "designer", where: "Denver", jobage: 14, salaryMin: 90000, fullTime: true, permanent: true, category: "it-jobs", sortBy: "date" },
        "ID",
        "KEY",
      ),
    )
    expect(u.searchParams.get("what")).toBe("designer")
    expect(u.searchParams.get("where")).toBe("Denver")
    expect(u.searchParams.get("max_days_old")).toBe("14")
    expect(u.searchParams.get("salary_min")).toBe("90000")
    expect(u.searchParams.get("full_time")).toBe("1")
    expect(u.searchParams.get("permanent")).toBe("1")
    expect(u.searchParams.get("category")).toBe("it-jobs")
    expect(u.searchParams.get("sort_by")).toBe("date")
  })

  test("country goes in the path, and every listed country builds", () => {
    for (const c of COUNTRIES) {
      const u = new URL(buildUrl({ ...base, country: c }, "ID", "KEY"))
      expect(u.pathname).toBe(`/v1/api/jobs/${c}/search/1`)
    }
  })
})

describe("normalize", () => {
  test("flattens Adzuna's nested shape", () => {
    const r = normalize({
      id: "123",
      title: "Registered Nurse",
      description: "Care for patients.",
      created: "2026-08-20T10:00:00Z",
      redirect_url: "https://www.adzuna.com/details/123",
      salary_min: 70000.4,
      salary_max: 90000.6,
      company: { display_name: "Acme Health" },
      location: { display_name: "Denver, CO" },
      category: { label: "Healthcare & Nursing Jobs" },
      contract_type: "permanent",
    })
    expect(r.id).toBe("123")
    expect(r.company).toBe("Acme Health")
    expect(r.location).toBe("Denver, CO")
    expect(r.url).toBe("https://www.adzuna.com/details/123")
    expect(r.salary_min).toBe(70000)
    expect(r.salary_max).toBe(90001)
    expect(r.category).toBe("Healthcare & Nursing Jobs")
  })

  test("flags a predicted salary", () => {
    // A predicted band must never be mistaken for the employer's stated offer,
    // or a deal-breaker check would veto (or pass) a job on invented numbers.
    expect(normalize({ salary_is_predicted: "1" }).salary_is_predicted).toBe(true)
    expect(normalize({ salary_is_predicted: "0" }).salary_is_predicted).toBe(false)
    expect(normalize({}).salary_is_predicted).toBe(false)
  })

  test("strips markup from title and description", () => {
    const r = normalize({ title: "<b>Nurse</b>", description: "<p>Care  for\npatients.</p>" })
    expect(r.title).toBe("Nurse")
    expect(r.description).toBe("Care for patients.")
  })

  test("missing fields become null rather than undefined", () => {
    const r = normalize({})
    for (const k of ["id", "title", "company", "location", "date", "url"] as const) {
      expect(r[k]).toBeNull()
    }
  })
})
