# Evaluation

This directory holds the evaluation suite for the Financial AI Agent v2. It
answers a question that matters for any multi-agent system going to production:
**does the agent route to the right sub-agents, and is the final answer actually
good?**

Every case runs against the synthetic [`investor_profile.example.md`](../../investor_profile.example.md).
No real personal data is used anywhere in evaluation.

## What is measured

Each case in [`golden_dataset.json`](golden_dataset.json) is scored on two
independent dimensions:

| Dimension | How | Why it matters |
|-----------|-----|----------------|
| **Routing / trajectory** | Deterministic — captured from the tool-call events emitted during the run. Checks that every required sub-agent (e.g. `ticker_resolver → research_agent → analyst_agent`) was actually invoked. | A multi-agent system can produce a plausible answer while skipping the data step. Trajectory checks catch silent mis-routing that a text-only score misses. |
| **Response quality** | LLM-as-judge — an independent Gemini judge grades the final answer against a per-case **rubric** of objective criteria, returning a verdict per criterion plus an overall 1–5 score. | Captures correctness, actionability, and tailoring that simple string matching cannot. |

A case **passes only if routing is correct AND the quality score meets the
`judge_pass_threshold`** (default 4/5). Separating the two dimensions means a
failure tells you *why*: bad routing vs. weak answer.

The dataset deliberately includes two non-happy-path cases:

- `governance_no_guarantee` — verifies the agent **refuses to promise guaranteed
  returns** (a responsible-AI / safety check).
- `tailoring_mortgage_vs_invest` — verifies the agent **uses the investor's
  actual profile** (their 5.5% mortgage rate) rather than generic advice.

## Running the suite

The harness depends only on `google-adk` and `google-genai` (already project
dependencies), so any reviewer can run it.

```bash
# Full suite (routing + LLM judge)
python tests/eval/run_eval.py

# Routing checks only — no judge, no extra API cost
python tests/eval/run_eval.py --no-judge

# A subset (Alpha Vantage free tier is rate limited)
python tests/eval/run_eval.py --cases stock_single_nvda,alt_gold
python tests/eval/run_eval.py --limit 3
```

Reports are written to `tests/eval/results/` (gitignored) as both JSON (full
detail: trajectory, response, per-criterion verdicts) and a Markdown summary
table. See [`SAMPLE_REPORT.md`](SAMPLE_REPORT.md) for the report format.

The process exits non-zero if any case fails, so it can gate CI.

## Platform-native path (agents-cli)

The repo also ships an [`agents-cli`](https://google.github.io/agents-cli/guide/evaluation/)
configuration for teams using the Gemini Enterprise Agent Platform eval surface:

```bash
agents-cli eval generate --dataset tests/eval/datasets/finance-dataset.json
agents-cli eval grade --metrics custom_response_quality
agents-cli eval compare BASE CAND   # regression check between two runs
```

`eval_config.yaml` defines the judge metric used by that path. The standalone
`run_eval.py` above is the portable equivalent and is the recommended entry
point for local runs and CI.

## Extending the dataset

Add a case to `golden_dataset.json` with:

- `eval_case_id`, `category`, `prompt`
- `expected_tools` — the sub-agents that *must* be invoked for correct routing.
  Each entry is either a **string** (that sub-agent is required) or a **list**
  (an "any one of these" group, for questions with more than one legitimate
  routing path). For example, a mortgage-vs-market question can gather comparison
  data via either agent:

  ```json
  "expected_tools": [["alternatives_agent", "research_agent"], "analyst_agent"]
  ```

  This requires `analyst_agent` AND at least one of the two data agents.
- `rubric` — 3–5 objective, yes/no criteria the final answer must satisfy

Keep rubric criteria binary and verifiable so judge scoring stays stable.

## A note on the LLM judge

The judge grades grounding against two authorized sources passed into its prompt:
the **investor profile** and the **retrieved tool data** for that run. This is
deliberate — without the retrieved data, an LLM judge will flag *correct,
tool-sourced* figures (e.g. a live stock price) as "fabricated" by comparing them
to its own stale training knowledge. Grounding the judge in what the agent
actually retrieved removes those false negatives.
