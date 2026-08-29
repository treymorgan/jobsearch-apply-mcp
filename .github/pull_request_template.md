<!--
Thanks for contributing.

Please confirm you have not committed any personal data:
  git diff --cached | grep -Ei '@|phone|salary|linkedin\.com/in/'
  python3 tools/security_guards.py
-->

## What this changes

<!-- One or two sentences. Link an issue if there is one. -->

## Why

<!-- The problem being solved, not just the change made. -->

## Checklist

- [ ] `python3 -m unittest discover -s tests -t .` passes
- [ ] `python3 tools/security_guards.py` passes
- [ ] `python3 tools/lint_skills.py` passes
- [ ] No personal data committed (name, contact details, employer, salary, target job titles)
- [ ] Examples and docs stay field-neutral, so the project works for any profession
- [ ] No em-dashes in anything the project generates for an employer
- [ ] Anything user-specific is configurable, not hardcoded

## Notes for the reviewer

<!-- Anything you are unsure about, or deliberately did not do. -->
