## Summary

Describe the user-visible or operational outcome.

## Scope

List the files, policy, service, or documentation changed.

## Risk and safety boundary

Describe the highest-risk behavior and the guardrail that contains it.

- [ ] No arbitrary shell execution was added.
- [ ] No live secret or environment value was added to Git, tests, or logs.
- [ ] No public administrative endpoint was added.
- [ ] No BaleMed or BaleMedPrices path, service, secret, or resource is touched.

## Verification

Provide the exact commands run and summarize their results without sensitive
values.

- [ ] Python compilation passed.
- [ ] Python linting passed.
- [ ] Unit tests passed.
- [ ] Policy validation passed.
- [ ] Secret scanning passed.
- [ ] Whitespace validation passed.

## Server effect

State `none` or list every intended host mutation and its approval gate.

## Rollback

Explain how to return to the previous Git or immutable release revision.

## Agent handoff

- [ ] `docs/agents/HANDOFF.md` was updated with a verified project-state change.
- [ ] Or, no handoff update is needed because this pull request does not change
      a gate, safety boundary, deployment state, or next safe step.
