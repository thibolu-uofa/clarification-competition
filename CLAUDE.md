# The Clarification Challenge — working notes

Competition entry. We implement one clarification algorithm as a single file and submit it
as a PR to the upstream repo. Everything else here is local scaffolding.

- **Our submission:** `clarify/algorithms/curiosity_by_design.py` (class `CuriosityByDesign`)
- **Design doc / plan:** `notes/curiosity_by_design_plan.py` (prose in comments)
- **Team:** Curiosity by Design — Thibaud (`lutellie@ualberta.ca`)

**The submission file is proven to be the file that scored val TDS 0.6161** — AST-identical to
tag `baseline-val-0.6161`, checked with `tools/ast_identity.py`. It carries no dormant code from
any rejected experiment: everything measured and rejected lives in git history or on a branch, not
behind a flag in the file a reviewer reads. Re-check after any edit before submitting.

## Deadlines (from CONTRIBUTING.md; AoE 23:59)

| | |
|---|---|
| **Oct 9, 2026** | **Registration — a PR must be open.** Branch `submission/curiosity-by-design` is cut from upstream `66bc192` and holds the one algorithm file; see "Registration PR". |
| Nov 6, 2026 | Submission deadline; commits after it are ignored. The algorithm can keep changing until then. |
| Nov 20, 2026 | Final results, after the organizers run every merged system on the hidden test set. |

**Only systems that match or beat the strongest baseline are ranked**, and the strongest baseline
is Okanagan at TDS 0.5917 — that is where the 0.592 target comes from. Ranking is by TDS with nDCG
as the tie-breaker, on the **private test set**, not on val.

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
- **Do not tune on the validation split.** The exact certification in
  `.github/PULL_REQUEST_TEMPLATE.md` is "We developed on the released splits only and did not tune
  on validation instances". Running val to *measure* is the sanctioned workflow (CONTRIBUTING.md
  Step 4, and the public leaderboard is val); what is forbidden is choosing a configuration by its
  val result. Running a *baseline* on val involves no decision about our submission and so is
  outside the certification entirely. "One shot" is our own stricter convention, kept because each
  extra val run is an invitation to select on it.

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

**All three on the same 773 train examples** (paired; ours is `part`):

| | TDS | Pass@1 | ask% | $/task |
|---|---|---|---|---|
| ours | **0.3789** | **39.46%** | 100.0 | 0.0065 |
| Okanagan | 0.3490 | 36.23% | 90.2 | 0.0006 |
| DirectLLM | 0.3247 | 32.47% | 0.0 | 0.0004 |

vs Okanagan: **+3.23pp**, 61 gained / 36 lost. So on train we are the best of the three — by a
clear margin over DirectLLM and a modest one over Okanagan, which gets there for a tenth of the
cost.

### The train/val gap is real and bigger than composition

DirectLLM scores **32.76%** on train (n=815) and **49.74%** on val (published). Two parts:

- **Composition.** Train is 79% MBPP, val 54.5% (`tools/split_offset.py` prints the table), and
  pass rates split hard by dataset — ours is **HumanEval 66.7% / MBPP 32.6%**, a 34pp spread.
  Reweighting DirectLLM's train cells onto val's proportions moves it 32.76% → 37.66%.
- **Residual difficulty.** The remaining **+12.08pp** to its published 49.74% is not composition.
  Train is simply harder, cell for cell.

So post-stratification alone **under-predicts val by ~12pp** and must not be used on its own —
it is validated against a baseline's known val number, not trusted a priori.

**Okanagan, the second baseline, breaks the transfer.** Also faithful ($0.00063/task vs published
$0.0006, ask rate 90.2% vs 88.6%, no exceptions), and on the same train sample it scores **36.20%**
against a published val **61.30%**:

| baseline | train (ours, n=815) | val (published) | raw offset | offset after composition |
|---|---|---|---|---|
| DirectLLM | 32.76% | 49.74% | +16.98pp | +12.08pp |
| Okanagan | 36.20% | 61.30% | **+25.10pp** | **+19.24pp** |

