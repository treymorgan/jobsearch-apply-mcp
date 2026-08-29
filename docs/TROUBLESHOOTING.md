# Troubleshooting

Start here: ask your AI assistant to run the **`config_status`** tool. It
reports which config file was loaded, which rules are active, where your
profile and state directories are, and whether portal search is available.
Most problems are visible in that one output.

---

## Setup problems

### My AI app does not show the jobsearch tools

1. **Restart the app completely.** Most MCP clients only read their config at
   startup, and closing the window is often not enough. Quit it properly.
2. **Check the config file is valid JSON.** A trailing comma or a missing
   bracket makes the whole file unreadable, and most apps fail silently. Paste
   it into any JSON validator.
3. **Check the command actually runs.** In a terminal:

   ```bash
   jobsearch-mcp --check
   ```

   That prints a configuration report and exits. It is the single best way to
   confirm an install: it shows the workspace it found, the config file it
   loaded, where your profile and database live, and whether portal search is
   available.

   If it says "command not found", see the next entry.

   > Running plain `jobsearch-mcp` with no arguments looks like it hangs. That
   > is correct: it is waiting for your AI app to talk to it over stdin. Press
   > Ctrl+C and use `--check` instead.

### "jobsearch-mcp: command not found"

The install put the command somewhere not on your PATH. Find it:

```bash
python3 -c "import shutil; print(shutil.which('jobsearch-mcp'))"
```

If that prints a path, use the full path in your MCP client config. If it
prints `None`, use the module form instead, which always works:

```json
{
  "command": "python",
  "args": ["-m", "jobsearch_mcp.server"],
  "env": { "JOBSEARCH_HOME": "/full/path/to/jobsearch-mcp" }
}
```

On macOS and Linux you may need `python3` rather than `python`.

### "No module named jobsearch_mcp"

The package is not installed into the Python your app is launching. If you used
a virtual environment, point the client at that environment's Python
explicitly:

| OS | Path |
|---|---|
| macOS / Linux | `/path/to/jobsearch-mcp/.venv/bin/python` |
| Windows | `C:\path\to\jobsearch-mcp\.venv\Scripts\python.exe` |

### pip says "externally managed environment"

Your system Python is protected. Use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e .
```

### The server starts but finds no profile or portals

It cannot locate the project folder. Set `JOBSEARCH_HOME` to the full path of
your clone in your MCP client's `env` block. `config_status` shows what it
resolved to.

---

## Search problems

### "bun runtime not found"

Live portal search needs [Bun](https://bun.sh):

```bash
curl -fsSL https://bun.sh/install | bash        # macOS / Linux
```

On Windows, in PowerShell:

```powershell
powershell -c "irm bun.sh/install.ps1 | iex"
```

Bun installs to `~/.bun/bin`, which is often missing from the PATH that GUI
apps inherit. The server checks that location automatically, but if it still
cannot find it, set `BUN_PATH` to the full path of the `bun` executable in your
client's `env` block.

You can use everything else without Bun. Add postings by hand with the
`ingest_jobs` tool.

### "No search terms"

Your `jobsearch.config.json` has no `search.queries`, or the file was not
found at all. `config_status` shows which file was loaded. See
[CONFIGURATION.md](CONFIGURATION.md).

### Search returns nothing, or far too little

- **Widen the time window.** `days` defaults to 14. Try 30.
- **Check your search terms** match how postings are actually titled. Job
  boards match literally, so an unusual internal title returns nothing.
- **Check your filters.** `filters.relevance_terms` hides anything that does
  not match. Run the search again with `all_results: true` to see what was
  hidden, then loosen the list.
- **You may be rate-limited.** Job boards throttle repeated searches. Wait an
  hour and try again. Do not lower `PORTAL_MIN_INTERVAL`; that makes a block
  more likely, not less.

### Search returns lots of irrelevant jobs

Broad search terms match broadly. Add words to `filters.exclude_terms` for the
categories you keep seeing, and use `filters.relevance_terms` to require a
signal that real matches share. Nothing is deleted, so you can always undo it.

### Everything comes back as "remote unconfirmed"

That is honest, not broken. Search results carry no reliable work-arrangement
field, so remote status is only resolved from a posting's full text. Run the
`job_detail` tool on anything you care about and the status is worked out and
saved.

### A remote job was marked onsite or hybrid

Some postings mention an office in passing. Use `update_job` to correct the
status; the correction is stored. If the wording is a common one, it is worth
opening an issue.

---

## Document problems

### "tectonic: command not found"

Compiling CVs and cover letters needs [Tectonic](https://tectonic-typesetting.github.io):

```bash
brew install tectonic          # macOS
```

On Windows and Linux, download the binary from the Tectonic releases page and
put it on your PATH. Tectonic is self-contained and needs no admin rights,
which is why it is preferred over a full TeX installation.

### The first compile takes forever

It is downloading LaTeX packages. It needs network access, and it only happens
once per document type. If it fails part way, just run it again; it resumes
from cache.

### The CV comes out as three pages

`cv/main_example.tex` is a comprehensive sample, so three pages is expected for
it. Tailored CVs produced by the `/apply` workflow are trimmed to exactly two
pages, and the workflow will not finish until they are.

### A job title sits alone at the bottom of a page

Add `\needspace{5\baselineskip}` before that entry. To rescue a section that
only just spills over, `\enlargethispage{2\baselineskip}` on the previous page
usually does it.

### Cover letter bullets are in the wrong font

`\lettercontent{}` must not wrap `\begin{itemize}`. Close it first, then wrap
the list in its own font block. The exact pattern is in
`.claude/skills/job-application-assistant/06-cover-letter-templates.md`.

---

## Hosting problems

### The server refuses to start with an authentication error

You set `MCP_AUTH=none` while listening on a public address. The server stops
on purpose rather than exposing your profile. Either bind to `127.0.0.1` and
use an SSH tunnel, or set `MCP_AUTH=token`. See [HOSTING.md](HOSTING.md).

### "MCP_AUTH=oauth needs the optional OAuth dependencies"

```bash
pip install -e ".[oauth]"
```

### Clients have to sign in again after every restart

`MCP_JWT_SIGNING_KEY` is changing between restarts, or the OAuth store is not
on a persistent volume. Set a fixed key and keep `/data` mounted.

### Hosted search works locally but not on the server

Job boards treat data-centre IP ranges differently. Run searches from your own
machine and push the results to the server with `ingest_jobs`.

---

## Still stuck?

Turn on debug logging and read what the server says:

```bash
LOG_LEVEL=DEBUG jobsearch-mcp          # macOS / Linux
```

```powershell
$env:LOG_LEVEL="DEBUG"; jobsearch-mcp   # Windows PowerShell
```

There is also a durable audit log recording every tool call, in your state
directory (`config_status` shows the path) as `audit.log`.

When opening an issue, include the `config_status` output and the relevant log
lines. **Remove your personal details first**; that output includes file paths
and your search settings.
