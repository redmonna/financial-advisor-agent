# Financial AI Agent v2 — Evaluation Report

> **Illustrative example of the report format.** The numbers below are a sample
> to show output shape, not a recorded benchmark run. Generate a real report with
> `python tests/eval/run_eval.py`.

- **Cases:** 12
- **Pass rate:** 10/12 (83%)
- **Routing accuracy:** 11/12 (92%)
- **Avg quality score:** 4.3 / 5 (pass threshold ≥ 4)

| Case | Category | Routing | Quality | Result |
|------|----------|---------|---------|--------|
| stock_single_nvda | stocks | ✅ | 5/5 | ✅ PASS |
| stock_single_aapl | stocks | ✅ | 4/5 | ✅ PASS |
| alt_gold | alternatives | ✅ | 4/5 | ✅ PASS |
| alt_housing | alternatives | ✅ | 4/5 | ✅ PASS |
| reit_pld | reit | ✅ | 4/5 | ✅ PASS |
| self_cert_gcp | self_investment | ✅ | 5/5 | ✅ PASS |
| self_career_track | self_investment | ✅ | 4/5 | ✅ PASS |
| mixed_stock_vs_gold | mixed | ✅ | 4/5 | ✅ PASS |
| portfolio_cert_vs_index | portfolio | ❌ missing ['analyst_agent'] | 3/5 | ❌ FAIL |
| alt_crypto_allocation | alternatives | ✅ | 5/5 | ✅ PASS |
| governance_no_guarantee | governance | ✅ | 5/5 | ✅ PASS |
| tailoring_mortgage_vs_invest | personalization | ✅ | 3/5 | ❌ FAIL |

The two failures illustrate what the split scoring surfaces: `portfolio_cert_vs_index`
produced a reasonable answer but **skipped the `analyst_agent` synthesis step**
(a routing bug), while `tailoring_mortgage_vs_invest` routed correctly but the
answer **did not reference the investor's actual 5.5% mortgage rate** (a quality
/ personalization gap). Each points at a different fix.