The two offsets disagree by 7–8pp, so **the train→val offset is algorithm-dependent and cannot be
used to translate our number**. Any claim of the form "our train 39.5% means val X%" is unsupported;
the honest statement is a range so wide it decides nothing (≈52% to ≈59%).

Two hypotheses, not yet separated:
- **H1** train is genuinely harder and stronger algorithms gain more from val's easier tasks;
- **H2** the published val numbers were produced under conditions we are not reproducing (a
  different benchmark revision or model snapshot), in which case the leaderboard is not a yardstick
  for us at all.

Both baselines reproduced their published **cost/task and ask rate** almost exactly, which shows we
are running the algorithms as intended — but says nothing about which hypothesis holds. The
decisive, cheap test is **DirectLLM on val** (770 examples, ~$0.33): if it reproduces ~49.7%, H1
holds; if it lands near its train 32.8%, H2 holds and every leaderboard comparison in this file is
void. Running a *baseline* on val does not tune our submission, so it does not touch the
certification — but it has not been run yet.

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

## Validation result (one-shot, 2026-10-05)

Measured once, with `overrides: (defaults)`, on the full 770-example val split. 770/770 rows,
zero exceptions, zero not-ok tasks, `docs/data/leaderboard.csv` untouched. The exact file is
tagged **`baseline-val-0.6161`**, and it is what `clarify/algorithms/curiosity_by_design.py` now
contains. (The copy once kept as `basic_curiosity.py` was deleted on 2026-10-09 — once the
submission file was restored to the baseline the two were the same program under two names, and a
second `ClarificationAlgorithmBase` subclass in the tree is a trap, not a safety net. The tag is
the fallback.)

| | |
|---|---|
| TDS | **0.6161** |
| Pass@1 | **64.16%** (sd 1.73pp) |
| nDCG | 0.8675 |
| clarification rate | 99.87% |
| over-asking | 100.00% |
| high-quality clarification | 86.87% |
| cost/task | $0.0069 |

Slices: unambiguous prompts 73.63% (n=91), ambiguous 62.89% (n=679); HumanEval 72.86% (n=350),
MBPP 56.90% (n=420); by path, widened 68.10%, fallback 65.23%, difference 56.15%.

**Position: 2nd of six**, above the strongest baseline (Okanagan 0.5917) and so rankable; below
GatedClarification (0.6410). At sd 1.73pp on Pass@1 (±0.017 TDS) we are ~1.1 sd above
ContractFirst and ~1.4 sd below the leader, and **ranking is on the private test set, not val.**

**The measured train→val offset for our algorithm is +24.70pp** (39.46% → 64.16%), close to
Okanagan's +25.10pp and nothing like DirectLLM's +16.98pp. This retires all three earlier
translation estimates, which were wrong in the same direction: 48.3% (post-stratification alone),
and the 52–59% range transferred from the baselines. **Do not estimate a val number from train
again — the offset is algorithm-dependent and was understated every time.**

nDCG is worth attention: 0.8675 on val against 0.96 on train, and high-quality clarification
86.87% against 95.9%. nDCG is the ranking tie-breaker and 13% of val questions are marked down,
which has never been looked at.

## Run names

Tags are terse and were chosen badly; this is the glossary until they are renamed.

