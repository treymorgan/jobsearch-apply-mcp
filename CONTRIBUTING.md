# Contributing

Contributions are welcome. This is a small project, so the process is
lightweight.

## Ground rules

**Never commit personal data.** The tracked files are blank templates. Before
opening a pull request:

```bash
git diff --cached | grep -Ei '@|phone|salary|linkedin\.com/in/'
python3 tools/security_guards.py
```

**Keep it field-neutral.** This project should be equally useful to a nurse, a
graphic designer and a backend engineer. Examples in documentation and code
comments must not assume an industry. Where an example is genuinely needed,
label it as one.

**No em-dashes in anything the project generates for an employer.** Commas,
colons and hyphens instead. En-dashes in date ranges are fine.

## Development setup

```bash
git clone <your fork>
cd jobsearch-mcp
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

Optional, for the parts that need them:

- [Bun](https://bun.sh) for the portal search tools
- [Tectonic](https://tectonic-typesetting.github.io) for compiling documents
- poppler (`pdftotext`) for the ATS check

## Running the checks

```bash
python3 -m unittest discover -s tests -t .
python3 tools/lint_skills.py
python3 tools/security_guards.py
```

There is no pytest, and the test suite itself is standard library only.

`tools/lint_skills.py` is the one exception: it parses the YAML frontmatter in
the skill files, so it needs PyYAML.

```bash
pip install pyyaml
```

Most of the tests check the **workflow markdown files** for internal
consistency, which is unusual but deliberate: the workflows are prompts, and a
prompt that contradicts itself fails silently at runtime. The suite has caught
real bugs, such as a new `documents/` subfolder that had not been added to the
`/reset` command's delete list.

**Fix the file, not the test**, unless the test genuinely encodes an assumption
that no longer holds.

## Testing the server by hand

```bash
jobsearch-mcp                      # stdio, what a desktop client launches
LOG_LEVEL=DEBUG jobsearch-mcp      # verbose
```

To exercise it as a client would, use the `fastmcp` Python client with a
`StdioTransport` pointed at `python -m jobsearch_mcp.server`.

Remember that **stdout is the protocol** under stdio. Log to stderr; a stray
`print` corrupts the JSON-RPC stream and the client disconnects with an
unhelpful parse error.

## Project layout

```
mcp_server/jobsearch_mcp/   the MCP server
  server.py                 tool definitions and startup
  config.py                 user configuration
  auth.py                   authentication modes
  portals.py                job board adapters
  profile.py                profile reads and guarded writes
  store.py                  SQLite state
  paths.py                  workspace location

.claude/
  commands/                 the slash-command workflows
  skills/                   profile templates, evaluation framework, scraper logic
.agents/skills/             portal search tools (TypeScript, run with bun)

cv/, cover_letters/         document templates
tools/                      lint, security guards, PDF verification
tests/                      the test suite
docs/                       user documentation
```

## Adding a job board

Use the `/add-portal` workflow. It investigates the site, scaffolds a tool from
the existing pattern, and tests a live query before registering anything.

Portal tools are usually specific to one country or market, so they are
generally best kept in your own fork. The generator is the shared feature; its
output is yours.

If you do contribute one, it must respect the request throttle.

## Adding an MCP tool

Add a function in `server.py` decorated with `@mcp.tool()`. The docstring is
what the model reads to decide when to call it, so write it for that audience:
say what it is for and when to prefer it over a similar tool, not just what the
arguments are.

Call `_audit(...)` at the top of anything that writes.

Anything user-specific belongs in `config.py` and
`jobsearch.config.example.json`, never hardcoded.

## Licence

By contributing you agree your work is licensed under the MIT licence, as in
[LICENSE](LICENSE).
