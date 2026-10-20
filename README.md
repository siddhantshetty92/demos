# Siddhant Shetty: AI & Automation Portfolio

Tools I designed and built to make go-to-market, product and operations teams faster at a B2B SaaS company, most of them built with AI coding agents and several using LLMs at runtime.

> **About these projects.** Each one is a clean-room rebuild of work I did on the job, reduced to the core idea and run entirely on synthetic data. No employer code, customer data, configuration or names are included. The point is to show the problem, the approach and the engineering, not to reproduce the original systems.

<!-- Add a two-line bio and links here, e.g. LinkedIn / email. -->

## Projects

| | Project | What it shows | Stack |
|---|---|---|---|
| **AI agents** | [Docs-Sync Agents](projects/05-docs-sync-agents) | LLM classifier with a deterministic tool decides, per merge, whether API docs and runbooks must change; human approval gate; writer agents; eval suite | Node, Anthropic API (tool use, structured output) |
| | [RFP Answer Assistant](projects/06-rfp-answer-assistant) | Retrieval-grounded questionnaire answering with citations, answer-library reuse, overclaim guardrails and review routing | Python, Anthropic API |
| **Demo automation** | [Demo Environment Builder](projects/02-demo-environment-builder) | One spec → org config, roster and months of case history whose Erlang-C staffing requirement tells a chosen story | Python, queueing math |
| | [Synthetic Contact Generator](projects/03-synthetic-contact-generator) | Interval actuals → individual contacts that reconcile back to every source metric | Python |
| | [Agent State Simulator](projects/04-agent-state-simulator) | Live agent-presence stream from a weekly schedule, with a rotating out-of-adherence pool | Node |
| **Product & revenue insight** | [Product Gap Intelligence](projects/01-product-gap-intelligence) | Turns gap tickets into a revenue-weighted dashboard behind an SSO gate (and the static-hosting leak that taught me how to build one) | Node, OIDC |
| | [Pipeline Diagnostic](projects/09-pipeline-diagnostic) | Quarter-over-quarter pipeline report: segment creation, funnel, loss reasons, tiered win-back list | Python |
| **Ops tools** | [Fair Round-Robin](projects/07-fair-round-robin) | Explainable, fair assignment of engineers to customer calls from calendar availability | JavaScript |
| | [Rotation Eligibility](projects/08-rotation-eligibility) | Enforces a labor rule by keeping exactly one eligibility tag per person: preview-first, idempotent writes | Python |

<p>
  <img src="docs/screenshots/product-gap-dashboard.png" width="49%" alt="Product gap dashboard">
  <img src="docs/screenshots/pipeline-diagnostic.png" width="49%" alt="Pipeline diagnostic report">
</p>

## How I work with AI

- **Agents write code; evals and tests decide when it's done.** Every project here has a test suite, and the LLM-backed ones have scenario evals that run offline against a baseline and live against the model.
- **Deterministic where possible, models where necessary.** The docs-sync classifier gets a code-based spec diff as a tool; the RFP assistant only sees retrieved, numbered sources. The model handles judgment, code handles facts.
- **Humans stay in the loop at the irreversible step.** Approvals before writer agents run, preview-by-default before writes, review flags instead of silent fixes.
- **Small, dependency-light tools that non-engineers can run.** Most projects use only the language's standard library, so they run anywhere with `python3` or `node`.

All projects ship with mock data and sample outputs, so you can read the results without running anything. See [docs/MOCK_DATA.md](docs/MOCK_DATA.md).

## Running everything

Requirements: Python 3.11+ and Node 20+. No installs needed except for the live LLM modes.

```bash
./run-all-tests.sh
```