| tag | what it is |
|---|---|
| `big800` | 815-example train sample, algorithm **before** the partitioning work |
| `part` | 815-example train sample, **current** algorithm (partitioning + 11 fixes); 773 of 815, battery |
| `base`, `repair` | early 160-example runs, pre-partition and +crash-repair |
| `abl_*` | ablation arms at n=160, one config knob each (`abl_nopart` = `--partition_inputs False`) |
| `base800_direct`, `base800_okanagan` | SDK baselines on our 815-example train sample |
| `cbd_val` | the one-shot val run above: the submitted algorithm, 770 examples, TDS 0.6161 |
| `synth_val` | the synthesis arm on val, 770 examples, TDS 0.5899 — rejected |
| `ratelimited_arms/` | four arms that measured the rate limiter, kept as evidence; see the concurrency note |

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
| `tools/ast_identity.py` | two files are behaviourally identical: AST compared with docstrings stripped, optional class rename |
| `tools/dormant_check.py` | a flagged-off change cannot affect the result: strips the named additions and all logging, then compares against the baseline |
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

## Deferred ideas (were TODOs in the submission file; moved here 2026-10-05)

The submission file carries no TODOs - a reviewer reads it first. Each item below keeps its
measured ceiling so the next change is chosen on evidence rather than on which TODO was nearest.

1. ~~Adjudicate a split vote with the clarification answer~~ — **built, measured, rejected.**
   See "Things already tried". The code was removed from the submission file on 2026-10-09; read
   it back with `git show 92407fa:clarify/algorithms/curiosity_by_design.py`.
2. **Per-input branch traces** (`run_candidates` / `SANDBOX_SCRIPT`). Instrument each candidate
   with `ast.NodeTransformer` so the sandbox records which conditions each input took. Enables 3
   and 4, and separates "inputs too weak" from "candidates share one reading" - today both look
   like one behaviour group. **Riskiest edit in the file:** it touches the one script that builds
   the whole behaviour table, and a broken transformer loses every cell silently.
3. **Coverage-guided widening** (`widen_search`). When every condition has been taken both ways,
   more inputs cannot separate anything; add the divergent candidate instead. Needs 2.
4. **Input shrinking and multi-input questions** (`pick_distinguishing_inputs`,
   `questions_from_differences`). Shrink the chosen input while the split holds, and show two or
   three inputs that split the same way so the model sees the rule, not the instance. The one
   item with an independently measurable target: val nDCG 0.8675 / 86.87% high-quality.
5. **Derive inputs from the candidates instead of asking** ("Option B" in
   `notes/curiosity_by_design_plan.py`). Collect conditions and compared constants with `ast`,
   use those and their neighbours as partition boundaries, filter through an `is_valid` the model
   supplies once. 14.3% of generated inputs are rejected by every candidate - but val says tasks
   with clean inputs pass 65.97% against 56.25%, a **+1.8pp** upper bound that is probably a
   selection effect. Largest build, weakest evidence.
6. **Decide `ask_when_agree`** (`fallback_question`). A question discounts the task ~4%, so
   asking only pays when `pass_rate_with x 0.96 > pass_rate_without`. The arm was started and
   killed when the suite was paused; still unmeasured.
7. **Recover `candidate`-aliased functions** (`defines_entry_point`). Some prompts name the
   function `candidate`; such a program is discarded today. Narrow: 76 of 771 train tasks never
   got 2 usable candidates (passing 23.68%), and this is one of several causes.
8. **A question-only behaviour signature** (`group_by_behaviour`). "Raise on empty input" vs
   "return 0" is a real open requirement, but the final program cannot afford to raise, so the
   raiser is discarded. Keeping it for *asking* while excluding it from the *vote* would recover
   the question. Deliberate trade-off, documented in the docstring rather than deferred.

Moot: drafting a second question from the remaining differences assumes a budget above one turn,
and the official setting fixes `max_clarification_turns=1`.

## Things already tried — don't redo them

