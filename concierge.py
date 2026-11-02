"""
FDE Week 2 - Personal concierge agent.

Kernel = exercise 5's tool loop, upgraded from one fixed round to a
while loop: decide -> execute -> feed back -> decide again, until the
model answers without calling a tool (or we hit MAX_TURNS).

Day 1 (done 2026-10-29): all tools were stubs; the fake-data chain
  check_free -> create_event -> draft_mail -> create_todo
ran end to end and passed acceptance.
Day 2 (this version): calendar + todos are REAL - they persist in
concierge_data.json next to this script, so data survives restarts.
Mail tools (read_mail / draft_mail / send_mail) are still stubs;
they get swapped on the mail day, one at a time, same as today.

Usage (PowerShell, with .venv activated):
    $env:ZHIPU_API_KEY="your-key"   # env var only, never in code
    python concierge.py             # runs the scripted demo below
    python concierge.py chat        # free-form: type your own requests

Model: glm-4-flash (decided 2026-10-26: verified on exercises 1-5, stable)
"""

import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("ZHIPU_API_KEY"),
    base_url="https://open.bigmodel.cn/api/paas/v4/",
)
MODEL = "glm-4-flash"
MAX_TURNS = 8

# ---------------------------------------------------------------------------
# Date / time normalization (program side, not the model's job).
# Exercise 4 proved the model returns literals like "tomorrow" / "3pm".
# The model only splits fields; this code converts them before any tool
# that touches a calendar sees them.
# ---------------------------------------------------------------------------

def normalize_date(s):
    if not s:
        return s
    s = str(s).strip().lower()
    today = date.today()
    if s in ("today", "今天"):
        return today.isoformat()
    if s in ("tomorrow", "明天"):
        return (today + timedelta(days=1)).isoformat()
    if s in ("后天", "day after tomorrow"):
        return (today + timedelta(days=2)).isoformat()
    return s  # already ISO (2026-10-30) or unknown: pass through unchanged


def normalize_time(s):
    if not s:
        return s
    s = str(s).strip().lower().replace(" ", "")
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?(am|pm)$", s)
    if m:
        hour = int(m.group(1))
        minute = m.group(2) or "00"
        if m.group(3) == "pm" and hour != 12:
            hour += 12
        if m.group(3) == "am" and hour == 12:
            hour = 0
        return "%02d:%s" % (hour, minute)
    return s  # already 15:00 style or unknown: pass through unchanged


# ---------------------------------------------------------------------------
# Persistent data: calendar + todos live in concierge_data.json next to
# this script. Loaded once at startup; saved after every change, so a
# restart keeps everything. First run seeds the same two events the
# day-1 stub had, so the demo behaves identically.
# The inbox is still a stub (mail day comes later).
# ---------------------------------------------------------------------------

DATA_FILE = Path(__file__).with_name("concierge_data.json")


def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    data = {
        "calendar": [
            {"date": "2026-10-30", "time": "10:00", "title": "Team standup",
             "person": "", "place": "", "topic": ""},
            {"date": "2026-10-30", "time": "16:30", "title": "Supplier call",
             "person": "", "place": "", "topic": ""},
        ],
        "todos": [],
    }
    save_data(data)
    return data


def save_data(data):
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


DATA = load_data()

FAKE_INBOX = [
    {"from": "Lao Wang", "subject": "Pricing draft v2", "unread": True},
    {"from": "HR", "subject": "November holiday schedule", "unread": True},
    {"from": "Newsletter", "subject": "Weekly tech digest", "unread": False},
]


# ---------------------------------------------------------------------------
# Tools: real Python functions. The model never runs these directly;
# our loop executes them and feeds the result back.
# ---------------------------------------------------------------------------

def _event_label(e):
    if e.get("title"):
        return e["title"]
    return "%s with %s" % (e.get("topic", ""), e.get("person", ""))


