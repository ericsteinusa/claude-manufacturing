#!/usr/bin/env python3
"""Post a message to a Microsoft Teams channel via an incoming webhook.

The webhook URL is read from the ``TEAMS_WEBHOOK_URL`` environment variable
so the secret never lives in the repo. Create the URL in Teams with the
"Post to a channel when a webhook request is received" Workflows template.

Usage:
    export TEAMS_WEBHOOK_URL='https://...'           # in your shell profile
    python3 scripts/post_to_teams.py "Title" message.md
    echo "body text" | python3 scripts/post_to_teams.py "Title"

The message body is sent as an Adaptive Card TextBlock, which renders a
subset of Markdown (bold, links, bullet lists). Body comes from the file
argument if given, otherwise from stdin.
"""
import json
import os
import sys
import urllib.error
import urllib.request


def build_card(title: str, body: str) -> dict:
    card_body = []
    if title:
        card_body.append({
            "type": "TextBlock",
            "text": title,
            "weight": "Bolder",
            "size": "Large",
            "wrap": True,
        })
    card_body.append({"type": "TextBlock", "text": body, "wrap": True})
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": card_body,
            },
        }],
    }


def main() -> int:
    url = os.environ.get("TEAMS_WEBHOOK_URL")
    if not url:
        sys.stderr.write(
            "TEAMS_WEBHOOK_URL is not set. Add it to your shell profile:\n"
            "  export TEAMS_WEBHOOK_URL='https://...'\n")
        return 2

    title = sys.argv[1] if len(sys.argv) > 1 else ""
    if len(sys.argv) > 2:
        with open(sys.argv[2], encoding="utf-8") as fh:
            body = fh.read()
    else:
        body = sys.stdin.read()
    if not body.strip():
        sys.stderr.write("No message body (pass a file or pipe via stdin).\n")
        return 2

    payload = json.dumps(build_card(title, body)).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Posted to Teams: HTTP {resp.status}")
            return 0
    except urllib.error.HTTPError as exc:
        sys.stderr.write(f"Teams webhook returned HTTP {exc.code}: "
                         f"{exc.read().decode('utf-8', 'replace')}\n")
        return 1
    except urllib.error.URLError as exc:
        sys.stderr.write(f"Could not reach Teams webhook: {exc.reason}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
