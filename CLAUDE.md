# The Clarification Challenge — working notes

Competition entry. We implement one clarification algorithm as a single file and submit it
as a PR to the upstream repo. Everything else here is local scaffolding.

- **Our submission:** `clarify/algorithms/curiosity_by_design.py` (class `CuriosityByDesign`)
- **Design doc / plan:** `clarify/algorithms/curiosityByDesign_plan.py` (prose in comments)
- **Team:** Curiosity by Design — Thibaud (`lutellie@ualberta.ca`)

## Spending rule (read first)

**Never start a run that spends API credits without the user asking in that message.**
Propose it with a cost and time estimate, then wait. Measured cost is **~$0.0067/task**, so
an 815-example run is ~$5.50 and ~55 min at 10 shards.

Free, no permission needed: unit tests, static analysis, trace-log analysis,
`tools/score.py` on an existing results file, and re-running `evaluate_responses.py` over
already-generated output (no model calls). Prefer these to answer a question.

## Stack and commands

Python 3.13, `uv`, ruff (line-length 100, E/F/I/B, E501 ignored). Deps: litellm, evalplus,
fire, rich, numpy, tqdm. `ruff` is **not** installed in `.venv` — don't assume lint runs.

```bash
.venv/bin/python generate_responses.py clarify/algorithms/curiosity_by_design.py --split val
.venv/bin/python evaluate_responses.py --split val --generation_path X --output_path Y
.venv/bin/python scripts/validate_repository.py      # the PR's own anti-cheat check
```

Docker is required for `env.exec_code`; image `ganler/evalplus` (3.5 GB, pulled). A sandbox
round trip is ~0.9s, so **runtime is ~93% LLM latency** — parallelise across tasks, never
optimise the sandbox.

## Submission constraints (PR check enforces these)

- Only `env.llm`, `env.ask_human`, `env.can_ask`, `env.exec_code`, and the `history` /
  `prompt_cost` properties. No test access, no credentials, no file writes from the algorithm.
- **Every attribute or key access starting with `_` is rejected** (SEC001-004). That includes
  `super().__init__()`, `self._helper()`, and `type(e).__name__`. The base class already
  merges `DEFAULT_CONFIG` with CLI overrides, so no constructor is needed.
- Exactly one public `ClarificationAlgorithmBase` subclass per file; prefix experiments with `_`.
- Standard library plus existing `pyproject.toml` deps only.
- **Do not tune on the validation split** — the PR template requires certifying this. Develop
  on train; val is a one-shot reported number.

## Official evaluation settings

`openai/gpt-4.1-mini`, temperature 0.7, `max_clarification_turns=1`, `num_samples=1`,
budgets 1.0, `--split val` (770 examples). Temperature is **fixed by the harness** —
`env.llm(messages)` takes messages only, so the algorithm cannot lower it.

## Scoring — what actually matters

`TDS = mean(pass_i * log(10)/log(10 + turns_i))`, at `evaluate_responses.py:100`. It is
**printed, never persisted**; re-run the evaluator over an existing results file and it
reprints for free.

One question costs 3.97%. We ask on ~99% of tasks, so in practice **`TDS = Pass@1 × 0.9603`
exactly**. The score is Pass@1; question tactics are second-order.

**Target: beat TDS 0.592**, which needs **Pass@1 ≥ 61.7%** — on **val**. Every number we
measure is on train, and train is ~17pp harder (below), so a train Pass@1 near 45% may already
clear it. Never compare a train figure to the leaderboard without the offset.

## Measured state (train subsample)

Two runs, compared paired on the 773 examples they share. The `part` run lost 42 examples to
a dead laptop battery mid-generation and was not topped up, so its n is 773, not 815; on that
subset `big800` reproduces its own published numbers (0.3590 / 37.39), which is what makes
the comparison readable.

| | `big800` (pre-partition) | `part` (partitioning + 11 fixes) |
|---|---|---|
| TDS | 0.3590 | **0.3789** |
| Pass@1 | 37.39% | **39.46%** |
| Pass@1, never-ambiguous prompts (n=106) | 46.23% | 45.28% |
| nDCG / high-quality clarification | 0.95 / 95% | 0.96 / 95.9% |
| cost/task | — | $0.0065 |