def check_free(date_str, time_range=""):
    busy = [e for e in DATA["calendar"] if e["date"] == date_str]
    busy.sort(key=lambda e: e["time"])
    busy_txt = "; ".join(
        "%s %s" % (e["time"], _event_label(e)) for e in busy) or "nothing"
    return "Busy on %s: %s. Other times are free." % (date_str, busy_txt)


def create_event(date_str, time, person, place, topic):
    event = {"date": date_str, "time": time, "person": person,
             "place": place, "topic": topic}
    DATA["calendar"].append(event)
    save_data(DATA)
    return "Event created: %s %s with %s at %s about %s" % (
        date_str, time, person, place, topic)


def read_mail():
    unread = [m for m in FAKE_INBOX if m["unread"]]
    if not unread:
        return "No unread mail (stub)."
    return "Unread mail (stub): " + "; ".join(
        "%s: %s" % (m["from"], m["subject"]) for m in unread)


def draft_mail(to, subject, body):
    return "Draft saved (stub, NOT sent) to %s, subject: %s" % (to, subject)


def send_mail(to, subject, body):
    return "Mail sent (stub) to %s, subject: %s" % (to, subject)


def create_todo(title):
    next_id = max([t["id"] for t in DATA["todos"]], default=0) + 1
    DATA["todos"].append({"id": next_id, "title": title, "done": False})
    save_data(DATA)
    return "Todo #%d created: %s" % (next_id, title)


def list_todos():
    if not DATA["todos"]:
        return "Todo list is empty."
    return "Todos: " + "; ".join(
        "#%d %s%s" % (t["id"], t["title"], " (done)" if t["done"] else "")
        for t in DATA["todos"])


def complete_todo(todo_id):
    for t in DATA["todos"]:
        if t["id"] == int(todo_id):
            t["done"] = True
            save_data(DATA)
            return "Todo #%d marked done." % t["id"]
    return "No todo with id %s." % todo_id


TOOL_FUNCS = {
    "check_free": check_free,
    "create_event": create_event,
    "read_mail": read_mail,
    "draft_mail": draft_mail,
    "send_mail": send_mail,
    "create_todo": create_todo,
    "list_todos": list_todos,
    "complete_todo": complete_todo,
}

# Tools whose date/time arguments must be normalized before execution,
# and which argument holds what.
DATE_ARGS = {"check_free": ("date_str", None), "create_event": ("date_str", "time")}

# ---------------------------------------------------------------------------
# Confirmation gate: irreversible actions stop and ask a human first.
# Drafting and creating are reversible, so they are NOT gated.
# ---------------------------------------------------------------------------

NEEDS_CONFIRM = {"send_mail"}  # delete/update event join this set when they exist


def confirm(action, args):
    print("  [CONFIRM] %s(%s) is irreversible. Run it? [y/N] " % (action, args), end="")
    try:
        answer = input().strip().lower()
    except EOFError:
        answer = ""
    return answer == "y"


# ---------------------------------------------------------------------------
# Tool schemas: the "manual" we hand to the model (same shape as exercise 5)
# ---------------------------------------------------------------------------

def _schema(name, desc, props, required):
    return {"type": "function",
            "function": {"name": name, "description": desc,
                         "parameters": {"type": "object",
                                        "properties": props,
                                        "required": required}}}


