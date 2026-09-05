# LangBot P0 capability record — 2026-09-05

Read-only observation of the owner's `ct` host. No credentials, conversations,
database rows, environment variables or authentication stores were read.
No bot was added, no message sent and no running service reconfigured.

## Runtime evidence

| Capability | Evidence status | Observed evidence / limit |
| --- | --- | --- |
| Target | Verified | Linux; project `/home/admin/bale-auto`; SSH user `admin` |
| Project Git | Verified absent | `git status --short --branch` reports not a repository; this is the transferred package |
| Installed version | Verified from installed source | `/app/pyproject.toml:3`: `4.10.9` |
| Image | Verified | `rockchin/langbot:latest`, image ID `sha256:43ee7bcdc4243dda4132a777697abb34bc9f9fd2a6763149d11ab92fe312185e` |
| Runtime | Verified | `langbot` and `langbot-postgres-1` healthy; `langbot_box` and `langbot_plugin_runtime` running |
| Web panel | Verified response, not authenticated administration | HTTP 200 from `http://127.0.0.1:5300/`; host binding `127.0.0.1:5300` |
| Telegram support | Installed code verified | `src/langbot/pkg/platform/sources/telegram.py`; native update retained as `source_platform_object`; private chat ID used as sender ID |
| Matrix support | Installed code verified | `src/langbot/pkg/platform/sources/matrix.py`; `event.sender`, `room.room_id`, `event.event_id` available in original event objects |
| Reply implementation | Installed code verified only | Telegram `send_message`/reply and Matrix room send/reply functions exist; no live delivery test |
| Bot/pipeline separation | Installed schema verified only | `entity/persistence/bot.py` has workspace, bot, adapter, enabled and pipeline fields; configured bots and actual isolation unknown |
| Configured adapter and enabled bot count | Unknown | Stored configuration may contain credentials; it was not opened |
| Model/provider/retention/pricing | Unknown | Neither model credentials nor session configuration were inspected |
| Backup/restore/encryption | Unknown | No backup or restore tested; no real data permitted by this proof |
| WhatsApp bridging | Unknown live | Matrix support is not proof of a configured or reliable WhatsApp bridge |

## Integration finding: generic webhook is insufficient as-is

Installed `src/langbot/pkg/platform/webhook_pusher.py` constructs a new random
UUID when pushing a person/group event. That UUID is not by itself a stable
platform message identity. The inspected person-message payload includes bot,
adapter, sender, message chain and time, but no explicit conversation field.
The POST code supplies `Content-Type: application/json` without a signature or
authorization header. `entity/persistence/webhook.py` has no dedicated signing
field. No claim is made about an external proxy or a custom plugin not inspected.

The inspected Matrix message converter adds text/image components, while the
original room and event remain in `source_platform_object`; the generic pusher
does not serialize that original object. Thus the generic webhook must not be
treated as proof that the required room/event identity reaches Ledger Core.

Additional out-of-scope limitation: Telegram group conversion currently assigns
`effective_chat.id` to the sender as well as the group. Do not extend this P0 to
group identity handling. P0/P1 remain private-conversation only.

## P0 disposition

Use the synthetic adapter, as required by the PRD fallback. It demonstrates a
versioned, HMAC-signed inbound text envelope, freshness rejection and identity
binding using an explicitly synthetic key. It is an in-process demonstration,
not an installed LangBot plugin, public endpoint or authenticated production
write API. Confirmation/correction/deletion call the core directly from trusted
test code; end-to-end authentication for those actions remains unverified.

Before a real channel trial, a bounded adapter must obtain identities from native
platform events, preserve message identity across retries, authenticate every
core mutation and deliver replies to the correct private conversation. Validate
the exact owner configuration with synthetic traffic after separate channel
authorization. Do not add another bot framework to bypass this gate.
