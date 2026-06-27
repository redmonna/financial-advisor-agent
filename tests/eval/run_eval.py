#!/usr/bin/env python3
"""Reproducible evaluation harness for the Financial AI Agent v2.

For every case in ``golden_dataset.json`` this harness runs the full multi-agent
system end-to-end and scores it on two independent dimensions:

1. **Routing / trajectory correctness** (deterministic) — did the root agent
   delegate to the sub-agents the case expects? Captured from the tool-call
   events in the run, so it is not subject to judge variance.

2. **Response quality** (LLM-as-judge) — does the final answer satisfy each
   objective criterion in the case rubric? An independent Gemini judge returns a
   per-criterion verdict plus an overall 1-5 score.

A case passes only if routing is correct AND the quality score meets the
``judge_pass_threshold`` declared in the dataset.

Evaluation always runs against ``investor_profile.example.md`` (synthetic) so no
real personal data is ever involved.

Usage:
    python tests/eval/run_eval.py                  # full suite
    python tests/eval/run_eval.py --cases stock_single_nvda,alt_gold
    python tests/eval/run_eval.py --limit 3        # first 3 cases (rate-limit friendly)
    python tests/eval/run_eval.py --no-judge       # routing checks only (no API cost)

Note: each case may call the Alpha Vantage MCP server. Its free tier is rate
limited, so use --limit or --cases when iterating.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict

# --- Make the repo root importable (this file lives in tests/eval/) ---
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(REPO_ROOT, ".env"), override=True)

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from main import create_root_agent

DATASET_PATH = os.path.join(os.path.dirname(__file__), "golden_dataset.json")
EXAMPLE_PROFILE = os.path.join(REPO_ROOT, "investor_profile.example.md")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
DEFAULT_JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "gemini-3-flash-preview")

JUDGE_PROMPT_TEMPLATE = """You are a strict, impartial evaluator for a financial-advisory AI agent.
Grade the agent's FINAL RESPONSE against the user's request and the rubric below.

The agent has access to TWO authorized sources of ground truth — judge factual
and numeric claims ONLY against these:

