"""Inspect delivery metadata or record a manually verified Telegram receipt.

Credentials come from the environment; message bodies and tokens are never printed.
This command never sends Telegram messages and never blindly resets an unknown send.
"""
import argparse
import datetime as dt
import json
import os

from delivery_ledger import GitHubLedger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot")
    parser.add_argument("--part", type=int, help="Zero-based part index")
    parser.add_argument("--expected-sha")
    parser.add_argument("--message-id", type=int)
    parser.add_argument("--note")
    parser.add_argument("--confirm-receipt", action="store_true")
    parser.add_argument("--abandon-slot", action="store_true",
                        help="Cancel remaining parts without retry; accepts possible non-delivery")
    args = parser.parse_args()
    write_args = (args.slot, args.part, args.expected_sha, args.message_id, args.note)
    if args.confirm_receipt and args.abandon_slot:
        parser.error("Choose receipt confirmation or abandonment, not both")
    if args.confirm_receipt and any(value is None for value in write_args):
        parser.error("Receipt confirmation requires slot, part, expected-sha, message-id and note")
    if args.abandon_slot and (not args.slot or not args.expected_sha or not args.note
                             or args.part is not None or args.message_id is not None):
        parser.error("Abandonment requires only slot, expected-sha and note")
    if not args.confirm_receipt and not args.abandon_slot and any(value is not None for value in write_args):
        parser.error("Run without arguments to inspect, or use --confirm-receipt with all fields")
    ledger = GitHubLedger(os.environ["GITHUB_REPOSITORY"], os.environ["DELIVERY_GITHUB_TOKEN"])
    ledger.load()
    if args.confirm_receipt:
        ledger.reconcile(args.slot, args.part, args.expected_sha, args.message_id,
                         args.note, dt.datetime.now(dt.timezone.utc))
    elif args.abandon_slot:
        ledger.abandon(args.slot, args.expected_sha, args.note, dt.datetime.now(dt.timezone.utc))
    print(json.dumps({"revision": ledger.sha, "slots": {
        key: {"created_at": entry["created_at"], "parts": [
            {"index": i, "status": part["status"],
             "telegram_message_id": part.get("telegram_message_id")}
            for i, part in enumerate(entry["parts"])]}
        for key, entry in ledger.slots.items()}}, indent=2))


if __name__ == "__main__":
    main()
