# Conversational Work Ledger — synthetic P0 on ct

The current project is `/home/admin/bale-auto` on the Linux server `ct`.
This is a transferred directory, not a Git checkout. No GitHub publication is
part of this work. The active checkpoint is `docs/agents/HANDOFF.md`.

## Run and review

From the project directory:

```bash
python3 -m unittest discover -s tests -v
python3 run_p0_review.py
```

The second command runs the suite, executes an asserted demonstration and writes
`work/p0_evidence/tests.log`, `test_results.json`, `P0_DEMO_FA.md` and
`P0_SCENARIO_COVERAGE.md`. Terminal output contains English status and counts,
not the Persian conversation. Python 3.12.3 and its standard library suffice.

## Current implementation

`src/p0_core.py` is a synthetic, in-memory state machine. It supports independently
confirmed money, memo, task, reminder, preference and relationship candidates;
unit/classification clarification; explicit draft revision; duplicate choice;
linked record correction; confirmed deletion; scoped retrieval; private reminder
lists and date-bounded cash-sales aggregation in rial. Draft source/fields are
purged on resolution. Expiry is 24 hours in this demonstration, swept lazily at
the next operation. The 30-day keyed-hash deletion marker uses an ephemeral key.
The key and all state disappear on process exit; nothing is durable across restart.

The parser accepts narrowly structured Persian text such as `دریافت ۵۰۰ تومان فروش`
or `یادداشت: قیمت قطعه`. Unknown classifications need a choice. A missing unit
is never inferred from a preference. Compound objects require separate lines or
semicolons. Ambiguous/unsupported text returns a manual-clarification response.
Dates are explicit Gregorian ISO dates; an omitted payment date defaults to the
UTC receipt date in this proof. No Jalali/relative-date or voice interpretation is
claimed. Preferences and relationships are stored only as confirmed objects;
automatic learned rules, relationship resolution and task completion are not
implemented. Corrections/deletion/retrieval are invoked through the test harness,
not a complete natural-language user interface.

The signed adapter demonstrates only inbound text authentication in-process.
No HTTP listener, LangBot plugin, live model, WhatsApp/Telegram connection,
database, encrypted storage or backup is created. This is not ready for real data.

`tests/test_p0_acceptance.py` maps 50 prior design scenarios to bounded contract
assertions and adds quantitative and adversarial tests. These are not 50 field
validated or full natural-language conversations. Refer to the coverage artifact.

## Preserved earlier work

`src/ledger.py`, `tests/test_p0_contract.py`, `demo_p0.py` and
`p0_synthetic_flow.js` are preserved historical prototypes. The old Python
amount parser concatenates all digits and its test loop does not detect that
failure; do not use it as the current core. `src/p0_core.py` and the review runner
are now the documented P0 entry points. The previous README and handoff are
preserved under `docs/agents/history/`.

## Phase gate

Technical synthetic evidence is ready for owner review once the recorded suite
passes. P0 is not accepted/closed until the owner reviews the demonstration and
privacy/consent draft. The actual LangBot route remains unverified for safe writes;
use the PRD synthetic fallback. Real-message P1 requires separate authorization,
completed privacy facts, consent and a validated channel/storage/restore path.
