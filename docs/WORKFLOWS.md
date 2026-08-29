# Workflows

The MCP tools handle data. The **workflows** handle judgement and writing:
turning a posting into a tailored, compiled, proofread CV and cover letter.

They are plain markdown instruction files under `.claude/`, not code. Any AI
agent that reads that folder can run them, including **Claude Code** and
**GitHub Copilot CLI**.

Run them from inside the project folder by typing the command, for example:

```
/apply https://example.com/jobs/12345
```

If your tool does not support slash commands, just say
*"follow the instructions in .claude/commands/apply.md for this posting"*.

---

## Start here: `/setup`

Run this once, before anything else.

It interviews you about your background, then writes your profile to the
`profile/` folder at the top of the project. Everything else reads those files,
so nothing works properly until this is done.

`profile/` is gitignored, so your name, employment history and salary
expectations are never committed. The files under
`.claude/skills/job-application-assistant/` are blank **templates** that stay
tracked; `/setup` copies their structure but never writes your details into
them.

You can point it at an existing CV or LinkedIn export to save typing.

`/setup --section search` later updates just your search terms.

---

## The daily loop

| Command | What it does |
|---|---|
| `/scrape` | Search the job boards, drop anything already seen, show what is new |
| `/rank` | Score the new batch against your fit framework, return a shortlist |
| `/apply <url>` | The full pipeline for one job: evaluate, draft, review, revise, compile, verify, track |
| `/outcome <company>` | Record what happened; also drafts follow-ups for applications that have gone quiet |
| `/interview <company>` | Stage-specific preparation, and an optional mock interview |

`/scrape` finds, `/rank` triages cheaply, `/apply` goes deep on one. On a big
batch do not skip `/rank`; it exists so you are not hand-reading a forty-row
table.

---

## How `/apply` works

This is the part worth understanding, because it is where the quality comes
from.

1. **Fetch** the posting. Falls back to browser headers if the site rejects the
   first request, and prefers the employer's own careers page over an
   aggregator, because aggregators drop the requisition ID and seniority grade.

2. **Evaluate** against your fit framework: technical, experience, behavioural
   and career alignment, weighted. Location and salary are pass/fail gates, not
   weighted scores. **It stops and asks you before drafting anything.**

3. **Draft** a CV and cover letter that address every stated requirement,
   either matched or honestly gapped.

4. **Review** in a fresh agent context, so the reviewer is not attached to the
   draft it is critiquing. This includes company research, a voice check
   against your behavioural profile, and a **grounding audit**: every factual
   claim is checked against your profile, and anything unsupported is stripped.
   This is the step that stops the AI quietly inventing achievements.

5. **Revise, compile and look at it.** Both documents are compiled to PDF and
   visually inspected. The CV must be exactly two pages with no job title left
   stranded at the bottom of a page; the cover letter exactly one. "It looks
   fine in the source" is not accepted, because LaTeX page breaks are
   unpredictable.

6. **ATS check.** The CV's text layer is extracted the way an applicant
   tracking system reads it, confirming your email and phone survive as real
   text rather than being trapped in an icon or a hyperlink, and reporting
   keyword coverage. Genuine gaps stay visible. Keyword stuffing is never the
   fix.

7. **Track.** A row in your tracker, and the posting archived under
   `documents/applications/`.

---

## Occasional commands

| Command | What it does |
|---|---|
| `/expand` | Enriches your profile from documents and your public presence. Additive only, never overwrites |
| `/upskill` | Compares tracked postings against your profile and produces a learning plan for the gaps |
| `/html-report` | A self-contained HTML dashboard of your pipeline. One file, opens in any browser |
| `/gmail-sync` | Scans your email for status signals. Proposes every change for approval, never writes unasked |
| `/notion-sync` | Publishes a read-only view of your pipeline to Notion |
| `/add-portal` | Scaffolds a search tool for another job board |
| `/add-template` | Registers your own CV or cover letter template, in LaTeX, Typst or anything else that compiles from the command line |
| `/reset` | Wipes parts of the workspace back to blank. Destructive, and always confirms first |

---

## Facts, and where they come from

Your profile files are the single source of truth about you. A tailored CV is
an **output**, never a fact source.

If you tell the agent something new about your background during a session, it
belongs in your profile that same turn, either by hand or with the
`add_profile_fact` tool. Otherwise the next session's grounding audit will see
it as unsupported and strip it back out.

---

## Bringing your own templates

The project ships with a LaTeX CV (moderncv, banking style) and a custom cover
letter class. Neither is mandatory.

`/add-template` registers your own: it stores the files, records how to compile
them, verifies the compile actually works, and wires it into `/apply`. Anything
that produces a PDF from the command line is fine.

---

## Adding another job board

`/add-portal` walks through building a search tool for a board this project
does not cover: investigate the site, scaffold the tool from the existing
pattern, and test a live query before registering it.

The two bundled examples are in `.agents/skills/`. They are TypeScript, run
with Bun, and have no dependencies to install.

Portal tools are usually specific to one country or market, so they are most
useful kept in your own fork.
