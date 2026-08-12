# Agent Handoff — bale-auto

## Purpose

Start here before continuing work on `bale-auto`. This file records the verified
project state, the safety boundary, and the rules for handing work to the next
agent without relying on chat history.

## Communication rule

- Write user-facing answers in Persian when the host environment permits it.
  If a stricter host policy requires another language, obey that policy and
  keep the same explanatory style.
- Keep technical terms in English, for example `Pull Request`, `CI`, `branch`,
  `commit`, and `rollback`; do not replace them with invented translations.
- On first use in a response, give each technical term a brief plain-language
  explanation of its role. For example: `CI` is the automated check that runs
  tests before a change is accepted.
- Keep commands, paths, code, configuration keys, and Git messages in English.

## Verified state — 2026-08-13

- Repository: `hosseintajdari/bale-auto` (private, SSH remote).
- Working branch: `feat/poc-foundation`.
- Draft `Pull Request` #1: https://github.com/hosseintajdari/bale-auto/pull/1
- Current branch commit: `8712973c76e09cfcc273f767eee1cb1d6493aa3c`.
- The `CI` gate is passing: run `31643214009` completed successfully. The
  earlier `startup_failure` runs stopped before GitHub scheduled any job and
  were resolved after the account/payment condition was cleared.
- The repository has an active GitHub roadmap in Issue #2, with Milestones M0
  through M3 and priorities `P0`, `P1`, and `P2`. Native issue dependencies are
  `#3 -> #4 -> (#5 and #6) -> #7 -> #8 -> #9`.
- M0 review work is tracked in Issue #3. M1, M2, M3, and the post-PoC backlog
  are tracked in Issues #4 through #10.
- Notion Project page: https://app.notion.com/p/3b9f6d55a67381cf9c21ce1014da7f82
  links to the GitHub roadmap. No Notion Critical Path milestone was created
  because a verified Goal relation is not currently available.
- A security diff review covered all six changed source-like files and found no
  plausible candidate. Local checks passed: 18 unit tests, policy validation,
  secret scan, and whitespace validation.
- The security scan completion is currently blocked by a tool metadata error:
  `scan.target.snapshotDigest: expected a non-empty string`. Do not claim a
  completed official scan or retry completion blindly; preserve the scan for
  continuation.

## Non-negotiable boundaries

- Keep `bale-auto` separate from BaleMed and BaleMedPrices: no shared paths,
  services, secrets, tokens, runtime state, or deployment resources.
- Never print, commit, copy, or request live secrets.
- Do not merge to `main` without the project owner's explicit approval.
- Do not modify the server without the project owner's explicit approval.
- Do not touch `/opt/bale-bot`; it belongs to another project.
- Do not install or expose OpenClaw until licence, version, security impact,
  rollback, and server approval have been reviewed.

## Server facts

The last read-only inspection found Docker active, no Tailscale or OpenClaw
command, no `/opt/bale-auto` directory, and no active `bale-auto` service.
These facts are not permission to deploy. Re-check them immediately before any
approved server work.

## Notion publication rules

Read `docs/agents/NOTION.md` before writing to Notion. The short version is:

- Git and GitHub are the source of truth for code, commits, pull requests, and
  automated checks.
- The bale-auto Project record carries only stable project status, gates,
  milestones, blockers, and links.
- Use the correct Notion destination for a PRD, runbook, durable decision, or
  glossary term; do not turn the Project record into a session log.
- Fetch the target page and its database schema before creating or changing a
  record. Record only verified facts, label assumptions, and verify every write.

## Safe next sequence

1. Refresh the GitHub state:
   ```powershell
   gh auth status
   gh pr view 1 --repo hosseintajdari/bale-auto
   gh pr checks 1 --repo hosseintajdari/bale-auto
   ```
2. Resolve or continue the blocked security scan using scan ID
  `ca608d3a-2fbf-440e-9c2f-46b450c1813e`; the exact blocker is recorded above.
3. Attach the verified review evidence to GitHub Issue #3 and review Draft
  `Pull Request` #1 for the security boundary and local test evidence. Do not
  merge until the owner explicitly approves it.
4. If the owner approves a merge, make no server change in the same step.
  Treat merge, deployment planning, and server deployment as separate gates.
5. Before any approved deployment, repeat the read-only server inspection,
  document an installation plan and rollback, and use `/opt/bale-auto` only.

## Handoff report format

For every completed session, report:

1. What was done.
2. What was learned, including a short explanation of any new technical term.
3. Evidence: commands, run URLs, commit IDs, or read-only observations.
4. Blocker or owner decision required.
5. The next safe step.
