"""
FDE Week 3 - Scoring step. Run AFTER triage.

This is the only program allowed to open answer_key.json, and it
reads triage_results.json (decisions already locked in) - it never
re-runs the agent, so the score cannot contaminate the triage.

For every missed ticket it also tags the likely error layer:
  retrieval miss  - none of find_similar's top 3 history tickets had
                    the correct category, so the model never saw good
                    evidence (fix: the retriever)
  judgment error  - the correct category WAS in the evidence, the
                    model still chose otherwise (fix: prompt/model)
That split is the whole point of keeping evidence program-side.

Usage:  python score.py
"""

import json
from pathlib import Path

BASE = Path(__file__).with_name("data")
RESULTS_FILE = Path(__file__).with_name("triage_results.json")


def _top_categories(ticket_id, top_k=3):
    """Recompute find_similar's top-k categories for error tagging.

    Mirrors triage.find_similar exactly (same bigram score), without
    importing the agent - the scorer stays independent of it.
    """
    incoming = json.loads((BASE / "tickets_incoming.json").read_text(
        encoding="utf-8"))
    history = json.loads((BASE / "tickets_history.json").read_text(
        encoding="utf-8"))
    by_id = {t["id"]: t for t in incoming}
    t = by_id[ticket_id]

    def bigrams(text):
        text = "".join(text.split())
        return {text[i:i + 2] for i in range(len(text) - 1)}

    query = bigrams(t["title"] + t["description"])
    scored = []
    for h in history:
        corpus = bigrams(h["title"] + h["description"])
        score = len(query & corpus) / max(1, len(query))
        if h["title"] == t["title"]:
            score += 0.5
        scored.append((score, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [h["category"] for _, h in scored[:top_k]]


def main():
    if not RESULTS_FILE.exists():
        print("No triage_results.json yet - run triage.py first.")
        return
    results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    key = json.loads((BASE / "answer_key.json").read_text(encoding="utf-8"))

    total = len(key)
    cat_ok = pri_ok = route_ok = 0
    misses = []
    missing = [tid for tid in key if tid not in results]
    for tid, truth in sorted(key.items()):
        r = results.get(tid)
        if r is None:
            misses.append((tid, "not recorded", "-", truth["category"],
                           truth["priority"], "no result"))
            continue
        c_ok = r["category"] == truth["category"]
        p_ok = r["priority"] == truth["priority"]
        # Routing correctness: sensitive tickets must never be plain
        # assignments; others must not be suggestion-only.
        if truth["sensitive"]:
            r_ok = r["action"] == "suggestion_only"
        else:
            r_ok = r["action"] in ("assigned", "escalate_human")
        cat_ok += c_ok
        pri_ok += p_ok
        route_ok += r_ok
        if not (c_ok and p_ok and r_ok):
            if not c_ok:
                tag = ("judgment error" if truth["category"]
                       in _top_categories(tid) else "retrieval miss")
            elif not p_ok:
                tag = "priority judgment error"
            else:
                tag = "ROUTING ERROR"
            misses.append((tid, r["category"], r["priority"],
                           truth["category"], truth["priority"], tag))

    print("=== Triage score over %d tickets (%d recorded) ==="
          % (total, total - len(missing)))
    print("Category accuracy : %d/%d = %.0f%%"
          % (cat_ok, total, 100.0 * cat_ok / total))
    print("Priority accuracy : %d/%d = %.0f%%"
          % (pri_ok, total, 100.0 * pri_ok / total))
    print("Routing correct   : %d/%d = %.0f%%"
          % (route_ok, total, 100.0 * route_ok / total))
    if misses:
        print("\nMisses (id | predicted cat/pri | truth cat/pri | tag):")
        for tid, pc, pp, tc, tp, tag in misses:
            print("  %s | %s/%s | %s/%s | %s" % (tid, pc, pp, tc, tp, tag))
    else:
        print("\nNo misses.")


if __name__ == "__main__":
    main()
