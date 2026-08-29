# The MCP server

Source for the job search MCP server. If you just want to *use* it, the
[main README](../README.md) is the place to start; this file is about how it is
put together.

```
mcp_server/
  jobsearch_mcp/
    server.py    tool definitions and startup
    config.py    user configuration loading
    auth.py      authentication modes for the HTTP transport
    portals.py   job board adapters, remote and salary detection
    profile.py   candidate profile reads and guarded writes
    store.py     SQLite state: jobs and applications
    paths.py     locating the workspace on disk
  Dockerfile
  docker-compose.yml
  docker-compose.tunnel.yml
  deploy.sh
  backup.sh
```

## Running it

```bash
pip install -e .          # from the repository root
jobsearch-mcp             # stdio, the default
```

For HTTP and hosting, see [docs/HOSTING.md](../docs/HOSTING.md).

## Design notes

### Scope boundary

The server owns **data and state**. It does not draft.

| Server | Local workflows |
|---|---|
| portal search and detail | fit evaluation prose |
| seen-job state, triage scores | CV and cover letter drafting |
| application tracker | reviewer agent critique |
| profile and interview-story lookups | compiling and inspecting PDFs |
| deterministic deal-breaker checks | ATS text-layer check |

Drafting needs a model in the loop, the document tree and a rendered page to
look at, so it stays local. The server is what makes searching and triage work
from anywhere, including a phone.

### Nothing about a particular job search is in the code

Search terms, commutable area, salary floor and title filters all come from
`jobsearch.config.json`. The built-in defaults filter nothing and veto nothing,
so an unconfigured server is useless but harmless rather than quietly applying
somebody else's preferences.

### Portal remote filters are not trusted

A board's remote filter still returns city-based rows, and its search results
carry no work-arrangement field at all, so a search-result location is evidence
of nothing. Remote status is only ever resolved from the posting's own
description text, in `classify_remote`.

The phrase lists behind it are deliberately asymmetric. The positive list is
long, because employers describe remote work in prose rather than with a
checkbox. The negative list contains only work-arrangement phrases, never bare
words: a bare "hybrid" matched "hybrid cloud environment" and vetoed two fully
remote jobs. A false negative silently discards a good job, while a false
positive only costs a manual check.

### Profile writes are shaped so the safe operation is the easy one

The profile is the grounding source for CV drafting, so anything written there
is treated as fact by every future draft.

`add_profile_fact` appends with a date and source and cannot destroy anything.
`update_profile_section` replaces a whole document, but snapshots first and
refuses near-empty content, and is reversible via `restore_profile_revision`.

Backup filenames carry microseconds and never clobber an existing file. An
earlier second-granular scheme let a restore's own safety snapshot overwrite
the very revision it was about to read, so the rollback returned corrupted
content and reported success. `restore` now also reads the revision into memory
before writing anything.

### Deal-breakers are a function, not a prompt rule

Hard constraints should not drift between one session and the next, so they are
evaluated deterministically. Salary is judged on the **top** of the band, since
that is what is negotiable, and a band that straddles the floor is flagged
rather than failed.

### Throttling

A default search fans out to many back-to-back portal requests. Automated
access is against some boards' terms of service and is only defensible as
low-rate personal use, so calls are serialised with a minimum interval
(`PORTAL_MIN_INTERVAL`, default 3 seconds). Please leave it in place.

### Logging goes to stderr

Under the stdio transport, stdout carries the JSON-RPC stream. A single stray
`print` there corrupts the protocol and the client disconnects with an
unhelpful parse error.

There is also a rotating audit log in the state directory recording every tool
call, because container stdout is wiped on every rebuild and an AI-written
profile fact needs to be traceable afterwards.

## Adding a tool

Add a function in `server.py` decorated with `@mcp.tool()`. The docstring is
what the model reads to decide when to call it, so write it for that audience:
say what the tool is for and when to prefer it over a neighbour, not just what
its arguments are.

Call `_audit(...)` at the top of anything that writes.