[A] INVESTOR PROFILE (the agent's known context about the user):
{investor_profile}

[B] RETRIEVED TOOL DATA (live data the agent gathered for this request):
{tool_data}

GROUNDING RULE: A figure or fact is "fabricated" ONLY if it does not appear in,
or reasonably follow from, source [A] or source [B] above. Personal details about
the user that match the INVESTOR PROFILE are correctly grounded, not fabricated.
Market figures that match the RETRIEVED TOOL DATA are correctly grounded. Do NOT
use your own outside knowledge of "correct" prices, ratios, or market values —
live data changes and your knowledge may be stale. If a specific figure appears
in NEITHER source, it is unsupported.

For each rubric criterion decide whether the response clearly satisfies it (true)
or not (false). Be conservative: if a criterion is only partially met or you are
unsure, mark it false. Then assign an overall quality score from 1 to 5:
  1 = fails the request   2 = major gaps   3 = acceptable   4 = good   5 = excellent

USER REQUEST:
{prompt}

RUBRIC CRITERIA:
{rubric}

AGENT FINAL RESPONSE:
{response}

Return ONLY a valid JSON object of this exact shape:
{{
  "criteria": [{{"criterion": "<text>", "met": <true|false>, "reasoning": "<short>"}}],
  "overall_score": <integer 1-5>,
  "explanation": "<one or two sentences>"
}}"""


@dataclass
class CaseResult:
    eval_case_id: str
    category: str
    prompt: str
    expected_tools: list[str]
    observed_tools: list[str]
    missing_tools: list[str]
    unexpected_tools: list[str]
    trajectory_pass: bool
    response: str
    tool_trace: list[dict] = field(default_factory=list)
    quality_score: int | None = None
    quality_pass: bool | None = None
    criteria: list[dict] = field(default_factory=list)
    judge_explanation: str = ""
    error: str | None = None

    @property
    def passed(self) -> bool:
        if self.error:
            return False
        if self.quality_pass is None:  # --no-judge mode
            return self.trajectory_pass
        return self.trajectory_pass and self.quality_pass


def _run_agent(runner: Runner, user_id: str, session_id: str, prompt: str) -> tuple[str, list[str], list[dict]]:
    """Run one prompt and return (final_response_text, ordered_tool_calls, tool_trace).

    ``tool_trace`` holds the data each sub-agent/tool returned, so the judge can
    assess grounding against what was actually retrieved rather than its own
    (possibly stale) world knowledge.
    """
    tool_calls: list[str] = []
    tool_trace: list[dict] = []
    final_text_parts: list[str] = []
    message = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])

    for event in runner.run(user_id=user_id, session_id=session_id, new_message=message):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "function_call", None):
                    tool_calls.append(part.function_call.name)
                if getattr(part, "function_response", None):
                    fr = part.function_response
                    resp = fr.response
                    text = resp if isinstance(resp, str) else json.dumps(resp, default=str)
                    tool_trace.append({"tool": fr.name, "data": text[:2500]})
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    final_text_parts.append(part.text)

    return "".join(final_text_parts).strip(), tool_calls, tool_trace


def _score_trajectory(expected: list, observed: list[str]) -> tuple[bool, list[str], list[str]]:
    """Score routing. Each item in ``expected`` is either:

    - a string: that sub-agent MUST be invoked, or
    - a list of strings: AT LEAST ONE of them must be invoked (for questions
      with more than one legitimate routing path).
    """
    observed_set = set(observed)
    known = {"ticker_resolver", "research_agent", "alternatives_agent",
             "self_investment_agent", "analyst_agent"}
    missing: list[str] = []
    allowed: set[str] = set()  # known sub-agents that are acceptable for this case
    for item in expected:
        if isinstance(item, list):
            allowed.update(item)
            if not (set(item) & observed_set):
                missing.append("one of [" + ", ".join(item) + "]")
        else:
            allowed.add(item)
            if item not in observed_set:
                missing.append(item)
    unexpected = sorted((observed_set & known) - allowed)
    trajectory_pass = not missing  # every required step (or any-of group) satisfied
    return trajectory_pass, missing, unexpected


def _format_tool_data(tool_trace: list[dict], cap: int = 8000) -> str:
    if not tool_trace:
        return "(no tool data was retrieved)"
    blocks = [f"### {t['tool']}\n{t['data']}" for t in tool_trace]
    joined = "\n\n".join(blocks)
    return joined[:cap]


def _judge(client, judge_model: str, prompt: str, rubric: list[str], response: str,
           tool_trace: list[dict], investor_profile: str) -> dict:
    rubric_text = "\n".join(f"- {c}" for c in rubric)
    judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
        prompt=prompt, rubric=rubric_text, response=response,
        tool_data=_format_tool_data(tool_trace),
        investor_profile=investor_profile or "(none)",
    )
    resp = client.models.generate_content(
        model=judge_model,
        contents=judge_prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    return json.loads(resp.text)


def evaluate(cases: list[dict], threshold: int, use_judge: bool, judge_model: str) -> list[CaseResult]:
    if not os.path.exists(EXAMPLE_PROFILE):
        raise FileNotFoundError(f"Synthetic profile not found: {EXAMPLE_PROFILE}")
    with open(EXAMPLE_PROFILE) as f:
        investor_profile = f.read()

    root_agent = create_root_agent(profile_path=EXAMPLE_PROFILE)
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, session_service=session_service, app_name="eval")

    client = None
    if use_judge:
        from google import genai
        client = genai.Client()  # reads GOOGLE_API_KEY / GEMINI_API_KEY from env

    results: list[CaseResult] = []
    for i, case in enumerate(cases, 1):
        cid = case["eval_case_id"]
        print(f"[{i}/{len(cases)}] {cid} ... ", end="", flush=True)
        # Fresh session per case so cases do not contaminate each other.
        session = session_service.create_session_sync(user_id="eval_user", app_name="eval")
        try:
            response, tool_calls, tool_trace = _run_agent(runner, "eval_user", session.id, case["prompt"])
            traj_pass, missing, unexpected = _score_trajectory(case.get("expected_tools", []), tool_calls)
            cr = CaseResult(
                eval_case_id=cid,
                category=case.get("category", ""),
                prompt=case["prompt"],
                expected_tools=case.get("expected_tools", []),
                observed_tools=tool_calls,
                missing_tools=missing,
                unexpected_tools=unexpected,
                trajectory_pass=traj_pass,
                response=response,
                tool_trace=tool_trace,
            )
            if use_judge:
                verdict = _judge(client, judge_model, case["prompt"], case.get("rubric", []),
                                 response, tool_trace, investor_profile)
                cr.quality_score = int(verdict.get("overall_score", 0))
                cr.criteria = verdict.get("criteria", [])
                cr.judge_explanation = verdict.get("explanation", "")
                cr.quality_pass = cr.quality_score >= threshold
            print("PASS" if cr.passed else "FAIL")
        except Exception as e:  # keep the suite running; record the failure
            cr = CaseResult(
                eval_case_id=cid, category=case.get("category", ""), prompt=case["prompt"],
                expected_tools=case.get("expected_tools", []), observed_tools=[],
                missing_tools=case.get("expected_tools", []), unexpected_tools=[],
                trajectory_pass=False, response="", error=str(e),
            )
            print(f"ERROR: {e}")
        results.append(cr)
    return results


def write_reports(results: list[CaseResult], threshold: int, use_judge: bool, out_dir: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(out_dir, f"eval_{stamp}.json")
    md_path = os.path.join(out_dir, f"eval_{stamp}.md")

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    traj_ok = sum(1 for r in results if r.trajectory_pass)
    scores = [r.quality_score for r in results if r.quality_score is not None]
    avg_quality = round(sum(scores) / len(scores), 2) if scores else None

    summary = {
        "timestamp": stamp,
        "total_cases": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0,
        "routing_accuracy": round(traj_ok / total, 3) if total else 0,
        "avg_quality_score": avg_quality,
        "judge_pass_threshold": threshold,
        "judge_used": use_judge,
    }
    with open(json_path, "w") as f:
        json.dump({"summary": summary, "cases": [asdict(r) for r in results]}, f, indent=2)

    lines = [
        "# Financial AI Agent v2 — Evaluation Report",
        "",
        f"- **Cases:** {total}",
        f"- **Pass rate:** {passed}/{total} ({summary['pass_rate']:.0%})",
        f"- **Routing accuracy:** {traj_ok}/{total} ({summary['routing_accuracy']:.0%})",
        f"- **Avg quality score:** {avg_quality if avg_quality is not None else 'n/a'} / 5"
        f" (pass threshold ≥ {threshold})",
        "",
        "| Case | Category | Routing | Quality | Result |",
        "|------|----------|---------|---------|--------|",
    ]
    for r in results:
        routing = "✅" if r.trajectory_pass else f"❌ missing {r.missing_tools}"
        if r.error:
            quality = "—"
        elif r.quality_score is None:
            quality = "n/a"
        else:
            quality = f"{r.quality_score}/5"
        result = "✅ PASS" if r.passed else "❌ FAIL"
        lines.append(f"| {r.eval_case_id} | {r.category} | {routing} | {quality} | {result} |")
    lines.append("")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))

    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Financial AI Agent v2 against the golden dataset.")
    parser.add_argument("--cases", help="Comma-separated eval_case_ids to run (default: all)")
    parser.add_argument("--limit", type=int, help="Run only the first N cases")
    parser.add_argument("--no-judge", action="store_true", help="Routing checks only; skip the LLM judge")
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL, help="Model id for the LLM judge")
    parser.add_argument("--output", default=RESULTS_DIR, help="Directory for result reports")
    args = parser.parse_args()

    with open(DATASET_PATH) as f:
        dataset = json.load(f)
    cases = dataset["eval_cases"]
    threshold = int(dataset.get("judge_pass_threshold", 4))

    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",")}
        cases = [c for c in cases if c["eval_case_id"] in wanted]
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("No matching cases.")
        return 1

    use_judge = not args.no_judge
    print(f"Running {len(cases)} case(s) | judge={'on (' + args.judge_model + ')' if use_judge else 'off'}\n")
    start = time.time()
    results = evaluate(cases, threshold, use_judge, args.judge_model)
    json_path, md_path = write_reports(results, threshold, use_judge, args.output)

    passed = sum(1 for r in results if r.passed)
    print(f"\n{'='*48}")
    print(f"  {passed}/{len(results)} passed  ({time.time()-start:.0f}s)")
    print(f"  report: {md_path}")
    print(f"{'='*48}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
