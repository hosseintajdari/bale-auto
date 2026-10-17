# Conversational Work Ledger

<div align="center">

**A private, Persian-first conversational work ledger for chat and Bale Messenger.**

[English](README.md) • [فارسی](README.fa.md)

</div>

---

A private, Persian-first work ledger for capturing payments, commitments, and work notes directly from chat. Incoming messages are staged as editable drafts; records are durably committed only after explicit user confirmation.

## Key Features

- **Persian Bazaar NLP Engine (`bazaar_parser`):**
  - Understands colloquial Iranian market vocabulary (e.g., `کارت کشید`, `پوز`, `فروش`, `دخل`, `خرید بار`, `خرج ناهار`, `مساعده`).
  - Supports written and spoken Persian number words (`میلیون`, `هزار`, `پونصد`, `دویست`, etc.).
  - Automatic memo and item extraction without tedious back-and-forth prompts.
- **Draft-First Lifecycle & Explicit Confirmation:**
  - No record is created without explicit user confirmation (`تأیید و ثبت`, `حله`, `ثبت کن`).
  - Unambiguous currency handling (`تومان` vs. `ریال`) with no silent, assumed conversions.
- **Live Bale Messenger Bot (`bale_bot`):**
  - Integrates with the official Bale Bot API (`tapi.bale.ai`) using long polling.
  - Interactive inline keyboard markup for single-tap confirmations and quick actions.
  - Emits real-time shadow traces to the monitoring panel (`Bale-Panel`).
- **Persistence & Session Management (`ledger` & `conversation`):**
  - Isolated SQLite storage for users and conversations.
  - Net balance calculation and formatted Persian numeral currency summaries.
  - Multi-turn conversation state machine with safe concurrency locks.
- **Strict Privacy Isolation:**
  - Raw draft content is purged as soon as drafts are resolved or confirmed.
  - Scoped multi-tenant boundary based on `(bot_id, platform, user_id)`.

## Project Map

- `src/bazaar_parser.py` — Bazaar NLP parser for colloquial Persian trade expressions.
- `src/bale_bot.py` — Live Bale messenger bot client with inline keyboards and telemetry.
- `src/ledger.py` — SQLite ledger engine, balance calculations, and Persian currency formatting.
- `src/conversation.py` — Multi-turn conversation service and draft transaction storage.
- `src/p0_core.py` — Core zero-dependency state machine, verification rules, and scoping.
- `tests/` — Automated test suite with 86 tests covering acceptance, adversarial input, contract invariants, and persona simulations.
- `docs/` — Product specifications, scenario catalogs, and architectural records.

## Quick Start

Python 3.11+ is supported with standard library defaults.

### 1. Run Tests and Review Suite

```bash
# Run unit and acceptance tests (86 tests)
python3 -m unittest discover -s tests -v

# Run P0 review generator
python3 run_p0_review.py
```

### 2. Run the Bale Bot

Configure your bot credentials in `.env` or `.env.local`:

```env
BALE_BOT_TOKEN="your_bale_bot_token_here"
SHADOW_TRACE_URL="http://localhost:5000/api/traces"  # optional
```

Start the bot:

```bash
python3 src/bale_bot.py
```

## Contributing & Security

- See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request guidelines and contribution contracts.
- See [SECURITY.md](SECURITY.md) for security boundaries and vulnerability reporting.
- Read documentation in Persian: [README.fa.md](README.fa.md).
