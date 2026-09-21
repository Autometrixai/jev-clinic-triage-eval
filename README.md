# Jev on clinic phone calls

An early, independent evaluation of **Jev**, TypeSafe AI's "System One" model (released 2026-09-15), on a realistic task: triaging phone calls to a private medical clinic.

Jev does not generate text. You send it a piece of text plus typed questions (`choice`, `score`, yes/no) and it returns constrained answers with probabilities and a confidence value. This repo asks one question: **is that confidence trustworthy enough to automate on?**

Transcripts and questions are in Spanish, as a Spanish clinic would receive them.

## Results

24 synthetic calls × 4 questions = 96 decisions. Nine calls are deliberate traps: negations, irony, mixed intents, noise.

| Field | Accuracy |
|---|---|
| Specialty | 95.8% |
| Clinical urgency | 83.3% |
| Intent (7 classes) | 79.2% |
| Wants an appointment | 79.2% |
| **Overall** | **84.4%** |

The number that matters is in the second table:

| Jev's confidence | Share of answers | Accuracy |
|---|---|---|
| ≥ 0.80 | 75% | **98.6%** (71 / 72) |
| < 0.80 | 25% | 41.7% |

When Jev says it is sure, it is almost always right. When it is not, it says so. A text-generating classifier does not give you that, and it is what makes **confidence-gated automation** possible: act on the confident 75%, send the rest to a person.

The single confident miss (#8) is arguably a labelling error: after surgery the caller says *"la zona"* and never names a specialty. Jev answered "not specified"; the ground truth assumed pelvic floor from context.

Cost: **$0.00083 for all 96 decisions**, about 116,000 decisions per dollar. Two independent runs produced the same headline figures.

## From decisions to actions

`router.py` shows the intended architecture: **Jev decides, plain code acts.** It reads the saved results (no API key needed) and applies explicit rules: alert the nurse, book, open a complaint ticket, discard spam, or queue for human review.

```
Handled without a human: 16/24 (67%)
```

Because the rules are ordinary code, changing behaviour means editing an `if`, not rewriting a prompt. An earlier version of these rules sent obvious spam to human review because it checked the confidence of an unrelated question. Reordering the rules fixed it with no change to the model.

## Method and limits

- **Synthetic data only.** No real patient data was used. The dataset models a fictional private clinic offering pelvic-floor, aesthetic and hair treatments.
- **One author for cases and questions.** That favours the model. A real deployment needs an evaluation on real traffic.
- **Label audit.** Reviewing the errors surfaced five ground-truth labels that contradicted the question definitions, such as a complaint labelled "normal" urgency when the question asks for *clinical* urgency. They are corrected and flagged `"label_corrected": true` in `cases.json`. Debatable cases still count against the model.
- **Noise.** On a garbled transcript (#14) Jev guessed "wants an appointment" at 0.70 confidence: below the threshold, but higher than garbage deserves. Speech-to-text noise is the first thing to test with real audio.
- **Where it fails.** Most misses are on the 7-way intent question with mixed intents ("I'm complaining *and* I want to book"). TypeSafe recommends atomic questions; splitting intent into independent yes/no questions is the obvious next step.

## Calling Jev through Vercel AI Gateway

At launch TypeSafe's own API was waitlisted, but Jev is served by Vercel AI Gateway as `typesafe-ai/jev`. It is not on OpenRouter. The gateway's format differs from TypeSafe's documentation in ways that are not documented anywhere. These differences were checked against both APIs on 2026-09-20:

| | TypeSafe API | Vercel AI Gateway |
|---|---|---|
| Endpoint | `POST https://api.typesafe.ai/v1/systemone` | `POST https://ai-gateway.vercel.sh/v1/evaluate` |
| Model | `jev-latest` | `typesafe-ai/jev` |
| Yes/no question type | `noul` | `boolean` |
| Yes/no answer field | `noul` | `probability` |
| Token usage field | `input_tokens` | `inputTokens` |

Also on the gateway:

- `score` criteria must be an **ordered array** of level descriptions. An object is rejected.
- `choice` criteria are an object of `{option: description}`.
- The account needs a card on file before any request is served.
- Parallel bursts return `429`. Three workers with exponential backoff were enough here.

## Run it

```bash
cp .env.example .env    # add your Vercel AI Gateway key
python3 evaluate.py     # calls Jev, writes results.json, prints the report
python3 router.py       # offline: applies the routing rules to results.json
```

Python 3.8+, standard library only. `results.json` from the reported run is included, so `router.py` runs without a key.

| File | |
|---|---|
| `cases.json` | 24 synthetic calls with ground truth |
| `questions.json` | the four typed questions sent to Jev |
| `evaluate.py` | runs the evaluation and prints the report |
| `router.py` | rules that turn decisions into actions |
| `results.json` | raw and parsed answers from the reported run |

---

By [Autometrix AI](https://autometrixai.com): AI automation for private clinics. MIT licence. Built with [Claude Code](https://claude.com/claude-code).