Paired: 50 gained, 34 lost, net **+16 examples (+2.07pp)**. A sign test on the 84 discordant
pairs gives two-sided **p=0.10**, so the direction is encouraging but the effect is not
established — it is the same size as the noise band. The whole gain sits in the ambiguous
slice (+2.55pp, n=667); the never-ambiguous control moved -1 example, i.e. not at all.

**Corrected (2026-10-02): the clarification machinery is the part that works.** This section
used to read "even on fully-specified prompts we only pass 46.3%, so the gap is code
correctness" — true, but it implied our asking was not earning anything. Measured against
DirectLLM on the same 773 examples (see **Where we stand against the baselines**), the split is:

| slice | DirectLLM (never asks) | ours |
|---|---|---|
| unambiguous prompts (n=106) | 44.34% | 45.28% |
| ambiguous prompts (n=667) | 30.58% | **38.53%** |

On fully-specified prompts we are level with an algorithm that asks nothing, so the ~45% ceiling
there is a **code-generation limit we share with the baseline**, not a clarification failure.
Every point of our advantage sits on ambiguous prompts, which is what the machinery is for.

Path splits are **selection effects, not treatment effects** — `difference` means the
candidates disagreed immediately (hard task, 27.7%), `widened` means they agreed first
(easy task, 48.1%). Don't read them as "this path is better".

Run-to-run noise: at n=160, ~17 tasks flip either way, so nothing below ~5pp is measurable
there. n=815 gives ~1.2pp. **Use ≥800 examples for any decision.**

**Measured, not asserted: n=160 gets the sign wrong.** The `part` vs `big800` contrast is
+2.07pp at n=773 (50 gained / 34 lost). Restricted to the 21 task ids of
`data/splits/train_sample.txt`, the same two runs read **−2.05pp** (6 gained / 9 lost, p=0.61).
So the error bar at n≈150 covers ±4pp *including the direction*. Treat any Pass@1 number from
the 160 subsample as unsigned noise; what that subsample does resolve is the mechanism counters
in the trace, which are near-deterministic, and cost. (The 21 task ids are also easier than the
benchmark average — 47.5% vs 37.4% Pass@1 — so their absolute numbers are not comparable to a
full-split figure either.)

## Where we stand against the baselines (measured 2026-10-02)

Every leaderboard number in `docs/data/leaderboard.csv` is on **val**; everything we measure is
on **train**. Comparing the two directly was the mistake that made us look hopeless. The fix is
to bring the baseline to our examples: `tools/baseline.py --algorithm clarify/baselines/<x>.py`
on our own split, which needs no val calls and gives a paired comparison.

**DirectLLM (`LLMClarification`) on our 815-example train sample.** Faithful to the leaderboard
run: $0.00043/task vs published $0.0004, clarification rate 0.0% vs published 0.0%, no
exceptions. Paired on the 773 examples we both cover:

| | TDS | Pass@1 |
|---|---|---|
| DirectLLM | 0.3247 | 32.47% |
| ours | **0.3789** | **39.46%** |

**+6.99pp Pass@1, 81 gained / 27 lost** of 108 discordant pairs — far outside the noise band, and
we win on TDS too despite paying the ask-rate discount that DirectLLM does not. **We are above
the weakest baseline, not below it.**

### The train/val gap is real and bigger than composition

DirectLLM scores **32.76%** on train (n=815) and **49.74%** on val (published). Two parts:

- **Composition.** Train is 79% MBPP, val 54.5% (`tools/split_offset.py` prints the table), and
  pass rates split hard by dataset — ours is **HumanEval 66.7% / MBPP 32.6%**, a 34pp spread.
  Reweighting DirectLLM's train cells onto val's proportions moves it 32.76% → 37.66%.
- **Residual difficulty.** The remaining **+12.08pp** to its published 49.74% is not composition.
  Train is simply harder, cell for cell.

So post-stratification alone **under-predicts val by ~12pp** and must not be used on its own —
it is validated against a baseline's known val number, not trusted a priori. Transferring
DirectLLM's measured offset to us puts our val-equivalent Pass@1 at roughly **56–60%**
(39.46% + 17pp raw, or 48.28% + 12pp composition-adjusted): above ClarifyGPT (57.3%), near
Okanagan (61.3%), below GatedClarification (66.8%). **One baseline, one offset** — an Okanagan
run on the same train sample is the independent check, and until it lands the transfer is a
single data point, not a calibration.

### Leaderboard reference (val, same official settings)

