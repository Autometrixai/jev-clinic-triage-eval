#!/usr/bin/env python3
"""Jev decides, plain code acts.

Reads results.json (written by evaluate.py) and applies explicit business rules
to every call. It makes no API calls: the model never triggers an action by
itself. Actions are simulated - they are only printed.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
THRESHOLD = 0.80


def route(p, c):
    """First matching rule wins. Each rule only trusts the confidence of the answers it reads."""
    if p["urgency"] == "alta" and c["urgency"] >= THRESHOLD:
        return "ALERT_NURSE", "Immediate SMS to the on-call nurse"
    if p["intent"] == "otro" and c["intent"] >= THRESHOLD:
        return "DISCARD", "Spam or wrong number"
    if p["intent"] == "reclamacion" and c["intent"] >= THRESHOLD:
        return "OPEN_TICKET", "Complaint ticket + email to management"
    if p["intent"] == "cancelar_cita" and c["intent"] >= THRESHOLD:
        return "RELEASE_SLOT", "Cancel in calendar, offer the slot to the waiting list"
    if c["intent"] < THRESHOLD or c["wants_appointment"] < THRESHOLD:
        return "HUMAN_REVIEW", "Jev is not sure: queue for a person"
    if p["wants_appointment"] and p["specialty"] != "otras" and c["specialty"] >= THRESHOLD:
        return "BOOK_APPOINTMENT", f"POST /calendar specialty={p['specialty']}"
    if p["wants_appointment"]:
        return "CALL_BACK", "Wants an appointment, specialty unclear: reception calls back"
    return "SEND_INFO", "WhatsApp with the info pack and prices"


def main():
    results = json.loads((ROOT / "results.json").read_text())
    transcripts = {c["id"]: c["transcript"] for c in json.loads((ROOT / "cases.json").read_text())}

    counts = {}
    print(f"\n{'#':>3}  {'caller said':<46} {'action':<17} detail")
    print("-" * 110)
    for r in results:
        action, detail = route(r["prediction"], r["confidence"])
        counts[action] = counts.get(action, 0) + 1
        print(f"{r['id']:>3}  {transcripts[r['id']][:44]:<46} {action:<17} {detail}")

    print()
    for action, n in sorted(counts.items(), key=lambda item: -item[1]):
        print(f"  {action:<17} {n:>2}  {'#' * n}")
    automated = len(results) - counts.get("HUMAN_REVIEW", 0)
    print(f"\n  Handled without a human: {automated}/{len(results)} ({automated / len(results):.0%})")


if __name__ == "__main__":
    main()
