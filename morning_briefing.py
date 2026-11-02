"""
FDE Week 2 - Morning briefing script (acceptance demo, no model call).

Reads today's schedule + open todos straight from concierge_data.json
(next to this script), and unread mail via concierge.read_mail().
It does NOT call the LLM, so ZHIPU_API_KEY is not needed for the
calendar/todo sections. For the mail section, run it in the same
PowerShell window where MAIL_ADDRESS / MAIL_AUTH_CODE are set.

Usage (PowerShell, with .venv activated, next to concierge.py):
    python morning_briefing.py
"""

import json
import sys
from datetime import date
from pathlib import Path

DATA_FILE = Path(__file__).with_name("concierge_data.json")


def load_data():
    if not DATA_FILE.exists():
        return None
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print("Could not read %s: %s" % (DATA_FILE.name, e))
        return None


def event_label(e):
    if e.get("title"):
        return e["title"]
    parts = [e.get("topic", ""), e.get("person", "")]
    return " ".join(p for p in parts if p) or "(untitled)"


def main():
    today = date.today().isoformat()
    print("=== Morning briefing - %s ===" % today)

    data = load_data()
    if data is None:
        print("\n[Schedule] No concierge_data.json found next to this "
              "script - run concierge.py once first, or copy this "
              "script next to concierge.py.")
        print("\n[Todos] Skipped (no data file).")
    else:
        events = [e for e in data.get("calendar", [])
                  if e.get("date") == today]
        events.sort(key=lambda e: e.get("time", ""))
        print("\n[Today's schedule]")
        if events:
            for e in events:
                print("  %s  %s" % (e.get("time", ""), event_label(e)))
        else:
            print("  Nothing scheduled today.")

        todos = [t for t in data.get("todos", []) if not t.get("done")]
        print("\n[Open todos]")
        if todos:
            for t in todos:
                print("  #%s  %s" % (t.get("id", ""), t.get("title", "")))
        else:
            print("  No open todos.")

    print("\n[Unread mail]")
    try:
        from concierge import read_mail
        print(" ", read_mail())
    except Exception as e:
        print("  Mail skipped: %s" % e)
        print("  (Calendar/todos above still work. For mail, run this "
              "in the PowerShell window where MAIL_ADDRESS and "
              "MAIL_AUTH_CODE are set, next to concierge.py.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