TOOLS = [
    _schema("check_free", "Check what is already scheduled on a date",
            {"date_str": {"type": "string", "description": "Date, e.g. tomorrow or 2026-10-30"},
             "time_range": {"type": "string", "description": "Optional time range"}}, ["date_str"]),
    _schema("create_event", "Create a calendar event",
            {"date_str": {"type": "string"}, "time": {"type": "string"},
             "person": {"type": "string"}, "place": {"type": "string"},
             "topic": {"type": "string"}},
            ["date_str", "time", "person", "place", "topic"]),
    _schema("read_mail", "Read unread mail in the inbox", {}, []),
    _schema("draft_mail", "Draft an email (does not send it)",
            {"to": {"type": "string"}, "subject": {"type": "string"},
             "body": {"type": "string"}}, ["to", "subject", "body"]),
    _schema("send_mail", "Send an email immediately (irreversible, needs confirmation)",
            {"to": {"type": "string"}, "subject": {"type": "string"},
             "body": {"type": "string"}}, ["to", "subject", "body"]),
    _schema("create_todo", "Add a todo item",
            {"title": {"type": "string"}}, ["title"]),
    _schema("list_todos", "List all todo items", {}, []),
    _schema("complete_todo", "Mark a todo item as done",
            {"todo_id": {"type": "integer"}}, ["todo_id"]),
]

SYSTEM = (
    "You are a personal concierge agent. Use the tools to handle scheduling, "
    "mail and todos. Prefer draft_mail over send_mail unless the user "
    "explicitly asks to send. Dates and times may be given in natural "
    "language (tomorrow, 3pm); pass them through as given, the program "
    "normalizes them."
)


# ---------------------------------------------------------------------------
# The agent loop: exercise 5's three steps, in a while loop.
# ---------------------------------------------------------------------------

def run_agent(history):
    for turn in range(MAX_TURNS):
        resp = client.chat.completions.create(
            model=MODEL, messages=history, tools=TOOLS)
        msg = resp.choices[0].message
        history.append(msg)

        if not msg.tool_calls:
            print("  [final answer]", msg.content)
            return msg.content

        for call in msg.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)

            # Normalize date/time before the tool sees them.
            if name in DATE_ARGS:
                dkey, tkey = DATE_ARGS[name]
                if dkey in args:
                    raw = args[dkey]
                    args[dkey] = normalize_date(raw)
                    if args[dkey] != raw:
                        print("  [normalize] %s -> %s" % (raw, args[dkey]))
                if tkey and tkey in args:
                    raw = args[tkey]
                    args[tkey] = normalize_time(raw)
                    if args[tkey] != raw:
                        print("  [normalize] %s -> %s" % (raw, args[tkey]))

            # Confirmation gate for irreversible actions.
            if name in NEEDS_CONFIRM and not confirm(name, args):
                result = "User declined to run %s. Do not retry it; offer a draft instead." % name
                print("  [gate] %s blocked by user" % name)
            else:
                result = TOOL_FUNCS[name](**args)
                print("  [tool] %s(%s) -> %s" % (name, args, result))

            history.append({"role": "tool", "tool_call_id": call.id,
                            "content": result})

    print("  [stopped] hit MAX_TURNS=%d without a final answer" % MAX_TURNS)
    return None


def demo():
    "Day-1 acceptance chain on fake data."
    print("=== Demo: one request, four tools, one chain ===")
    history = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content":
         "Meeting with Lao Wang tomorrow 3pm in Nanshan about pricing. "
         "Check if I'm free, book it if I am, draft a notification email "
         "to Lao Wang (do not send it), and add a todo to prepare the "
         "pricing sheet."},
    ]
    run_agent(history)
    print("\nTodos now:", list_todos())
    print("(chain passes if you saw: check_free -> create_event -> "
          "draft_mail -> create_todo, with dates normalized to a real date)")


def chat():
    print("=== Chat mode (type 'quit' to exit) ===")
    history = [{"role": "system", "content": SYSTEM}]
    while True:
        try:
            text = input("\nYou: ").strip()
        except EOFError:
            break
        if text.lower() in ("quit", "exit"):
            break
        if not text:
            continue
        history.append({"role": "user", "content": text})
        run_agent(history)


if __name__ == "__main__":
    if not os.environ.get("ZHIPU_API_KEY"):
        print("Missing env var ZHIPU_API_KEY - set it in PowerShell first")
        sys.exit(1)
    if len(sys.argv) > 1 and sys.argv[1] == "chat":
        chat()
    else:
        demo()
