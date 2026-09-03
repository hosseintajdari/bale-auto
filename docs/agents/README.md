# Checkpoint and handoff standard

## Canonical files

- `docs/agents/HANDOFF.md` is the only active project-state document.
- This file defines how that document is maintained.
- GitHub Issues and Pull Requests track collaborative work when they exist.
- Git commits preserve history. Durable product decisions belong in the
  relevant PRD, ADR, runbook, or product document.

The default is one combined document. Its **Checkpoint** section answers
"what is true now?" and its **Handoff** section answers "what should happen
next?". A second active checkpoint file is justified only when a long-running
operation needs independently updated, machine-oriented resume state. If that
exception is used, the active handoff must name the exact file and explain its
lifecycle.

## Required handoff structure

Use these headings in order:

1. **Metadata** — update time, status, repository/checkout, branch, HEAD, and
   GitHub Issue or Pull Request when one exists.
2. **Checkpoint** — completed outcomes, verified evidence, current boundaries,
   and uncommitted work that must be preserved.
3. **Decisions and blockers** — only unresolved choices that change the result
   or risk.
4. **Handoff** — one next outcome, ordered entry files, authorized scope,
   execution steps, and checkable completion criteria.
5. **History pointers** — links to durable documents, Issues, Pull Requests,
   commits, or archived phase records. Do not copy their full contents.

Label every material statement as one of: **verified**, **reported**,
**proposed**, or **unknown** when its evidence status is not obvious. Include
dates for live or drift-prone facts.

Use this compact skeleton when rebuilding the active file:

```markdown
# Active checkpoint and handoff — <project>

## Metadata
- Updated, status, repository, checkout, branch, HEAD, Issue/PR

## Checkpoint
- Verified outcomes and evidence
- Current boundaries
- Uncommitted work to preserve

## Decisions and blockers
- Decision, bounded options, and why it blocks progress

## Handoff
### One next outcome
### Read in order
### Authorized scope
### Completion criteria

## History pointers
- Durable docs, Issues, Pull Requests, commits, archived phase records
```

## Update rules

Update `HANDOFF.md` when:

- a material phase finishes;
- work pauses with unfinished or uncommitted state;
- the next authorized outcome changes;
- a new owner decision or external blocker prevents safe progress; or
- evidence invalidates a previous checkpoint statement.

Before saving it, inspect the exact checkout and Git status, verify referenced
files exist, and separate current evidence from historical evidence. Keep one
primary next outcome. A handoff records state and authority; it does not grant
new authority by itself.

## GitHub and archival

When an Issue or Pull Request exists, link it from the Metadata section and use
GitHub for discussion, review, CI, and acceptance history. The repository
handoff remains the local resume point, including uncommitted work that GitHub
cannot see.

After a phase handoff is fulfilled, mark it `completed/archived` and point to
the canonical handoff. Do not create a new active handoff for every session.
Retain an old phase document only when it contains durable evidence or a useful
execution record; otherwise Git history is sufficient.

## Completion check

A handoff update is complete when a fresh agent can identify, without chat
history:

- the exact checkout and current Git state;
- the last verified outcome and its evidence;
- the one next outcome and its authorized boundary;
- every unresolved owner decision; and
- the checks that prove the next outcome is finished.
