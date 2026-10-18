"""GitHub-backed write-ahead ledger for opt-in Telegram delivery.

No code in the preview workflow supplies a GitHub write token or Telegram secrets.
A 'sending' part is deliberately NOT retried automatically: Telegram's sendMessage
has no idempotency key, so a timeout can mean the message arrived.
"""
import base64
import datetime as dt
import json
from pathlib import Path

import requests

LEDGER_PATH = "state/live_ledger.json"
MAX_LEDGER_BYTES = 900_000


class DeliveryUncertain(RuntimeError):
    """A previously attempted Telegram send needs human reconciliation."""


class LedgerConflict(RuntimeError):
    """A concurrent or ambiguous GitHub state update must fail closed."""


class GitHubLedger:
    def __init__(self, repository, token, branch="main", transport=requests):
        if not repository or repository.count("/") != 1 or not token:
            raise ValueError("Writable GitHub repository and token are required")
        self.repository = repository
        self.token = token
        self.branch = branch
        self.transport = transport
        self.url = f"https://api.github.com/repos/{repository}/contents/{LEDGER_PATH}"
        self.sha = None
        self.slots = {}

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"}

    def load(self):
        response = self.transport.get(
            self.url, params={"ref": self.branch}, headers=self._headers(), timeout=20)
        if response.status_code == 404:
            self.sha, self.slots = None, {}
            return
        response.raise_for_status()
        payload = response.json()
        if payload.get("encoding") != "base64" or not payload.get("sha"):
            raise LedgerConflict("Unsupported GitHub ledger content")
        decoded = base64.b64decode(payload["content"])
        if len(decoded) > MAX_LEDGER_BYTES:
            raise LedgerConflict("Ledger is too large")
        state = json.loads(decoded)
        if state.get("version") != 1 or not isinstance(state.get("slots"), dict):
            raise LedgerConflict("Invalid ledger structure")
        self.sha, self.slots = payload["sha"], state["slots"]

    def save(self):
        data = json.dumps({"version": 1, "slots": self.slots},
                          ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(data) > MAX_LEDGER_BYTES:
            raise LedgerConflict("Ledger exceeds safe GitHub Contents API size")
        body = {"message": "Record Telegram delivery state [skip ci]",
                "content": base64.b64encode(data).decode("ascii"),
                "branch": self.branch}
        if self.sha:
            body["sha"] = self.sha
        try:
            result = self.transport.put(
                self.url, headers=self._headers(), json=body, timeout=20)
        except requests.RequestException as exc:
            raise LedgerConflict("GitHub ledger update outcome uncertain") from exc
        if result.status_code in (409, 422):
            raise LedgerConflict("GitHub ledger conflict; stop instead of resending")
        result.raise_for_status()
        if result.status_code not in (200, 201):
            raise LedgerConflict("Unexpected GitHub ledger response")
        sha = result.json().get("content", {}).get("sha")
        if not sha:
            raise LedgerConflict("GitHub did not confirm ledger revision")
        self.sha = sha

    def prune(self, now, keep_days=14):
        """Remove old slots only. Confirmed parts are compacted immediately."""
        cutoff = now.date() - dt.timedelta(days=keep_days)
        for key in list(self.slots):
            try:
                date = dt.date.fromisoformat(key.split(":", 1)[1][:10])
            except (IndexError, ValueError):
                raise LedgerConflict("Malformed ledger slot identifier")
            if date < cutoff:
                record = self.slots[key]
                # An ambiguous Telegram result must never be silently forgotten.
                # Otherwise a later run could reuse the same article after pruning.
                if not isinstance(record, dict) or not isinstance(record.get("parts"), list):
                    raise LedgerConflict("Malformed ledger record; cannot safely prune")
                if any(not isinstance(part, dict) or part.get("status") != "sent"
                       for part in record["parts"]):
                    continue
                del self.slots[key]

    def claimed_articles(self, region):
        return {identifier
                for key, data in self.slots.items() if key.startswith(region + ":")
                for identifier in data["article_ids"]}

    def claim(self, slot, article_ids, chunks, now):
        """Persist the whole message BEFORE any Telegram request."""
        if slot in self.slots:
            return False
        if not slot.startswith(("RO:", "FR:")) or not article_ids or not chunks:
            raise ValueError("Valid country slot, article ids and chunks required")
        region = slot.split(":", 1)[0]
        if set(article_ids) & self.claimed_articles(region):
            raise LedgerConflict("Already claimed article in this country")
        if any(not isinstance(x, str) or not 0 < len(x) <= 4000 for x in chunks):
            raise ValueError("Invalid Telegram message part")
        self.slots[slot] = {
            "created_at": now.isoformat(),
            "article_ids": list(dict.fromkeys(article_ids)),
            "parts": [{"status": "pending", "text": text, "telegram_message_id": None}
                      for text in chunks],
        }
        self.save()
        return True

    def resume(self, slot, send_part):
        """Send pending chunks; never re-attempt a potentially delivered chunk."""
        record = self.slots[slot]
        if any(p["status"] == "sending" for p in record["parts"]):
            raise DeliveryUncertain(f"Manual reconciliation required for {slot}")
        for part in record["parts"]:
            if part["status"] == "sent":
                continue
            if part["status"] != "pending":
                raise LedgerConflict(f"Unknown delivery status in {slot}")
            # Write-ahead claim ensures crash/timeout cannot trigger automatic duplicate.
            part["status"] = "sending"
            self.save()
            result = send_part(part["text"])
            if not isinstance(result, int) or isinstance(result, bool) or result < 1:
                raise DeliveryUncertain(f"Telegram receipt missing for {slot}")
            part["status"] = "sent"
            part["telegram_message_id"] = result
            part.pop("text", None)  # Compact safely after confirmed Telegram receipt.
            self.save()
        return True

    def unfinished_slots(self, region):
        return sorted(
            key for key, entry in self.slots.items()
            if key.startswith(region + ":")
            and any(p["status"] != "sent" for p in entry["parts"])
        )


def send_telegram_part(token, chat_id, message, transport=requests):
    """Return a verified Telegram message_id; missing/ambiguous receipts fail closed."""
    try:
        response = transport.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
            timeout=25)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        # requests includes the bot token in URL-bearing exception messages.
        # Suppress exception chaining so logs never print that secret.
        raise DeliveryUncertain("Telegram send failed or timed out; delivery must be reconciled") from None
    result = payload.get("result") or {}
    identifier = result.get("message_id")
    if payload.get("ok") is not True or type(identifier) is not int or identifier < 1:
        raise DeliveryUncertain("Telegram did not return a valid message id")
    return identifier
