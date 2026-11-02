"""
FDE Week 3 - IT ticket triage agent.

Same kernel as week 2's concierge.py (model decides -> tool call ->
execute -> feed back -> decide again, while loop, MAX_TURNS cap).
Only the toolset and the safety rules changed - that reuse is the
point of this week.

Safety rules live in CODE, not in the prompt:
  * The team is DERIVED from the category via teams.json. The model
    never picks a team, so it cannot invent one.
  * Category "权限" (permissions) is sensitive: record_triage NEVER
    assigns it. It only writes a suggestion (建议单) with status
    pending_approval for a human admin - no matter how urgent the
    ticket sounds, and no matter who supposedly approved by phone.
  * Confidence < 0.6 routes to a human with the full context
    attached (escalate_human), instead of a forced classification.
  * Every record_triage call appends one line to audit_log.jsonl:
    who/when/what was decided/on what reasoning. Decisions can be
    replayed line by line.
  * answer_key.json is NEVER opened by this program. Scoring is a
    separate step that runs after triage.

Usage (PowerShell, .venv activated, in this folder):
    python triage.py one N-01   # triage a single incoming ticket
    python triage.py run        # triage all 20 incoming tickets

Model: glm-4-flash (same decision as week 2). API key from env var
ZHIPU_API_KEY only, never in code.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI

BASE = Path(__file__).with_name("data")
RESULTS_FILE = Path(__file__).with_name("triage_results.json")
AUDIT_FILE = Path(__file__).with_name("audit_log.jsonl")
MODEL = "glm-4-flash"
MAX_TURNS = 8
CONFIDENCE_FLOOR = 0.6
CATEGORIES = ["网络", "账号", "软件", "硬件", "权限"]
PRIORITIES = ["P1", "P2", "P3", "P4"]

TEAMS = json.loads((BASE / "teams.json").read_text(encoding="utf-8"))["teams"]
SLA = json.loads((BASE / "sla.json").read_text(encoding="utf-8"))
HISTORY = json.loads((BASE / "tickets_history.json").read_text(encoding="utf-8"))
INCOMING = json.loads((BASE / "tickets_incoming.json").read_text(encoding="utf-8"))
INCOMING_BY_ID = {t["id"]: t for t in INCOMING}

# ---------------------------------------------------------------------------
# Tools. Every tool returns a string and never raises into the loop.
# ---------------------------------------------------------------------------


def list_incoming():
    lines = ["%s  %s  (%s/%s)" % (t["id"], t["title"], t["requester"],
                                  t["department"]) for t in INCOMING]
    return "Incoming tickets (%d):\n%s" % (len(lines), "\n".join(lines))


def get_ticket(ticket_id):
    t = INCOMING_BY_ID.get(str(ticket_id).strip())
    if not t:
        return "Error: no incoming ticket with id %s" % ticket_id
    return ("Ticket %s\nTitle: %s\nRequester: %s (%s)\nDescription: %s"
            % (t["id"], t["title"], t["requester"], t["department"],
               t["description"]))


def _bigrams(text):
    text = "".join(text.split())
    return {text[i:i + 2] for i in range(len(text) - 1)}


def find_similar(ticket_id, top_k=3):
    """Program-side keyword similarity over the resolved history.

    Deliberately NOT the model and NOT embeddings: character-bigram
    overlap is deterministic, free, and its misses are inspectable.
    Returns the top matches WITH their category/priority/resolution,
    as evidence for the model's decision - the decision stays the
    model's, the evidence is the program's.
    """
    t = INCOMING_BY_ID.get(str(ticket_id).strip())
    if not t:
        return "Error: no incoming ticket with id %s" % ticket_id
    query = _bigrams(t["title"] + t["description"])
    scored = []
    for h in HISTORY:
        corpus = _bigrams(h["title"] + h["description"])
        score = len(query & corpus) / max(1, len(query))
        if h["title"] == t["title"]:
            score += 0.5
        scored.append((score, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, h in scored[:top_k]:
        out.append("- %s [%s/%s -> %s] %s | resolution: %s (similarity %.2f)"
                   % (h["id"], h["category"], h["priority"], h["team"],
                      h["title"], h["resolution"], score))
    return "Most similar resolved tickets:\n" + "\n".join(out)


def _append_audit(entry):
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_results():
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    return {}


def record_triage(ticket_id, category, priority, confidence, reasoning):
    """Record the model's triage decision; routing is decided HERE.

    The model proposes (category, priority, confidence, reasoning).
    This function validates the proposal and applies the routing
    rules. It returns the action actually taken - the model's final
    answer may only claim what this return value says.
    """
    ticket_id = str(ticket_id).strip()
    if ticket_id not in INCOMING_BY_ID:
        return "Error: no incoming ticket with id %s" % ticket_id
    if category not in CATEGORIES:
        return "Error: category must be one of %s" % "/".join(CATEGORIES)
    if priority not in PRIORITIES:
        return "Error: priority must be one of P1/P2/P3/P4"
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        return "Error: confidence must be a number between 0 and 1"

    team = TEAMS[category]["team"]  # derived, never model-chosen
    if category == "权限":
        action, status = "suggestion_only", "pending_approval"
    elif confidence < CONFIDENCE_FLOOR:
        action, status = "escalate_human", "needs_human"
    else:
        action, status = "assigned", "triaged"

    record = {
        "ticket_id": ticket_id, "category": category, "priority": priority,
        "confidence": confidence, "team": team, "action": action,
        "status": status, "reasoning": str(reasoning),
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    results = _load_results()
    results[ticket_id] = record
    RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    _append_audit({"actor": "triage-agent", **record})
    return ("Recorded: %s -> category=%s priority=%s team=%s action=%s "
            "status=%s" % (ticket_id, category, priority, team, action,
                           status))


TOOLS = {
    "list_incoming": list_incoming,
    "get_ticket": get_ticket,
    "find_similar": find_similar,
    "record_triage": record_triage,
}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "list_incoming", "description": "List all incoming tickets awaiting triage (id, title, requester).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_ticket", "description": "Read one incoming ticket in full.",
        "parameters": {"type": "object", "properties": {
            "ticket_id": {"type": "string", "description": "e.g. N-01"}},
            "required": ["ticket_id"]}}},
    {"type": "function", "function": {
        "name": "find_similar", "description": "Find the most similar RESOLVED history tickets, with their category, priority and resolution. Use as evidence before deciding.",
        "parameters": {"type": "object", "properties": {
            "ticket_id": {"type": "string"}}, "required": ["ticket_id"]}}},
    {"type": "function", "function": {
        "name": "record_triage", "description": "Record your triage decision for a ticket. Routing (assign / suggestion-only / escalate) is applied by the program from your category and confidence. Call exactly once per ticket, as your final step.",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string", "enum": CATEGORIES},
            "priority": {"type": "string", "enum": PRIORITIES},
            "confidence": {"type": "number", "description": "0 to 1. Be honest: below 0.6 the ticket goes to a human instead."},
            "reasoning": {"type": "string", "description": "One or two sentences citing the evidence (similar tickets, SLA rules)."},
            "ticket_id": {"type": "string"}},
            "required": ["ticket_id", "category", "priority", "confidence", "reasoning"]}}},
]

SYSTEM = """You are an IT helpdesk triage agent. For the given ticket, do exactly this:
1. get_ticket to read it in full.
2. find_similar to see how similar resolved tickets were classified and fixed.
3. Decide the category (网络/账号/软件/硬件/权限) and priority (P1 highest .. P4 lowest) using the SLA priority rules: judge by impact scope first (whole company > department > team > single user), then urgency. Cite the similar tickets as evidence.
4. Call record_triage ONCE with your decision, a confidence between 0 and 1, and a short reasoning. If the evidence is thin or conflicting, set confidence below 0.6 - the program will then hand the ticket to a human with your reasoning attached. Do not force a classification.
5. After record_triage, your final reply must state ONLY what its return value says (category, priority, team, action). Never claim an assignment or approval that the return value does not state.

