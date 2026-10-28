"""Minimal Telegram Bot API client (stdlib only).

Long-polling getUpdates + sendMessage + inline keyboards — everything the
supporter and owner panels need, in the same dependency-free style as the
rest of this repository.
"""
import json
import urllib.request


class TgClient:
    def __init__(self, token, api_base="https://api.telegram.org", timeout=35):
        self.base = api_base.rstrip("/") + "/bot" + token
        self.timeout = timeout

    def call(self, method, **params):
        data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(
            self.base + "/" + method, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        if not body.get("ok"):
            raise RuntimeError("telegram api error: " + str(body.get("description")))
        return body.get("result")

    def get_updates(self, offset=None, timeout=25):
        params = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            params["offset"] = offset
        return self.call("getUpdates", **params)

    def send_message(self, chat_id, text, reply_markup=None):
        params = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return self.call("sendMessage", **params)

    def answer_callback(self, callback_query_id, text=""):
        return self.call("answerCallbackQuery", callback_query_id=callback_query_id, text=text)


def inline_keyboard(rows):
    """rows: list of lists of (label, callback_data)."""
    return {"inline_keyboard": [[{"text": label, "callback_data": data} for label, data in row] for row in rows]}


def run_polling(client, handler):
    """handler(update) -> None. Offset bookkeeping lives here."""
    offset = None
    while True:
        for upd in client.get_updates(offset=offset):
            offset = upd["update_id"] + 1
            handler(upd)
