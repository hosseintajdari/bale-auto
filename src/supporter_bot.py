"""Telegram bot for the local supporter (distribution layer).

The supporter's own level, nothing above it:
- define new shop users (the onboarding entry point),
- see HIS users only — plan, status, referral counts, plan-2 unlocks,
- attach a referral code to a user (drives free months + plan 2),
- his own summary.

Access: only telegram_ids registered in the supporters table and active.
The owner never uses this bot; the owner panel is a separate bot.
User-facing text is Persian (UX text); code and docs stay English.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support_store import SupportStore
from tg_client import TgClient, inline_keyboard, run_polling

WELCOME = "سلام! پنل پشتیبان. اینجا کاربر جدید تعریف می‌کنی و کاربرهای خودت را می‌بینی."
DENIED = "این بات برای پشتیبان‌های تعریف‌شده است. اگر پشتیبانی، مالک باید اول تو را تعریف کند."

MENU = inline_keyboard([
    [("➕ تعریف کاربر جدید", "new_user")],
    [("👥 کاربران من", "my_users"), ("🔗 ثبت کد معرفی", "attach_ref")],
    [("📊 وضعیت من", "my_stats")],
])

PLAN_NAMES = {"free_full": "ماه رایگان (فول)", "ledger_499": "دفتر ۴۹۹",
              "accountant_999": "حسابدار صنف ۹۹۹", "agent_1099": "ارتباطی ۱٬۰۹۹"}
STATUS_NAMES = {"defined": "تعریف‌شده", "active": "فعال", "paused": "متوقف"}


class SupporterPanel:
    """Pure panel logic: (telegram_id, text/callback) -> replies.

    replies: list of (text, reply_markup_or_None). No network here, so the
    whole panel is unit-testable.
    """

    def __init__(self, store):
        self.store = store
        self.sessions = {}

    def _supporter(self, tg_id):
        s = self.store.get_supporter_by_tg(tg_id)
        if not s or not s["active"]:
            return None
        return s

    def _menu_reply(self):
        return [(WELCOME, MENU)]

    def handle_text(self, tg_id, text):
        sup = self._supporter(tg_id)
        if sup is None:
            return [(DENIED, None)]
        text = (text or "").strip()
        if text in ("/start", "شروع"):
            self.sessions.pop(tg_id, None)
            return self._menu_reply()
        flow = self.sessions.get(tg_id)
        if flow:
            return self._flow_text(sup, tg_id, flow, text)
        return [("از دکمه‌های پنل انتخاب کن:", MENU)]

    def handle_callback(self, tg_id, data):
        sup = self._supporter(tg_id)
        if sup is None:
            return [(DENIED, None)]
        if data == "new_user":
            self.sessions[tg_id] = {"kind": "new_user", "step": "full_name", "data": {}}
            return [("نام و نام خانوادگی صاحب مغازه را بفرست:", None)]
        if data == "my_users":
            return [(self._users_text(sup), MENU)]
        if data == "my_stats":
            st = self.store.supporter_stats(sup["id"])
            txt = ("📊 وضعیت تو" + chr(10)
                   + f"کاربر تعریف‌شده: {st['users_defined']}" + chr(10)
                   + f"کاربر فعال: {st['users_active']}" + chr(10)
                   + f"پلن ۲ بازشده بین کاربرهات: {st['plan2_unlocked']}")
            return [(txt, MENU)]
        if data == "attach_ref":
            self.sessions[tg_id] = {"kind": "attach_ref", "step": "user_id", "data": {}}
            return [("شماره‌ی کاربر (از فهرست «کاربران من») را بفرست:", None)]
        return self._menu_reply()

    def _flow_text(self, sup, tg_id, flow, text):
        if flow["kind"] == "new_user":
            steps = [
                ("full_name", "نام مغازه را بفرست (اگر ندارد، «-» بفرست):", "shop_name"),
                ("shop_name", "صنفش چیست؟ (مثلاً داروخانه، سوپرمارکت)", "guild"),
                ("guild", "شماره موبایلش را بفرست:", "phone"),
                ("phone", "شناسه یا شماره‌اش در بله را بفرست (اگر نداری «-»):", "bale_ref"),
                ("bale_ref", None, None),
            ]
            for key, prompt, nxt in steps:
                if flow["step"] == key:
                    flow["data"][key] = "" if text == "-" else text
                    if nxt is None:
                        d = flow["data"]
                        user = self.store.add_user(
                            sup["id"], d.get("full_name", ""), d.get("shop_name", ""),
                            d.get("guild", ""), d.get("phone", ""), d.get("bale_ref", ""))
                        self.sessions.pop(tg_id, None)
                        txt = (f"✅ کاربر تعریف شد." + chr(10)
                               + f"شماره کاربر: {user['id']}" + chr(10)
                               + f"نام: {user['full_name']} — {user['shop_name']}" + chr(10)
                               + f"کد معرفی او: {user['referral_code']}" + chr(10)
                               + "پلن شروع: ماه رایگان (فول). این کد را به خودش بده؛ "
                               + "هر کس را با این کد بیاورد، یک ماه رایگان می‌گیرد و با نفر دوم پلن ۲ برایش باز می‌شود.")
                        return [(txt, MENU)]
                    flow["step"] = nxt
                    return [(prompt, None)]
        if flow["kind"] == "attach_ref":
            if flow["step"] == "user_id":
                if not text.isdigit():
                    return [("شماره کاربر باید عدد باشد؛ دوباره بفرست:", None)]
                user = self.store.get_user(int(text))
                if not user or user["supporter_id"] != sup["id"]:
                    self.sessions.pop(tg_id, None)
                    return [("این کاربر مال تو نیست یا وجود ندارد.", MENU)]
                flow["data"]["user_id"] = user["id"]
                flow["step"] = "code"
                return [("کد معرفیِ کسی که او را آورده را بفرست:", None)]
            if flow["step"] == "code":
                ref = self.store.record_referral(text, flow["data"]["user_id"])
                self.sessions.pop(tg_id, None)
                if ref is None:
                    return [("این کد ثبت نشد: یا کد ناشناخته است، یا این کاربر قبلاً معرف دارد، یا کد مال خودش است.", MENU)]
                referrer = self.store.get_user(ref["referrer_user_id"])
                months = self.store.free_months_earned(referrer["id"])
                p2 = " و پلن ۲ هم برایش باز شد 🎉" if self.store.plan2_unlocked(referrer["id"]) else ""
                return [(f"✅ ثبت شد. {referrer['full_name']} تا حالا {months} ماه رایگان از معرفی گرفته{p2}", MENU)]
        self.sessions.pop(tg_id, None)
        return self._menu_reply()

    def _users_text(self, sup):
        users = self.store.list_users(sup["id"])
        if not users:
            return "هنوز کاربری تعریف نکرده‌ای."
        lines = ["👥 کاربران تو:"]
        for u in users:
            refs = self.store.referral_count(u["id"])
            p2 = " · پلن۲ باز" if self.store.plan2_unlocked(u["id"]) else ""
            lines.append(
                f"{u['id']}. {u['full_name']} — {u['shop_name']} ({u['guild']})" + chr(10)
                + f"   پلن: {PLAN_NAMES.get(u['plan'], u['plan'])} · وضعیت: {STATUS_NAMES.get(u['status'], u['status'])}" + chr(10)
                + f"   کد: {u['referral_code']} · معرفی‌کرده: {refs}{p2}")
        return chr(10).join(lines)


def main():
    token = os.environ["SUPPORTER_BOT_TOKEN"]
    store = SupportStore(os.environ.get("SUPPORT_DB_PATH", "data/support.db"))
    panel = SupporterPanel(store)
    client = TgClient(token)

    def handler(upd):
        msg = upd.get("message") or {}
        cb = upd.get("callback_query") or {}
        if cb:
            tg_id = cb["from"]["id"]
            replies = panel.handle_callback(tg_id, cb.get("data", ""))
            client.answer_callback(cb["id"])
            chat_id = cb["message"]["chat"]["id"]
        elif msg:
            tg_id = msg["from"]["id"]
            replies = panel.handle_text(tg_id, msg.get("text", ""))
            chat_id = msg["chat"]["id"]
        else:
            return
        for text, markup in replies:
            client.send_message(chat_id, text, reply_markup=markup)

    run_polling(client, handler)


if __name__ == "__main__":
    main()