| algorithm | TDS | Pass@1 | ask rate | $/task |
|---|---|---|---|---|
| LLMClarification (DirectLLM) | 0.497 | 49.7% | 0% | 0.0004 |
| ClarifyGPT | 0.562 | 57.3% | 49.9% | 0.0092 |
| Okanagan | 0.592 | 61.3% | 88.6% | 0.0006 |
| ContractFirstClarifier | 0.597 | 62.1% | 92.7% | 0.0010 |
| GatedClarification | 0.641 | 66.8% | 100% | 0.0006 |

Okanagan is worth staring at: 61.3% at **$0.0006/task**, a tenth of ours, with 5 `env.llm` call
sites. Our 13.7 calls/task buy a lower number.

## Run names

Tags are terse and were chosen badly; this is the glossary until they are renamed.

| tag | what it is |
|---|---|
| `big800` | 815-example train sample, algorithm **before** the partitioning work |
| `part` | 815-example train sample, **current** algorithm (partitioning + 11 fixes); 773 of 815, battery |
| `base`, `repair` | early 160-example runs, pre-partition and +crash-repair |
| `abl_*` | ablation arms at n=160, one config knob each (`abl_nopart` = `--partition_inputs False`) |
| `base800_direct`, `base800_okanagan` | SDK baselines on our 815-example train sample |

## Known SDK bugs and gotchas (not ours; work around them)

- `clarify/runtime.py:158` stringifies ground truth, and one task's expected answer has
  >4300 digits → `ValueError`, killing a whole evaluation pass. Fix: `PYTHONINTMAXSTRDIGITS=0`
  (already in `tools/baseline.py`).
- `clarify/data.py:40` derives the data root from the split file's own path by stripping
  components while `"split"` is in it. **Shard split files must live in `data/splits/`** or
  the benchmark silently loads 0 instances and the run exits 0 having done nothing.
- `clarify/data.py:59` asserts one benchmark per dataset file, so a mixed Mbpp+HumanEval
  *dataset* file cannot load. Use a split file instead.
- `env.py:175` reads the user's answer with `` ANSWERS=`(.+?)` `` — a backtick inside the
  answer truncates it. Never put backticks in a question; `plain_question()` strips them.
- `env.py:233/238` return `"Irrelevant question."` / `"Cannot answer the given question."`
  instead of an answer. `usable_answer()` filters these.
- `generate_responses.py` sets `need_clarification` from
  `len(example.get("clarifications", [None])) > 0`, and train examples have no
  `clarifications` key, so it is **always True** and the built-in over-asking rate is
  permanently 0.00% on train. `tools/score.py` computes the real one.
- `data/mbpp_demo_test.jsonl` has no hidden requirements, so the simulated user improvises and
  can contradict its own tests. **Unusable for measuring Pass@1** — smoke tests only.
- Parallel workers are `ProcessPoolExecutor`/spawn, so a `logging` handler attached in the
  parent never sees child records. That is why runs shard with `max_workers=1` each.

## Local tooling (gitignored, not part of the PR)

| | |
|---|---|
| `tools/baseline.py` | generate → merge → evaluate → score; `--skip_generation` retries the free part |
| `tools/run_traced.py` | one shard, attaches the trace log handler |
| `tools/build_subsample.py` | seeded train subsample; same seed nests, so 160 ⊂ 815 |
| `tools/score.py` | recomputes TDS, breaks it down by path, real over-asking rate |
| `tools/compare_runs.py` | two results files, restricted to the examples they share: paired flips + sign test |
| `tools/ablation_table.py` | many arms vs one control, restricted to a split's task ids; score table, control slice, mechanism counters |
| `tools/split_offset.py` | per-variant-cell pass rates reweighted onto val's composition, against the published val number where one exists |
| `tools/run_arms.py` | runs the ablation suite two arms at a time; skips arms already complete, so an interrupted suite resumes |
| `tests/test_helpers.py` | regression tests for the pure helpers; one assertion per trap below. `.venv/bin/python tests/test_helpers.py` |
| `runs/` | all outputs; `data/splits/train_sample{,800}.txt` are the fixed subsamples |

The algorithm emits one JSON trace record per task via
`logging.getLogger("curiosity_by_design")` — silent with no handler, no file writes, so it is
submission-safe. **Merging must not dedupe on `(task_id, prompt)`**: the benchmark contains
distinct examples sharing both (e.g. `Mbpp/562`, `Mbpp/574`).