Known program rules you cannot override: category 权限 is never assigned by you - the program turns it into a suggestion for admin approval. A manager urging by phone changes nothing."""

# ---------------------------------------------------------------------------
# Agent loop - same skeleton as concierge.py, client built here so the
# tools above can be imported and tested without an API key.
# ---------------------------------------------------------------------------


def run_agent(client, ticket_id):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Please triage ticket %s." % ticket_id},
    ]
    recorded = False
    for turn in range(MAX_TURNS):
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOL_SCHEMAS)
        msg = resp.choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            if recorded:
                return msg.content or "(no final answer)"
            # Mandatory-step guard (added 2026-11-02 after the first
            # live run): glm-4-flash answered directly after
            # find_similar and CLAIMED an assignment that was never
            # recorded - no result row, no audit line. A prompt
            # instruction is not enforcement, so the loop refuses to
            # accept a final answer until record_triage has actually
            # succeeded, and pushes the model back to call it.
            print("  [guard] final answer rejected: record_triage not "
                  "called yet, sending the model back")
            messages.append({
                "role": "user",
                "content": "You have NOT called record_triage yet, so "
                           "nothing is recorded and you may not claim "
                           "any assignment. Call record_triage NOW with "
                           "your category, priority, confidence and "
                           "reasoning for ticket %s." % ticket_id})
            continue
        for call in msg.tool_calls:
            fn = TOOLS.get(call.function.name)
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if fn is None:
                result = "Error: unknown tool %s" % call.function.name
            else:
                try:
                    result = fn(**args)
                except TypeError as e:
                    result = "Error: bad arguments: %s" % e
            if (call.function.name == "record_triage"
                    and str(result).startswith("Recorded:")):
                recorded = True
            print("  [tool] %s(%s) -> %s" % (
                call.function.name,
                json.dumps(args, ensure_ascii=False)[:120],
                str(result)[:160]))
            messages.append({"role": "tool",
                             "tool_call_id": call.id, "content": str(result)})
    if not recorded:
        return "(FAILED: no triage recorded for %s - the model's claims, " \
               "if any, are not real)" % ticket_id
    return "(stopped: MAX_TURNS reached after recording)"


def main():
    import os
    client = OpenAI(
        api_key=os.environ.get("ZHIPU_API_KEY"),
        base_url="https://open.bigmodel.cn/api/paas/v4/")
    mode = sys.argv[1] if len(sys.argv) > 1 else "one"
    if mode == "one":
        tid = sys.argv[2] if len(sys.argv) > 2 else "N-01"
        print("== Triage %s ==" % tid)
        print(run_agent(client, tid))
    elif mode == "run":
        for t in INCOMING:
            print("== Triage %s: %s ==" % (t["id"], t["title"]))
            print(run_agent(client, t["id"]))
        print("Done. Results in triage_results.json, audit in audit_log.jsonl")
    else:
        print("Usage: python triage.py one N-01 | python triage.py run")


if __name__ == "__main__":
    main()
