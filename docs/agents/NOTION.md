# Notion Routing for External Agents

## Source-of-truth split

- **Git and GitHub:** source of truth for implementation, branches, commits,
  pull requests, checks, and issue-level engineering work.
- **Notion Projects and Milestones:** project direction, stable status, gates,
  blockers, and critical path.
- **Notion Docs:** PRD, specification, ADR, security model, and runbook. Store
  the repository path and GitHub URL when they exist.
- **Notion Knowledge:** durable decisions, architecture, FAQ, and reusable
  learning.
- **Notion Glossary:** standalone technical vocabulary only.
- **Ship Log:** an actual deployment or release result, never a planned one.

## External-agent write protocol

1. Collect evidence during the session without writing partial conclusions.
2. Choose the destination by content type; do not create a duplicate record
   merely because the correct page is not immediately visible.
3. Fetch the target page first. For a database record, fetch its schema and
   preserve required properties and relations.
4. Write only verified facts. Mark an inference as an inference and preserve
   links to the underlying GitHub run, pull request, commit, or document.
5. Read the target again after writing and verify title, status, relations,
   literal paths, and URLs.

## bale-auto targets

- Project status page: https://app.notion.com/p/3b9f6d55a67381cf9c21ce1014da7f82
- Approved PRD reference: https://app.notion.com/p/3b7834f066298137a6e6fec4244fe141
- Draft PR #1: https://github.com/hosseintajdari/bale-auto/pull/1

The approved PRD reference may return `object_not_found` to an integration.
Treat that as an access limitation, not proof that the PRD is missing; preserve
the link and do not create a replacement without owner direction.

## Update threshold

Update the Project record after a stable change to a gate, milestone, blocker,
or deployment state. Do not add raw command output, daily notes, or a full CI
log. A passing or failing `CI` gate may be summarized with its run URL and the
effect on the next decision.
