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
- Deployed foundation: PR #1 merged to `main` at
  `4cb8a3fde2f95aeb8a27584ebb1f935a3b235f85`:
  https://github.com/hosseintajdari/bale-auto/pull/1
- Verification documentation branch: `codex/openclaw-poc-verification`.
- The `CI` deployment gate passed in run `31655666729`. The
  earlier `startup_failure` runs stopped before GitHub scheduled any job and
  were resolved after the account/payment condition was cleared.
- The repository has an active GitHub roadmap in Issue #2, with Milestones M0
  through M3 and priorities `P0`, `P1`, and `P2`. Native issue dependencies are
  `#3 -> #4 -> (#5 and #6) -> #7 -> #8 -> #9`.
- M0-M3 delivery work is tracked in Issues #3 through #9; Issue #10 is the
  post-PoC backlog. Reconcile completed issues against the deployment evidence
  in this handoff.
- Notion Project page: https://app.notion.com/p/3b9f6d55a67381cf9c21ce1014da7f82
  links to the GitHub roadmap. No Notion Critical Path milestone was created
  because a verified Goal relation is not currently available.
- The OpenClaw Compose deployment is live under `/opt/bale-auto`, using image
  `ghcr.io/openclaw/openclaw:2026.7.1-2-slim`. The container is healthy and the
  host publishes port 18789 on `127.0.0.1` only.
- OpenAI OAuth is usable, the default model is `openai/gpt-5.6-sol`, and the
  end-to-end test run `ea78e120-f32c-4807-9152-31f501c85f37` returned the exact
  expected response `BALE_AUTO_OPENCLAW_OK`.
- The health checker was updated for the Docker deployment. Local checks pass:
  19 unit tests, policy validation, secret scan, and whitespace validation.
- The security scan completion is currently blocked by a tool metadata error:
  `scan.target.snapshotDigest: expected a non-empty string`. Do not claim a
  completed official scan or retry completion blindly; preserve the scan for
  continuation.

## Non-negotiable boundaries

- Keep `bale-auto` separate from BaleMed and BaleMedPrices: no shared paths,
  services, secrets, tokens, runtime state, or deployment resources.
- Never print, commit, copy, or request live secrets.
- The owner granted standing authority for normal in-scope commits, pushes,
  pulls, merges, deployment work, and tests. Do not request repetitive approval
  for those routine actions.
- Do not touch `/opt/bale-bot`; it belongs to another project.
- Keep the OpenClaw gateway loopback-only unless the owner explicitly expands
  its access path.

## Server facts

The owner corrected the target to `ubuntu@185.204.170.119`; the local `balemed`
alias resolves to that same user and address. The 2026-08-13 inspection found
Ubuntu 24.04.4 LTS and Docker are active. The existing `/opt/bale-bot` worktree
still has six pre-existing status entries and was not touched;
`/opt/bale-med-prices` remains clean. The OpenClaw image increased root disk
use to 95%, with about 1.2 GiB free, so capacity cleanup is a near-term task.

`/opt/bale-auto` is owned by `ubuntu:ubuntu` with mode `0750` and now contains
the deployed Compose definition, policy/checker files, ignored `.env`, and
persistent OpenClaw state. The gateway health endpoint returns
`{"ok":true,"status":"live"}`. Continue with
`docs/runbooks/SERVER_PREPARATION_CHECKLIST.md` and
`docs/runbooks/OPENCLAW_POC.md`; re-check time-sensitive facts before changes.

The first interactive OAuth attempt left stale Docker metadata named
`bale-auto-openclaw-cli-run-59373805309a`. containerd reports no live task, but
Docker removal blocks. Do not restart the shared Docker daemon solely for this;
clear it during an appropriate maintenance window. The gateway remains healthy.

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

1. Refresh the GitHub state and verify the verification branch/PR:
   ```powershell
   gh auth status
   gh pr view 1 --repo hosseintajdari/bale-auto
   ```
2. Publish and merge the health-checker/documentation correction after CI.
3. Close or update GitHub Issues #3 through #9 using the verified deployment
  and end-to-end run evidence; keep #10 open for post-PoC work.
4. Update the Notion Project record with the stable deployed/tested state and
  GitHub links; do not copy secrets or raw logs.
5. Prioritize a safe disk-capacity review. Preserve BaleMed/BaleMedPrices,
  `/backup`, 3x-ui, WARP, Git data, and operational backups.

## Handoff report format

For every completed session, report:

1. What was done.
2. What was learned, including a short explanation of any new technical term.
3. Evidence: commands, run URLs, commit IDs, or read-only observations.
4. Blocker or owner decision required.
5. The next safe step.
