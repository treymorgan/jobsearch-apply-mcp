# Job Search Apply MCP

[![CI](https://github.com/treymorgan/jobsearch-apply-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/treymorgan/jobsearch-apply-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-server-5A4FCF.svg)](https://modelcontextprotocol.io)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/treymorgan)

**Turn a job posting into a CV and cover letter you can actually send.**

Give it a posting. It scores whether the job is worth your time, drafts a
tailored CV and cover letter, has a second AI review the draft and strip any
claim your profile does not support, compiles both to PDF, checks the pages
are right and that an applicant tracking system can read them, and tracks what
happened next.

It also finds the postings in the first place, and remembers everything it has
already shown you.

Runs entirely on your own machine with the AI tools you already use:
**Claude Code**, **GitHub Copilot CLI**, **Claude Desktop**, **Cursor**, or
anything else that speaks MCP. No API keys, no server, no subscription.

Your files stay on your own computer. This project runs no service, has no
account, and uploads nothing anywhere.

One honest caveat: it works *through* your AI assistant, so anything you ask
that assistant to read is sent to whichever AI provider you already use, exactly
as if you had pasted it into a chat with it. Your CV is stored locally, but if
you ask the assistant to tailor it, the assistant sees it. See
[SECURITY.md](SECURITY.md).

---

## How it works

```
      ┌────────────────────────────────────────────────────────┐
      │  ONE-TIME SETUP                                        │
      │                                                        │
      │   Install  ──▶  /setup  ──▶  edit jobsearch.config.json│
      │                 tells it        tells it what jobs     │
      │                 about YOU       you want               │
      └────────────────────────────────────────────────────────┘
                                │
                                ▼
      ┌────────────────────────────────────────────────────────┐
      │  EVERY WEEK                                            │
      │                                                        │
      │   /scrape  ──▶  /rank  ──▶  /apply <url>               │
      │   find new      score &     tailor CV + letter,        │
      │   postings      shortlist   check them, track it       │
      └────────────────────────────────────────────────────────┘
                                │
                                ▼
      ┌────────────────────────────────────────────────────────┐
      │  WHEN SOMETHING HAPPENS                                │
      │                                                        │
      │   /outcome <company>  ──▶  /interview <company>        │
      │   record the reply         prepare for the call        │
      └────────────────────────────────────────────────────────┘
```

Two halves, working together:

- **The MCP server** remembers things: every posting seen, every application
  sent, your profile. Your AI assistant queries it with ordinary questions.
- **The workflows** do the writing: evaluating a role, drafting a tailored CV
  and cover letter, checking them, and preparing you for the interview.

---

## Is this for me?

You need to be comfortable copying a few commands into a terminal. You do
**not** need to know what MCP is, own a server, or write any code.

There are two tiers, and the difference matters:

| You have | What you get |
|---|---|
| **GitHub Copilot CLI** or **Claude Code** | **Everything.** The `/setup`, `/scrape`, `/apply` workflows run as typed commands. **Recommended.** |
| Claude Desktop, Cursor, or another MCP client | The 19 data tools only. The workflows still work, but you paste in an instruction file to start each one (shown below). |
| A Linux server or VPS | Either of the above, reachable from your phone. See [docs/HOSTING.md](docs/HOSTING.md). |
| None of the above | You need at least one AI app that speaks MCP. |

**Why the difference:** the drafting workflows are markdown instruction files in
`.claude/`. Coding CLIs load that folder automatically and expose each file as a
slash command. Desktop chat apps do not, so there you point the assistant at the
file by hand. Same workflow, one extra line of typing.

If you are choosing, pick a coding CLI. The CV drafting is where the value is,
and that is the tier where it runs by itself.

---

## What you get

**19 tools your AI assistant can call**, covering the whole loop:

- search job portals and remember everything already seen, so you never read
  the same posting twice
- pull a posting's full text and work out whether it is genuinely remote and
  what it pays
- check a role against your own hard limits (salary floor, where you are
  willing to work) with a deterministic yes/no, not a vibe
- score and shortlist a batch of postings
- track applications from drafted to offer or rejection
- store and search your own profile: experience, skills, interview stories

**Plus a set of guided workflows** (`/apply`, `/scrape`, `/rank`, `/interview`
and more) that turn a job posting into a tailored, compiled, proofread CV and
cover letter. See [docs/WORKFLOWS.md](docs/WORKFLOWS.md).

The value is in the drafting. A reviewer agent critiques every draft before you
see it, and a grounding audit strips any claim your profile does not actually
support, so the CV cannot quietly invent things about you.

---

## Quick start

Three steps. Budget about ten minutes.

### 1. Install

**Windows:** use **PowerShell** (press Start, type "PowerShell"). **macOS:** use
**Terminal** (Cmd+Space, type "Terminal").

You need two things:

- **Python 3.10 or newer.** Check with `python --version` on Windows,
  `python3 --version` on macOS. If missing, get it from
  [python.org](https://www.python.org/downloads/) and **tick "Add Python to
  PATH"** in the Windows installer, or it will not be found later.
- **Git.** Check with `git --version`. If missing, get it from
  [git-scm.com](https://git-scm.com/downloads), or skip it by downloading this
  project as a ZIP from GitHub ("Code" → "Download ZIP") and unzipping it.

```bash
git clone https://github.com/treymorgan/jobsearch-apply-mcp.git
cd jobsearch-apply-mcp
pip install -e .
```

On macOS and Linux use `pip3` if `pip` is not found.

Check it installed:

```bash
jobsearch-mcp --check
```

That prints where everything resolved to and flags anything wrong. It is the
fastest way to confirm the install before touching your AI app's config.

<details>
<summary>If pip complains about an "externally managed environment"</summary>

Some systems protect the system Python. Use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

Note the interpreter path, you may need it in step 3:

| OS | Path |
|---|---|
| Windows | `C:\path\to\jobsearch-apply-mcp\.venv\Scripts\python.exe` |
| macOS / Linux | `/path/to/jobsearch-apply-mcp/.venv/bin/python` |
</details>

### 2. Tell it what you are looking for

```bash
cp jobsearch.config.example.json jobsearch.config.json
```

On Windows Command Prompt use `copy` instead:

```
copy jobsearch.config.example.json jobsearch.config.json
```

(PowerShell accepts `cp`.)

Open `jobsearch.config.json` in any text editor and change the search terms to
job titles you actually want. Everything in the file is optional and explained
inline. Full reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

### 3. Connect it to your AI app

Pick your app below, then restart it.

<details open>
<summary><b>GitHub Copilot CLI</b> or <b>Claude Code</b> (recommended - full workflows)</summary>

**Claude Code**, from inside the cloned folder:

```bash
claude mcp add jobsearch -- jobsearch-mcp
```

**GitHub Copilot CLI**, edit your MCP config:

| OS | File |
|---|---|
| Windows | `C:\Users\<you>\.copilot\mcp-config.json` |
| macOS / Linux | `~/.copilot/mcp-config.json` |

```json
{
  "mcpServers": {
    "jobsearch": {
      "type": "local",
      "command": "jobsearch-mcp",
      "env": { "JOBSEARCH_HOME": "/full/path/to/jobsearch-apply-mcp" },
      "tools": ["*"]
    }
  }
}
```

With either of these, run the workflows by typing `/setup`, `/scrape`, `/apply`
directly. Open the project folder in the CLI so it finds `.claude/`.
</details>

<details>
<summary><b>Claude Desktop</b> (data tools only)</summary>

Edit the config file directly:

| OS | File |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

Or from inside the app: **Settings → Developer → Edit Config**. Paste this in,
replacing the path with the folder you cloned into:

```json
{
  "mcpServers": {
    "jobsearch": {
      "command": "jobsearch-mcp",
      "env": { "JOBSEARCH_HOME": "/full/path/to/jobsearch-apply-mcp" }
    }
  }
}
```

On Windows the path looks like `C:\\Users\\you\\jobsearch-apply-mcp` (double
backslashes are required in JSON).

If `jobsearch-mcp` is not found, use the full Python path instead:

```json
{
  "mcpServers": {
    "jobsearch": {
      "command": "python",
      "args": ["-m", "jobsearch_mcp.server"],
      "env": { "JOBSEARCH_HOME": "/full/path/to/jobsearch-apply-mcp" }
    }
  }
}
```

Claude Desktop does not read the `.claude/` folder, so `/setup` and the other
slash commands do not exist there. You get the 19 data tools, and you start each
workflow by pasting its instruction file path (see
[Using it](#using-it-a-worked-example) below).
</details>

<details>
<summary><b>Cursor</b> (data tools only)</summary>

Create `.cursor/mcp.json` in your project, using the same shape as the Claude
Desktop example above. Same caveat: data tools yes, slash commands no.
</details>

<details>
<summary><b>ChatGPT, Grok, Gemini</b> (not supported without hosting)</summary>

These connect to MCP servers over **remote HTTP only**. They cannot launch a
local program, which is how this project normally runs.

To use them you would have to host the server yourself, with a public HTTPS
address and authentication, as described in
[docs/HOSTING.md](docs/HOSTING.md). That is a real amount of work, and even
then you would get the data tools without the drafting workflows, which is the
part most people want.

For a laptop, use a coding CLI instead. Hosting is worth it mainly if you
want to reach your job search from a phone.
</details>

### Check it worked

Ask your AI assistant:

> Use the jobsearch config_status tool and show me the result.

You should get back a summary of your settings. If you do, you are done.
Then try:

> Search for jobs using the jobsearch tools and show me what is new.

Something wrong? See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

---

## Using it: a worked example

Setup told the server *how* to run. This tells it *about you*, and then puts it
to work. Talk to your AI assistant in the project folder in plain English.

### Step 1: Tell it about yourself (once, about 15 minutes)

Drop whatever you already have into the `documents/` folder first. It saves a
lot of typing:

| Put this here | What it is |
|---|---|
| `documents/cv/` | Your current CV or resume, **as PDF** (`.docx` cannot be read, convert it first) |
| `documents/linkedin/` | LinkedIn profile export (Profile → Resources → Save to PDF) |
| `documents/diplomas/` | Degree certificates |
| `documents/references/` | Reference letters |

Then say:

> /setup

It reads what you provided, asks about anything missing, and writes your
profile to the `profile/` folder. If you have nothing to upload, it just
interviews you instead.

Everything it writes is gitignored. Your name, phone number and salary
expectations never get committed.

### Step 2: Tell it what you are looking for

`/setup` fills in `jobsearch.config.json` for you, but it is a plain text file
and you should check it. Open it and confirm the search terms match how jobs
you want are actually advertised:

```json
{
  "search": {
    "queries": ["registered nurse", "clinical nurse specialist"],
    "remote_location": "United States",
    "local_location": "Denver, Colorado, United States",
    "local_metro": ["denver", "boulder", "aurora"]
  },
  "deal_breakers": {
    "salary_floor": 85000
  }
}
```

That example says: search remote roles across the US, **and** anything in the
Denver area where commuting is fine, and treat anything under $85,000 as a no.

Leave `local_metro` empty if you only want remote work. Every field is
optional and explained in [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

Check it took effect:

> Run the jobsearch config_status tool.

### Step 3: Find jobs

> /scrape

Searches the job boards, drops anything you have already seen, and shows what
is new. Run it every few days; it only ever shows you new postings.

> /rank

Scores that batch against your profile and hands back a shortlist, so you are
not reading a forty-row table by hand.

You can also just ask normally:

> Any new remote jobs over $100k that I have not looked at yet?

### Step 4: Apply to one

> /apply https://example.com/jobs/12345

This is the part that saves real time:

1. Reads the posting and **scores your fit**, then stops and asks whether to
   continue. It will tell you when a job is not worth applying to.
2. Drafts a CV and cover letter tailored to that posting.
3. A **second AI reviews the draft** with fresh eyes, researches the company,
   and strips any claim your profile does not actually support. It cannot
   invent achievements for you.
4. Compiles both to PDF, looks at the result, and fixes layout problems. The CV
   comes out at exactly two pages, the letter at one.
5. Checks the PDF is machine-readable, so an applicant tracking system does not
   silently discard you.
6. Records it in your tracker.

You get two PDFs to read and send. **Always read them before sending.**

### Step 5: Keep track

> /outcome Acme Corp

Records what happened: heard nothing, got an interview, rejected, offered. It
also drafts follow-up emails for applications that have gone quiet.

> /interview Acme Corp

Builds a preparation pack for the specific stage you have reached, using the
CV you actually sent, and will run a mock interview if you want one.

### What a normal week looks like

```
Monday      /scrape        see what is new
            /rank          get the shortlist
Tuesday     /apply <url>   apply to the best two or three
Thursday    /outcome       record any replies
As needed   /interview     prepare when you get a call
```

Full detail on every command: [docs/WORKFLOWS.md](docs/WORKFLOWS.md).

### If you do not have slash commands

On Claude Desktop, Cursor and other chat clients, `/setup` and friends do not
exist. The workflows still run: point the assistant at the instruction file.

Note the two folders. Most workflows are **commands**; three are **skills**.

| Workflow | Say this |
|---|---|
| `/setup` | Follow the instructions in `.claude/commands/setup.md` |
| `/apply` | Follow the instructions in `.claude/commands/apply.md` for this posting: `<url>` |
| `/rank` | Follow the instructions in `.claude/commands/rank.md` |
| `/outcome` | Follow the instructions in `.claude/commands/outcome.md` |
| `/interview` | Follow the instructions in `.claude/commands/interview.md` |
| `/scrape` | Follow the instructions in `.claude/skills/job-scraper/SKILL.md` |
| `/upskill` | Follow the instructions in `.claude/skills/upskill/SKILL.md` |

Everything else is under `.claude/commands/` with a matching filename.

Because the assistant has to read the file each time, this is more typing and
uses more of your context than a coding CLI, which is why a CLI is the
recommended path.

---

## Optional extras

None of these are required. Add them when you want the feature.

| Want | Install | Why |
|---|---|---|
| Live portal search | [Bun](https://bun.sh) | Runs the job-board search tools. Without it, you can still add postings by hand with the `ingest_jobs` tool. |
| Search outside tech | A free [Adzuna API key](https://developer.adzuna.com/signup) | Covers every sector and 19 countries. Without it, search falls back to a source that only lists technical roles. Instant signup, no card. |
| Compiled PDF CVs | [Tectonic](https://tectonic-typesetting.github.io) | Turns the drafted CV and cover letter into PDFs. `brew install tectonic`, or download the binary on Windows. |
| ATS checking | poppler (`pdftotext`) | Verifies an applicant tracking system can read your PDF. `brew install poppler`. |
| Access from your phone | A always-on machine | See [docs/HOSTING.md](docs/HOSTING.md). |

---

## Where your data lives

Nothing leaves your machine unless you deliberately host the server yourself.

| What | Where | In git? |
|---|---|---|
| Your profile, experience, interview stories | `profile/` | No, gitignored |
| Your search settings and salary floor | `jobsearch.config.json` | No, gitignored |
| Your CV, diplomas, references, LinkedIn export | `documents/` | No, gitignored |
| Generated CVs and cover letters | `cv/main_*`, `cover_letters/cover_*` | No, gitignored |
| Jobs seen, applications tracked | a local database in your OS data folder | Not in the repo at all |

The files under `.claude/skills/job-application-assistant/` are **blank
templates** and stay tracked. Your real answers go to `profile/`, which is
gitignored, so forking this repo cannot publish your details by accident.

This is enforced rather than just documented: `python3 tools/security_guards.py`
fails if any of those ignore rules is removed. See [SECURITY.md](SECURITY.md).

---

## Documentation

| Guide | For |
|---|---|
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Every setting, with examples |
| [docs/WORKFLOWS.md](docs/WORKFLOWS.md) | The `/apply`, `/scrape`, `/rank` workflows |
| [docs/TOOLS.md](docs/TOOLS.md) | What each of the 19 MCP tools does |
| [docs/HOSTING.md](docs/HOSTING.md) | Running it on a server, phone access, auth |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | When something does not work |
| [SECURITY.md](SECURITY.md) | Threat model and privacy |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development and tests |

---

## Job boards

| Portal | Covers | Needs |
|---|---|---|
| **Adzuna** | All sectors, 19 countries | A free API key |
| **freehire** | Technical roles, many markets | Nothing |

Search picks Adzuna automatically when a key is present, and falls back to
freehire otherwise, saying so in the results. If you are not looking for a
technical job, get the key: it takes a minute at
[developer.adzuna.com/signup](https://developer.adzuna.com/signup) and there is
no card.

```bash
export ADZUNA_APP_ID=your_app_id
export ADZUNA_APP_KEY=your_app_key
```

Or put them in your MCP client's `env` block alongside `JOBSEARCH_HOME`.
`jobsearch-mcp --check` reports whether they were picked up.

## A note on job boards

Bundled portals use official APIs. That keeps results stable, since an API does
not break when a site changes its markup, and it keeps the project within what
those services allow.

Requests are throttled to one every few seconds regardless. The throttle is
deliberate; please do not remove it.

`/add-portal` checks a site's `robots.txt` and terms when you add your own, and
prefers an official API where one exists.

---

## Contributing

Issues and pull requests are welcome, and so are questions.

| I want to | Go here |
|---|---|
| Get it working / ask a question | [Discussions](https://github.com/treymorgan/jobsearch-apply-mcp/discussions) |
| Report something broken | [Open an issue](https://github.com/treymorgan/jobsearch-apply-mcp/issues/new/choose) |
| Report a security problem | [Private advisory](https://github.com/treymorgan/jobsearch-apply-mcp/security/advisories/new) |
| Contribute a change | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Add a job board for my country | Run `/add-portal`, and keep it in your fork |

Good first contributions: a job board for your market, a CV template for your
country's conventions, or a phrasing fix to the remote-work detection in
`portals.py` (a posting wrongly marked onsite silently costs someone a job, so
these are worth more than they look).

Two ground rules: never commit personal data, and keep examples field-neutral so
the project stays useful whatever someone does for a living. See also the
[Code of Conduct](CODE_OF_CONDUCT.md).

---

## Support

This is free and always will be.

If it saved you an evening of CV formatting, you can
[buy me a coffee](https://buymeacoffee.com/treymorgan). Entirely optional, and
it buys no priority: bugs and PRs are handled on merit. Starring the repo or
filing a good bug report helps the project more.

---

## Licence

MIT for this project's own code and documentation. See [LICENSE](LICENSE).

The bundled fonts under `cover_letters/OpenFonts/` are **not** MIT. Lato and
Raleway are licensed under the SIL Open Font License 1.1. If you redistribute
this project, their `OFL.txt` files must ship with them. Details in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

Built on the `ai-job-search` framework by Mads Lorentzen. The MCP server,
configuration layer and hosting options were added by Trey Morgan.
