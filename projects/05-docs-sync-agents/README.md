# Docs-Sync Agents

**An LLM pipeline that reads every merge, decides whether the public API spec and on-call runbooks must change, and hands approved work to writer agents that open docs PRs.**

## Problem

API reference docs and incident runbooks rot because updating them is a separate task nobody owns at merge time. The hard part isn't writing the docs; it's *noticing* that a merge changed the contract or an operational behavior. Some cases are easy to miss: a new `/v2` route next to `/v1` is a version cutover, not an addition; a `Sunset` header means on-call needs a migration runbook; a retry-backoff change touches no API but changes what on-call sees.

## How it works

```
merge ──► classifier (LLM + diff_specs tool) ──► { spec, runbook, files, rationale }
              │                                         │
              │   skip/skip ──► done                    ▼
              │                              awaiting_approval (human)
              │                                         │
              ▼                                         ▼
        job store (jobs/<sha>.json)          writer briefs ──► coding agent ──► docs PR ──► CI gates
```

1. **Classify.** The classifier sees the merge diff and has one tool, `diff_specs`, a deterministic OpenAPI comparison (removed operations, type changes and new required request fields are breaking; new optional fields and same-version paths are additive; a new version prefix is a cutover). The model must call the tool, but decides from the code diff when the spec file hasn't been edited yet, because code usually lands before docs. Output is constrained to a JSON schema with enums.
2. **Gate on a human.** Anything other than skip/skip moves to `awaiting_approval`. The job file is a small state machine (`classified → awaiting_approval → writing → pr_opened | writer_failed`) that refuses illegal transitions.
3. **Brief the writers.** Approved jobs produce one brief per writer (spec, runbook) with hard rules: stay on versioned paths, keep `/v1` untouched on breaking changes, never invent commands, append a changelog entry.
4. **Check the output.** `lib/gates.js` lints runbooks (required frontmatter, required sections, `code_paths` that exist) and checks scope: if the classifier said `runbook=skip`, a PR that edits runbooks fails.

## Evals

`evals/scenarios/*` are real diffs with before/after specs and expected labels. The offline heuristic baseline gets 6 of 7. It misses `skip-test-only`, where a test file registers a route, which is exactly the judgment the LLM classifier is there for.

```
$ npm run eval
scenario                      expected            got
additive-code-first           additive/skip       additive/skip       ✓
breaking-v2-cutover           breaking/new        breaking/new        ✓
ops-only-backoff              skip/update         skip/update         ✓
skip-test-only                skip/skip           additive/skip       ✗
…
6/7 correct

$ npm install && ANTHROPIC_API_KEY=… npm run eval:live
```

**Mock data:** seven scenarios in [`evals/scenarios/`](evals/scenarios) (diff, before/after OpenAPI spec, expected labels), a fixture API repo with a runbook in [`fixtures/repo/`](fixtures/repo), and in [`sample-output/`](sample-output) the eval results and the job file for an approved v2-cutover merge, including the writer briefs.

## Run it

```bash
npm test                                         # 6 tests, no API key needed (the model client is faked)
node sync.js --repo path/to/api-repo --sha HEAD  # classify one merge (heuristic provider)
node sync.js --repo … --sha HEAD --provider anthropic
node sync.js --repo … --sha <sha> --approve      # print writer briefs for your coding agent
```

The classifier uses the official Anthropic SDK (`@anthropic-ai/sdk`, an optional dependency loaded only for the live provider) with tool use and structured output.

## Design choices

- **Deterministic tool, probabilistic judgment.** Spec comparison is code. The model only decides what code can't (intent of a diff that hasn't touched the spec yet).
- **Evals before prompts.** The scenarios were written first, from real misses, and every prompt change is run against them.
- **Humans approve, agents write, CI verifies.** Each stage has a narrow job and a machine-checkable output.
- **Rehearsable.** The original ran as a live demo: scripted "breaking", "additive", "ops-only" and "noise" merges against a fictional scheduling API, with the classifier's reasoning streamed to a control-plane UI and the writer agents opening real PRs within a few minutes.