## Traps in our own code (found by review, now fixed — don't reintroduce)

- **A sandbox `skipped` cell is not a behaviour.** The 20s deadline fills the rest of a row
  with `skipped` to keep its width. Comparing those split two *identical* programs into two
  groups and drafted the one question from a timing artefact. `valid_indices` now drops any
  column where **any** row was skipped.
- **`"rank for final selection" is a no-op in the normal case.`** `group_by_behaviour`
  already discards every candidate failing a valid input whenever one clean candidate exists,
  so all surviving groups score 0 and the sort collapses to group size (the old majority
  vote). Ranking — and therefore `repaired_or_original` — only bite on the fallback path
  where nothing was clean. Read the comment at `final_program` before tuning
  `repair_attempts`.
- **Only module-level definitions count.** `ast.walk` picked up `class S: def f(self, a)`,
  yielding arity `(2,2)` including `self`, which rejected every correct input and emitted a
  hint naming `self` as a parameter. `module_level_nodes` descends into `if`/`try`/loops but
  never into a function or class body, and returns last-first so a redefinition wins.
- **Prompts must use Python syntax.** `json.dumps` in `readable` produced `returns true` and
  `returns null`; `canon`'s encoding also leaked as `[["int", 1]]`. Both reached
  `DIFFERENCE_TEMPLATE`, the one prompt that must make a disagreement legible.
- **List distinct behaviours, not groups.** Two groups can agree at the chosen input and
  differ elsewhere, which rendered "Behaviour 1: returns 5 / Behaviour 2: returns 5" under a
  template saying "two implementations disagree".
- **The clarification turn is spent before the answer is read**, so discarding a terse but
  complete reply ("Descending order.") pays the score penalty for nothing. Reject refusals
  and mid-sentence fragments only.
- Counters that run twice per task (`resolved_inputs`, `group_by_behaviour`) must
  **accumulate or use per-stage keys** — overwriting silently corrupted the very fields a
  change was being measured by.

## Algorithm shape

Sample N candidates → generate inputs → run all candidates × all inputs in **one**
`exec_code` call → group by behaviour → turn a disagreement into one question → ask →
regenerate from the answer by majority vote.

Config knobs are in `DEFAULT_CONFIG` and overridable from the CLI, so A/B tests need no code
change: `--partition_inputs False`, `--input_retries 0`, `--repair_attempts 0`,
`--use_personas False`. That is true of `generate_responses.py` (fire turns unknown flags into
`**kwargs`), but our own drivers used to drop them; `tools/baseline.py` and `tools/run_traced.py`
now take `--algorithm` and repeatable `--set key=value`, and each value is read with
`ast.literal_eval` so `False` arrives as a bool rather than a true-ish string. An unknown key
fails fast in the base class, which is the point — an arm must not run 160 tasks with a silently
ignored flag. `input_retries` is a real count (each retry is one model call);
`exec_timeout` is clamped to a positive floor because `setitimer(.., 0)` disarms the timer
rather than tightening it, which loses the whole table instead of one cell.

Input partitioning, input regeneration and crash-triggered repair have now been measured
together as one bundle (`part` run, see **Measured state**): +2.07pp paired, p=0.10. Nothing
separates their individual contributions, and the bundle is not worth re-litigating at that
n — the next ≥800-example run should test a different change, not re-measure this one.

## Things already tried — don't redo them

- **Crash-repair alone: no effect.** Cut input failures 317 → 104 but Pass@1 moved +1 task of
  160. Paired view: 9 gained, 8 lost, repair implicated in 1. Crash-freeness on generated
  inputs is a weak proxy for passing hidden tests.
- **Personas are mostly not doing the work** — 62% of round-1 behaviour splits cut across
  persona boundaries, so temperature noise drives the diversity. `--use_personas False` is an
  untested, cheap experiment.
- **14.3% of generated inputs are rejected by every candidate**, and 67 of 815 tasks have
  essentially no usable inputs. Of those, only ~43% are arity mismatches — and the common
  direction is too *few* arguments (unfixable by rewrapping), not too many.

## Conventions

Comments explain *why*, never *what*, and are written as prose in the surrounding style. State
measured numbers with their n. When correcting an earlier claim, say so plainly — several
conclusions in this file replaced earlier wrong ones (the 160-example subsample was
optimistic by ~9pp; path differences are selection effects).
