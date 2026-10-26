# Conversational Work Ledger

<div align="center">

**A private, Persian-first conversational work ledger for chat and Bale Messenger.**

[English](README.md) • [فارسی](README.fa.md)

</div>

---

A private, Persian-first work ledger for capturing payments, commitments, and work notes directly from chat. Incoming messages are staged as editable drafts; records are durably committed only after explicit user confirmation.

## Status

Development prototype for synthetic evaluation. The review suite passed 103 tests
on 2026-10-26; this does not establish live channel or production readiness.
Owner acceptance, real-data consent, and persistent message-retention rules are
still pending. Conversation-engine consolidation ([#35](https://github.com/hosseintajdari/bale-auto/issues/35))
and audit-history/retention design ([#38](https://github.com/hosseintajdari/bale-auto/issues/38))
remain open. Use synthetic data until those boundaries are settled.

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
  - Can emit shadow traces to the monitoring panel (`Bale-Panel`) only when explicitly enabled; traces include raw message text and identifiers.
- **Persistence & Session Management (`ledger` & `conversation`):**
  - Isolated SQLite storage for users and conversations.
  - Net balance calculation and formatted Persian numeral currency summaries.
  - Multi-turn conversation state machine with safe concurrency locks.
- **Strict Privacy Isolation:**
  - The synthetic P0 core purges its raw draft content on resolution. The SQLite bot's message-history retention remains a separate open design item; do not assume it provides the same purge guarantee.
  - Scoped multi-tenant boundary based on `(bot_id, platform, user_id)`.

## Project Map

- `src/bazaar_parser.py` — Bazaar NLP parser for colloquial Persian trade expressions.
- `src/bale_bot.py` — Live Bale messenger bot client with inline keyboards and telemetry.
- `src/ledger.py` — SQLite ledger engine, balance calculations, and Persian currency formatting.
- `src/conversation.py` — Multi-turn conversation service and draft transaction storage.
- `src/p0_core.py` — Core zero-dependency state machine, verification rules, and scoping.
- `tests/` — Automated acceptance, adversarial-input, contract-invariant, and persona-simulation checks.
- `docs/` — Product specifications, scenario catalogs, and architectural records.

## Quick Start

Python 3.11+ is supported with standard library defaults.

### 1. Run Tests and Review Suite

```bash
# Run unit and acceptance tests
python3 -m unittest discover -s tests -v

# Run P0 review generator
python3 run_p0_review.py
```

### 2. Run the Bale Bot

Configure your bot credentials in `.env` or `.env.local`:

```env
BALE_BOT_TOKEN="your_bale_bot_token_here"
PANEL_BASE_URL="http://localhost:3001"
PANEL_API_SECRET="set_a_private_panel_api_secret"
# Panel emission transmits raw message text and identifiers; default is disabled.
# ENABLE_PANEL_EMIT=1
```

Start the bot:

```bash
python3 src/bale_bot.py
```

## Contributing & Security

- See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request guidelines and contribution contracts.
- See [SECURITY.md](SECURITY.md) for security boundaries and vulnerability reporting.
- Read documentation in Persian: [README.fa.md](README.fa.md).
