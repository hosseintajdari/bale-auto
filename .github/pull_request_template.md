## Summary

Describe the change and why it is needed.

## Scope and safety

- [ ] This change stays within the documented P0 scope.
- [ ] All test inputs are synthetic; no real financial or private data is included.
- [ ] No credentials, generated evidence, environment files, or service configuration are included.
- [ ] Confirmation, ownership, unit preservation, idempotency, and deletion behavior remain intact (or are explicitly discussed below).

## Verification

```text
python3 -m unittest discover -s tests -v
python3 run_p0_review.py
git diff --check
```

Result:

## Notes for reviewers

Call out product-contract, privacy, retention, workflow, or compatibility risks.