- **Adjudicating a split vote with the clarification answer: actively harmful on the tasks it
  touched.** When the post-clarification vote split, one model call asked which group's
  behaviour matched the author's answer instead of taking the majority. It worked exactly as
  designed — fired on 104 of 815 train tasks (12.8%, matching the predicted rate), returned a
  usable choice every time, overruled the majority on 31 of those (29.8%), and cost ~nothing
  (13.8 vs 13.7 calls/task, $0.0066 vs $0.0065). Overall it read **+0.91pp** paired (39 gained,
  32 lost, p=0.48) — but the attribution kills it, because **only the overruled tasks received
  different treatment** and everywhere else the two runs differ by resampling alone:

  | slice | n | baseline | with adjudication | gained/lost |
  |---|---|---|---|---|
  | never fired (pure re-roll) | 679 | 41.5% | 43.0% | 36 / 26 |
  | fired, agreed with majority | 67 | 31.3% | 29.9% | 3 / 4 |
  | **fired, overruled the majority** | **27** | **7.4%** | **0.0%** | **0 / 2** |

  Not one overruled task passed. The headline gain is resampling luck in the untouched slice.
  **The lesson generalises beyond this change:** a split vote marks a task nobody solves
  (baseline 7.4%), not a choice made wrongly, so the "+4.6pp ceiling" computed by assuming
  split-vote tasks could be lifted to unanimous-level performance was never real — it was a
  selection effect, flagged at the time and then under-weighted anyway. Treat every
  "if slice X behaved like slice Y" ceiling in this file the same way.
  The code was first left in the file behind `adjudicate_vote="never"` and was removed entirely on
  2026-10-09, when the file was restored to the 0.6161 baseline for submission.

- **Synthesising one final program from every candidate: −2.73pp on val, the clearest negative of
  the four.** The design was the right shape for the problem — 59.4% of tasks have *no* correct
  candidate, so selection cannot help them and only generation can. Hand the model the whole
  dossier (original specification, the question and its answer, every round-1 and round-2 candidate
  with its observed behaviour table) and ask for one final program, framed so the attempts read as
  evidence rather than answers: "most of them are wrong ... a majority among them carries no
  weight". Bundled with pooling round-1 candidates into the final vote, revising candidates against
  the answer, and preferring a revised program within its group.

  | | baseline | synthesis |
  |---|---|---|
  | TDS | **0.6161** | 0.5899 |
  | Pass@1 | **64.16%** | 61.43% |
  | nDCG | 0.8675 | **0.8831** |

  Paired on 770 val examples: **−2.73pp, 54 gained / 75 lost.** The mechanism was not broken —
  synthesis produced on 762/770, the sandbox veto rejected 43, so it was used on 719 (93.4%) — and
  it agreed with the vote winner on 85.5% of tasks, so the 14.5% where it departed carry the entire
  effect. Cost rose to $0.0088/task from $0.0069 (18.8 calls/task against 13.8). Damage concentrated
  in **HumanEval, 72.86% → 68.00%**, our strongest half; the unambiguous control slice is identical
  at 73.63% both ways, which is the sanity check. The train counterfactual — both programs logged
  from the *same* generation, so no resampling noise at all — had already read the same direction
  (vote 38.77% vs synthesis 37.53%, 810 pairs). Kept on branch `experiment/synthesis-arm`.

  **Two lessons.** First, nDCG moved *up* while Pass@1 moved down: the synthesis only rewrites the
  final program, so that is resampling on the question side, and a metric that moves where no
  treatment was applied is noise, not evidence. Second, a prediction from the mechanism — "val has
  more correct candidates for a reviewer to recognise, so synthesis should transfer better than on
  train" — was reasonable, agreed by both of us, and **wrong in the measured direction**. Mechanism
  stories are hypotheses to test, never grounds to skip the measurement.

### Measurements worth more than any of the four changes (2026-10-08/09)

- **Input pair separation is 79.6%, not 21.3%.** The earlier figure measured *crash detection* and
  was mislabelled as discriminating power; three arguments were built on it before the user caught
  it. Our inputs separate four right/wrong program pairs in five.
