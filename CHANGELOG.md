# Changelog

Notable changes to this project. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-08-28

First public release.

### Added

- **MCP server** exposing 19 tools for job search, triage, application tracking
  and candidate-profile access. Runs over stdio by default, so no server,
  domain or identity provider is required.
- **Configuration file** (`jobsearch.config.json`) holding search terms,
  commutable area, salary floor and title filters. Nothing about a particular
  job search is hardcoded; the shipped defaults filter nothing and veto nothing.
- **Two job-board portals**: Adzuna (official API, all sectors, 19 countries,
  free key) and freehire (no key, technical roles). Search selects Adzuna when a
  key is configured and falls back to freehire otherwise, reporting which it
  used.
- **Agent workflows** for the full application loop: `/setup`, `/scrape`,
  `/rank`, `/apply`, `/outcome`, `/interview`, `/upskill` and more, including a
  reviewer pass and a factual grounding audit that strips claims the profile
  does not support.
- **Optional HTTP transport** with three authentication modes (`none`, `token`,
  `oauth`) for hosting the server on a machine you control.
- `--help`, `--version` and `--check` command-line flags. `--check` reports the
  resolved configuration and dependencies, and is the supported way to verify an
  install.
- Cross-platform support verified in CI on Linux, macOS and Windows against
  Python 3.10 and 3.13.

### Security

- Personal data is written only to gitignored locations (`profile/`,
  `jobsearch.config.json`), so the project can be forked publicly without
  leaking a profile. Enforced by `tools/security_guards.py` and by CI.
- The server refuses to start unauthenticated on a non-loopback address.
- OAuth mode fails closed on authorization: `MCP_ALLOWED_EMAILS` is required,
  and multi-tenant `AZURE_TENANT_ID` values are rejected.
- Scraped job-posting text is returned under an explicit `untrusted_posting_text`
  key with a banner stating it is third-party data and not instructions, and the
  same warning appears in the relevant tool descriptions.
- `security_guards.py` allowlists the shape of `.claude/settings.json`, not just
  its values, so settings such as `defaultMode: bypassPermissions` are rejected.

[Unreleased]: https://github.com/treymorgan/jobsearch-apply-mcp/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/treymorgan/jobsearch-apply-mcp/releases/tag/v1.0.0
