#!/usr/bin/env python3
"""Evaluate Jev (TypeSafe's System One model) on synthetic clinic phone calls.

Sends every transcript in cases.json to Jev through Vercel AI Gateway, compares
the typed answers with hand-labelled ground truth, prints a report and writes
results.json (which router.py reads offline).
"""
import json
import os
import pathlib
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).parent
ENDPOINT = "https://ai-gateway.vercel.sh/v1/evaluate"
MODEL = "typesafe-ai/jev"
CONFIDENCE_THRESHOLD = 0.80
URGENCY_LEVELS = ["baja", "normal", "alta"]
FIELDS = ["intent", "specialty", "wants_appointment", "urgency"]


def load_api_key():
    if key := os.environ.get("AI_GATEWAY_API_KEY"):
        return key
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "AI_GATEWAY_API_KEY" and value.strip():
                return value.strip()
    raise SystemExit("Missing AI_GATEWAY_API_KEY: copy .env.example to .env and fill it in.")


def ask_jev(transcript, questions, api_key):
    body = json.dumps({"model": MODEL, "state": transcript, "questions": questions}).encode()
    request = urllib.request.Request(ENDPOINT, data=body, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 5:
                raise
            time.sleep(2 ** attempt * 0.5 + random.random())


def parse(answers):
    """Turn Jev's raw answers into a prediction and a confidence per field."""
    p_yes = answers["wants_appointment"]["probability"]
    urgency = URGENCY_LEVELS[min(2, max(0, round(answers["urgency"]["score"])))]
    prediction = {
        "intent": answers["intent"]["choice"],
        "specialty": answers["specialty"]["choice"],
        "wants_appointment": p_yes >= 0.5,
        "urgency": urgency,
    }
    confidence = {
        "intent": answers["intent"]["confidence"],
        "specialty": answers["specialty"]["confidence"],
        # Boolean answers carry no confidence field: use distance from 0.5 instead.
        "wants_appointment": abs(p_yes - 0.5) * 2,
        "urgency": answers["urgency"]["confidence"],
    }
    return prediction, confidence


def report(results, notes, cost, elapsed):
    n = len(results)
    correct = dict.fromkeys(FIELDS, 0)
    confident, unsure, errors = [], [], []
    for r in results:
        for field in FIELDS:
            ok = r["prediction"][field] == r["expected"][field]
            correct[field] += ok
            (confident if r["confidence"][field] >= CONFIDENCE_THRESHOLD else unsure).append(ok)
            if not ok:
                errors.append((r["confidence"][field], r["id"], field,
                               r["expected"][field], r["prediction"][field]))

    print(f"\nAccuracy on {n} synthetic calls\n")
    for field in FIELDS:
        print(f"  {field:<18} {correct[field]:>2}/{n}  {correct[field] / n:6.1%}")
    total = sum(correct.values())
    print(f"  {'overall':<18} {total:>2}/{n * len(FIELDS)}  {total / (n * len(FIELDS)):6.1%}")

    answered = len(confident) + len(unsure)
    print(f"\nSplit by Jev's own confidence (threshold {CONFIDENCE_THRESHOLD})\n")
    for label, bucket in (("confident", confident), ("unsure", unsure)):
        if bucket:
            print(f"  {label:<10} {sum(bucket):>2}/{len(bucket):<3} {sum(bucket) / len(bucket):6.1%}"
                  f"   ({len(bucket) / answered:.0%} of answers)")

    print(f"\nCost ${cost:.6f} for {answered} decisions in {elapsed:.1f}s")
    print(f"\nErrors ({len(errors)}), most confident first:")
    for conf, case_id, field, expected, got in sorted(errors, reverse=True):
        print(f"  #{case_id:<3} {field:<18} expected {str(expected):<14} "
              f"got {str(got):<14} conf {conf:.2f}  {notes[case_id]}")


def main():
    cases = json.loads((ROOT / "cases.json").read_text())
    questions = json.loads((ROOT / "questions.json").read_text())
    api_key = load_api_key()

    started = time.time()
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(lambda c: ask_jev(c["transcript"], questions, api_key), cases))
    elapsed = time.time() - started

    results, cost = [], 0.0
    for case, response in zip(cases, responses):
        prediction, confidence = parse(response["answers"])
        cost += float(response["providerMetadata"]["gateway"]["marketCost"])
        results.append({"id": case["id"], "expected": case["expected"], "prediction": prediction,
                        "confidence": confidence, "raw_answers": response["answers"]})

    (ROOT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    report(results, {c["id"]: c["note"] for c in cases}, cost, elapsed)


if __name__ == "__main__":
    main()
