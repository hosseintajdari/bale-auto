"""Telegram bot: the OWNER panel — a separate bot from the supporter's.

Owner level only (OWNER_TELEGRAM_ID): global stats, every user with their
supporter, supporter management (define / activate / deactivate) and plan
changes. The supporter never sees this bot; his bot is scoped to his own
rows. User-facing text is Persian (UX text); code and docs stay English.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support_store import SupportStore
from tg_client import TgClient, inline_keyboard, run_polling

NL = chr(10)
WELCOME = "پنل مالک. نمای کامل توزیع: آمار، همه‌ی کاربرها، پشتیبان‌ها."
DENIED = "این پنل فقط برای مالک است."
PLANS = [("free_full", "ماه رایگان (فول)"), ("ledger_499", "دفتر ۴۹۹"),
         ("accountant_999", "حسابدار صنف ۹۹۹"), ("agent_1099", "ارتباطی ۱٬۰۹۹")]
PLAN_NAMES = dict(PLANS)

MENU = inline_keyboard([
    [("📊 آمار کلی", "stats"), ("👥 همه کاربران", "all_users")],
    [("🧑‍🤝‍🧑 پشتیبان‌ها", "supporters"), ("➕ تعریف پشتیبان", "new_supporter")],
    [("🎚 تغییر پلن کاربر", "change_plan")],
])


class OwnerPanel:
    """Pure panel logic, unit-testable like SupporterPanel."""

    def __init__(self, store, owner_tg_id):
        self.store = store
        self.owner_tg_id = int(owner_tg_id)
        self.sessions = {}

    def _ok(self, tg_id):
        return int(tg_id) == self.owner_tg_id

    def handle_text(self, tg_id, text):
        if not self._ok(tg_id):
            return [(DENIED, None)]
        text = (text or "").strip()
        if text in ("/start", "شروع"):
            self.sessions.pop(tg_id, None)
            return [(WELCOME, MENU)]
        flow = self.sessions.get(tg_id)
        if flow:
            return self._flow_text(tg_id, flow, text)
        return [("از دکمه‌های پنل انتخاب کن:", MENU)]

    def handle_callback(self, tg_id, data):
        if not self._ok(tg_id):
            return [(DENIED, None)]
        if data == "stats":
            g = self.store.global_stats()
            txt = (f"📊 آمار کلی" + NL + f"پشتیبان: {g['supporters']}" + NL
                   + f"کاربر: {g['users']}" + NL + f"معرفی ثبت‌شده: {g['referrals']}")
            return [(txt, MENU)]
        if data == "all_users":
            return [(self._all_users_text(), MENU)]
        if data == "supporters":
            return [(self._supporters_text(), self._supporters_keyboard())]
        if data == "new_supporter":
            self.sessions[tg_id] = {"kind": "new_supporter", "step": "tg_id", "data": {}}
            return [("آیدی عددی تلگرام پشتیبان را بفرست:", None)]
        if data == "change_plan":
            self.sessions[tg_id] = {"kind": "change_plan", "step": "user_id", "data": {}}
            return [("شماره‌ی کاربر را بفرست:", None)]
        if data.startswith("sup_toggle:"):
            sid = int(data.split(":", 1)[1])
            sup = next((s for s in self.store.list_supporters() if s["id"] == sid), None)
            if sup:
                self.store.set_supporter_active(sid, not sup["active"])
                sup = next(s for s in self.store.list_supporters() if s["id"] == sid)
                state = "فعال" if sup["active"] else "غیرفعال"
                return [(f"پشتیبان «{sup['name']}» {state} شد.", MENU)]
            return [("پشتیبان پیدا نشد.", MENU)]
        if data.startswith("plan:"):
            flow = self.sessions.get(tg_id)
            if flow and flow["kind"] == "change_plan":
                plan = data.split(":", 1)[1]
                self.store.set_user_plan(flow["data"]["user_id"], plan)
                user = self.store.get_user(flow["data"]["user_id"])
                self.sessions.pop(tg_id, None)
                return [(f"✅ پلن {user['full_name']} شد: {PLAN_NAMES.get(plan, plan)}", MENU)]
            return [(WELCOME, MENU)]
        return [(WELCOME, MENU)]

    def _flow_text(self, tg_id, flow, text):
        if flow["kind"] == "new_supporter":
            if flow["step"] == "tg_id":
                if not text.isdigit():
                    return [("آیدی باید عدد باشد؛ دوباره بفرست:", None)]
                flow["data"]["tg_id"] = int(text)
                flow["step"] = "name"
                return [("نام پشتیبان را بفرست:", None)]
            if flow["step"] == "name":
                sup = self.store.add_supporter(flow["data"]["tg_id"], text)
                self.sessions.pop(tg_id, None)
                return [(f"✅ پشتیبان تعریف شد: {sup['name']} (تلگرام {sup['telegram_id']}). "
                         + "حالا او می‌تواند بات پشتیبان را باز کند و کاربر تعریف کند.", MENU)]
        if flow["kind"] == "change_plan":
            if flow["step"] == "user_id":
                if not text.isdigit() or not self.store.get_user(int(text)):
                    return [("کاربر پیدا نشد؛ شماره‌ی درست را بفرست:", None)]
                flow["data"]["user_id"] = int(text)
                kb = inline_keyboard([[(label, "plan:" + key)] for key, label in PLANS])
                user = self.store.get_user(int(text))
                return [(f"پلن تازه برای {user['full_name']} (الان: {PLAN_NAMES.get(user['plan'], user['plan'])}):", kb)]
        self.sessions.pop(tg_id, None)
        return [(WELCOME, MENU)]

    def _all_users_text(self):
        users = self.store.list_users()
        if not users:
            return "هنوز کاربری نیست."
        sups = {s["id"]: s["name"] for s in self.store.list_supporters()}
        lines = ["👥 همه کاربران:"]
        for u in users:
            refs = self.store.referral_count(u["id"])
            lines.append(
                f"{u['id']}. {u['full_name']} — {u['shop_name']} ({u['guild']})" + NL
                + f"   پشتیبان: {sups.get(u['supporter_id'], '?')} · پلن: {PLAN_NAMES.get(u['plan'], u['plan'])}" + NL
                + f"   کد: {u['referral_code']} · معرفیِ فعال: {refs} · موبایل: {u['phone']}")
        return NL.join(lines)

    def _supporters_text(self):
        sups = self.store.list_supporters()
        if not sups:
            return "پشتیبانی تعریف نشده."
        lines = ["🧑‍🤝‍🧑 پشتیبان‌ها (برای فعال/غیرفعال‌کردن روی دکمه بزن):"]
        for s in sups:
            st = self.store.supporter_stats(s["id"])
            state = "فعال" if s["active"] else "⛔ غیرفعال"
            lines.append(f"{s['id']}. {s['name']} — {state} · کاربر: {st['users_defined']} · فعال: {st['users_active']}")
        return NL.join(lines)

    def _supporters_keyboard(self):
        rows = [[(("⛔ غیرفعال کن: " if s["active"] else "✅ فعال کن: ") + s["name"], f"sup_toggle:{s['id']}")]
                for s in self.store.list_supporters()]
        return inline_keyboard(rows) if rows else MENU


def main():
    token = os.environ["OWNER_BOT_TOKEN"]
    owner_id = os.environ["OWNER_TELEGRAM_ID"]
    store = SupportStore(os.environ.get("SUPPORT_DB_PATH", "data/support.db"),
                         os.environ.get("LEDGER_DB_PATH") or None)
    panel = OwnerPanel(store, owner_id)
    client = TgClient(token)

    def handler(upd):
        msg = upd.get("message") or {}
        cb = upd.get("callback_query") or {}
        if cb:
            replies = panel.handle_callback(cb["from"]["id"], cb.get("data", ""))
            client.answer_callback(cb["id"])
            chat_id = cb["message"]["chat"]["id"]
        elif msg:
            replies = panel.handle_text(msg["from"]["id"], msg.get("text", ""))
            chat_id = msg["chat"]["id"]
        else:
            return
        for text, markup in replies:
            client.send_message(chat_id, text, reply_markup=markup)

    run_polling(client, handler)


if __name__ == "__main__":
    main()