- **Selection headroom is only +1.99pp, and ~75% of it is blocked by input blindness.** Final round:
  37 tasks have both a passing and a failing candidate; on 21 of those every candidate looks
  identical to us; we return a failing program though one passed on **16 tasks (1.99pp)**, of which
  **12 are blocked by one visible behaviour** and 4 are ranking mistakes. So input work is real but
  capped near **1.5pp** — and the mutation score says 41% of small semantic changes already slip
  past ~19 inputs. Measure any input change against those 12 tasks, never against aggregate Pass@1.
- **The churn floor: 62 discordant tasks out of 679 with zero treatment.** Two runs of the *same*
  config disagree on ~9% of tasks. Any arm whose discordant count is near 62 has done nothing,
  whatever its net reads. This is the number that makes most single-arm results unreadable.
- **59.4% of tasks have no correct candidate at all**, and on 84.8% of unsolved tasks every
  candidate agrees on one wrong behaviour. Failures are 65.2% wrong output / 34.5% crashes.
  Generation, not selection, is the binding constraint — but the two generation-side changes tried
  so far (revision, synthesis) both lost.

- **Crash-repair alone: no effect.** Cut input failures 317 → 104 but Pass@1 moved +1 task of
  160. Paired view: 9 gained, 8 lost, repair implicated in 1. Crash-freeness on generated
  inputs is a weak proxy for passing hidden tests.
- **Personas are mostly not doing the work** — 62% of round-1 behaviour splits cut across
  persona boundaries, so temperature noise drives the diversity. `--use_personas False` is an
  untested, cheap experiment.
- **14.3% of generated inputs are rejected by every candidate**, and 67 of 815 tasks have
  essentially no usable inputs. Of those, only ~43% are arity mismatches — and the common
  direction is too *few* arguments (unfixable by rewrapping), not too many.

## Registration PR (prepared 2026-10-09)

Branch **`submission/curiosity-by-design`**, cut from upstream `66bc192` so it carries no local
scaffolding, containing exactly one file: `clarify/algorithms/curiosity_by_design.py`.

Everything else in this repo is deliberately *not* in it — `CLAUDE.md`, `tests/`, `notes/`,
`tools/`, `runs/` and our `.gitignore` additions are local and would be noise in a review. Verify
with `git diff --name-only 66bc192 submission/curiosity-by-design`: it must print one path.

The PR body is reproduced in `notes/pr_body.md`. The leaderboard row is **not** touched — the
"No leaderboard change" box is ticked, `docs/data/leaderboard.csv` is untouched, and the val
numbers go in the body as prose. Adding a row is a separate PR once the organizers confirm the
result, and editing that file would make the diff look like a score claim we cannot verify.

Certification: "developed on the released splits only and did not tune on validation instances."
The honest version of why this holds, stated plainly because it is the one claim in the PR we might
be asked to defend:

- **The shipped configuration predates every val run.** `DEFAULT_CONFIG` was fixed on train, and
  the first val run measured that already-frozen file. Nothing in the shipped file was chosen by a
  val comparison, because there was no val number to choose by when it was chosen.
- Val was run twice, both times to *measure* a finished configuration, which CONTRIBUTING.md Step 4
  sanctions and the public leaderboard is built on.
- **The uncomfortable part, recorded rather than glossed:** the synthesis arm was rejected after a
  val run, and had it improved on val we would have shipped it — that would have been val
  selection. What keeps the decision clean is that train evidence pointed the same way *first* (the
  paired counterfactual, no resampling noise, vote 38.77% vs synthesis 37.53%), so val confirmed a
  conclusion it did not produce. Thin, and it only holds because the answer was negative.
- **The rule going forward, which is cheap to keep:** decide on train, then run val once to report.
  One val run per configuration, and never two configurations compared on val. We have now spent
  two of those runs; a third that picks between arms would void the certification.

## Conventions

Comments explain *why*, never *what*, and are written as prose in the surrounding style. State
measured numbers with their n. When correcting an earlier claim, say so plainly — several
conclusions in this file replaced earlier wrong ones (the 160-example subsample was
optimistic by ~9pp; path differences are selection effects).
