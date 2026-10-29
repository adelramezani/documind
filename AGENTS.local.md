# Personal development workflow

Personal working-style rules. Project facts belong in AGENTS.md.

## Session capture

- When you learn a non-obvious project fact (command, gotcha, convention,
 failed approach, decision+rationale), append it to the AGENTS.md in the
 directory that owns the topic — do this at the moment you learn it.
- Create the directory's AGENTS.md if missing (title + one section only;
 don't scaffold empty sections).
- Root AGENTS.md is only for cross-cutting facts: DB/schema semantics,
 .env credentials, shared conventions every subdirectory needs.
- If a new fact contradicts an existing entry anywhere, fix the stale
 entry — stale notes are worse than none.
- At session end, offer to deduplicate/reorganize.

## Test-first development

- For new features and bug fixes, write the test scenario first: a failing test that
  demonstrates the desired behavior (or reproduces the bug), then implement until it
  passes. Use the project's existing test framework and conventions.
- If a change is genuinely untestable (one-off exploration, throwaway analysis), say so
  explicitly instead of silently skipping tests.

## Regression baseline around major changes

- Before starting a major change, run the relevant tests and record the result as the baseline.
- After the change, re-run and compare against the baseline. New failures must be
  explained and either fixed or explicitly flagged — never silently ignored.

## Approach before implementation

- For new features, libraries, or architectural choices: investigate options first
  (existing codebase patterns, then docs/best practices), then present a short
  comparison with a recommendation and trade-offs — and wait for my decision before
  implementing. Don't jump straight to code.
- Give a real opinion; disagree when the trade-offs warrant it rather than deferring.
- For new dependencies, check what the project already uses; prefer mature versions
  (at least ~7 days old, pinned).

## Environment safety

- Before running anything that touches real infrastructure (production/staging
  databases, cloud resources, deploy or sync commands, external APIs with side
  effects), check whether a simulated/test environment exists for the task.
- If the work could run against a simulation but none is configured, STOP and ask:
  "Want me to set up a simulated environment first?" Never assume the real
  environment is intended.

## Database safety
- Database access is read-only by default. Writes outside this project database [database_name],
 and any DROP/DELETE/TRUNCATE, require explicit user approval first.
- Exploratory queries must filter (e.g. time range) and LIMIT; no unbounded
 scans of tables.

## Working style

- Minimal diffs: no drive-by refactors or reformatting outside the task. Notice an
  improvement? Mention it, don't implement it.
- Never claim something works without running it. Report actual output; on failure,
  show the error, not a summary of it.
- Stop and ask before: schema/migration changes, new dependencies, deleting or
  renaming files, modifying shared modules. Proceed without asking for additive
  changes, tests, and notes.
- Clean up temp files you create.

## AI agent skill development

- When creating a new skill, use the following structure:
>  Interview me to find out what you are going to create
>  - Interview. ask one question at a time:
>  - what triggers the skill (the user request or situation)
>  - what goal and output it should produce
>  - the exact steps
>  - which tools, repos or credentials it needs
>  - known gotchas, and what to never do
>  - what done looks like (how it gets verified)
>  - one or two concrete examples

## README maintenance

- After creating a new feature or updating an existing one, update `README.md` in the same change: add/refresh its row in the Features table (name, link, description, date).
