# Conversational Work Ledger — project instructions

## Entry and authority

This project's execution root is `/home/admin/bale-auto` on Linux host `ct`.
Before resuming work, read `docs/agents/HANDOFF.md` for current evidence, phase
and next outcome, then `README.md` for execution commands. Product decisions
belong in `docs/product/CONVERSATIONAL_WORK_LEDGER_PRD.md`.

The owner may control the agent from Windows, iPhone, iPad or a server CLI.
Verify the actual execution host and directory on each new session. A shared
account, conversation or sidebar placement does not establish host access.

## Cross-environment continuity

The Windows entry point is `C:\Users\hosse\Documents\ChatGPT\bale-auto`.
Its `docs/agents/HANDOFF.md` routes to this server; `docs/agents/ct-state/`
contains explicit read-only snapshots refreshed by `scripts/Sync-CtProjectState.ps1`.
The server handoff is authoritative. Snapshot timestamps and hashes describe a
point in time, not automatic synchronization. If server access is unavailable,
use snapshots for context only and report the connection gap before implementation.

Keep code changes and tests in this execution root. Coordinate one writer at a
time; reread files before replacing them if another client may have worked.
After substantive work, update the server handoff with evidence and one next
outcome. Refresh Windows state snapshots when that client is available.

Windows `checkout/`, transfer packages and old OpenClaw material remain separate
historical copies. Copying status does not authorize merging or overwriting code.
Git history, publication and external-system changes need their own authorization.

## Working boundaries

Use synthetic data until the current phase gate permits real content. Preserve
independent confirmation, explicit rial/toman units, ownership and idempotency.
LangBot is the channel runtime; Ledger Core owns product rules and records.
Read credentials or private data only when explicitly required and authorized.
Service, SSH/access, dependency, deployment and real-message changes are separate
from ordinary project-file edits. Keep terminal status, code and technical docs
in English; Persian belongs in user conversation and requested UX/consent text.

Global agent preferences belong outside this file. Project status belongs in
the handoff. After changing agent instructions, use a new task to reload them.
