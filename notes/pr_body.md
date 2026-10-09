## Submission type

- [x] **New submission** — adds `clarify/algorithms/<name>.py`
- [ ] **Update of an existing submission** — replaces our earlier file
- [ ] **Leaderboard update only** — adds/updates our row in `docs/data/leaderboard.csv` (`confirmed=false`)

## Team

| | |
| --- | --- |
| **Team name** | Curiosity by Design |
| **Team members** | Thibaud (University of Alberta) |
| **Main contact** | Thibaud — lutellie@ualberta.ca |
| **License** | MIT |

## Algorithm

**File:** `clarify/algorithms/curiosity_by_design.py`
**Class name:** `CuriosityByDesign`

**Summary**

The algorithm finds what a task leaves open by differential testing, and asks about that rather than guessing. An underspecified requirement shows itself as a disagreement between independent readings of the same prompt: if two correct-looking implementations behave differently on some input, the prompt did not decide what that input should do, and that is what the one question is spent on. Several candidate implementations are sampled under different stated user personas, executed against generated inputs inside a single `env.exec_code` call, and grouped by observed behaviour; the input that splits the candidates most evenly becomes the question. The answer is folded back into the specification, the candidates are regenerated from it without personas, and the returned program is the largest group that fails no valid input.

**Core mechanism**

Per task:

1. **Sample candidates** (`num_candidates=4`) from the prompt, each prefixed with a different stated *user* persona ("I'm a beginner who is still learning Python.", "I'm a senior software developer."). The persona describes who wants the code, not a role to play, so readings differ for reasons other than sampling temperature. Each request is retried up to `generation_attempts=3` times if the response contains no parseable fenced block.
2. **Generate inputs** (`num_inputs=10`) with one `env.llm` call, then reconcile them against the candidates' *real* signatures parsed with `ast`. An input that fits no signature is rewritten where it only makes sense as a single argument and dropped otherwise; if most inputs fit nothing, inputs are re-asked once (`input_retries=1`).
3. **Execute** every candidate against every input in **one** `env.exec_code` call. The sandbox harness records, per cell, the return value, exception type, non-termination, mutation of the arguments, and anything printed, under a per-call `signal.setitimer` deadline (`exec_timeout=2.0`) and an overall budget.
4. **Group by behaviour.** Two interpretive rules do the work here. A candidate that crashes on an input the others handle is a bug, not a reading, and is discarded while any clean candidate survives. An input that *every* candidate rejects says more about the input than about the task and is excluded from the comparison (`partition_inputs=True`). A cell the deadline skipped is not a behaviour and never separates two candidates.
5. **Widen once** if every candidate agrees (`search_rounds=2`): ask for inputs aimed further at the boundaries before concluding the prompt is unambiguous.
6. **Ask.** On a disagreement, up to `max_differences=3` distinguishing inputs are each drafted into a candidate question, and the draft that best fits the published judging criteria — one specific requirement, answerable, not about implementation details or tests — is the one asked through `env.ask_human`. When the candidates agree, one question is still drafted from the prompt alone (`ask_when_agree=True`), because a prompt that several independent readings happen to agree on can still be underspecified.
7. **Decide.** The answer is appended to the specification and the candidates are regenerated from it *without* personas, since the goal is now agreement rather than diversity. Those are executed and grouped again; the winner is the largest group failing no valid input. The final program is repaired once if it still crashes on an input (`repair_attempts=1`), and the unrepaired version is kept unless the repair is strictly better.

**Degradation.** `env.exec_code` requires Docker. Where it is unavailable, or the sandbox returns nothing usable, the algorithm falls back to asking the model directly for the single most critical question about the prompt, so a result still comes back without an execution environment. Answers that are refusals (`"Irrelevant question."`, `"Cannot answer the given question."`) or mid-sentence fragments are rejected, but a terse yet complete reply is kept — the clarification turn is spent before the answer is read, so discarding a usable short answer pays the discount for nothing.

**Related work / inspiration**

Differential testing as a specification oracle, in the spirit of randomized differential testing (McKeeman, 1998) and its use in compiler testing (Csmith; Yang et al., PLDI 2011) — here applied to disagreement between LLM samples rather than between compilers. The idea that disagreement among sampled programs localizes ambiguity is shared with ClarifyGPT; the difference is that the disagreement is established by *execution* on reconciled inputs rather than by inspection, and the input that most evenly splits the candidates is what the question is built from. Self-consistency sampling (Wang et al., ICLR 2023) motivates the majority-group selection.

## Algorithm parameters and defaults

| Parameter | Default | Description |
| --- | --- | --- |
| `num_candidates` | `4` | Candidate programs sampled per task. |
| `use_personas` | `True` | Vary the stated user persona per candidate; `False` sends the same prompt for all. |
| `num_inputs` | `10` | Generated inputs used to compare the candidates. |
| `search_rounds` | `2` | Rounds of looking for a distinguishing input before concluding the prompt is unambiguous. |
| `ask_when_agree` | `True` | Still ask one question when all candidates behave identically. |
| `max_questions` | `1` | Questions asked per task (also limited by the environment). |
| `generation_attempts` | `3` | Retries when a response contains no usable implementation. |
| `max_differences` | `3` | Distinguishing inputs turned into drafted questions, of which the best-scoring one is asked. |
| `partition_inputs` | `True` | Separate informative inputs from malformed ones that every candidate rejects. |
| `input_retries` | `1` | Re-ask for inputs when most do not fit any candidate signature. |
| `repair_attempts` | `1` | Repair rounds for the final program when it fails on a valid input. |
| `exec_timeout` | `2.0` | Seconds allowed per candidate call inside the sandbox. |
| `float_tol` | `1e-9` | Rounding applied to floats before comparing behaviour. |

- [x] The defaults in this table match `DEFAULT_CONFIG` in the code.
- [x] No parameter is read from environment variables, files, or hard-coded elsewhere.

## OPTIONAL - Evaluation settings used for the reported results

| Option | Value |
| --- | --- |
| `--language_model` | `openai/gpt-4.1-mini` |
| `--temperature` | `0.7` |
| `--clarification_model` | *(default)* |
| `--max_clarification_turns` | `1` |
| `--max_prompt_budget` | `1.0` |
| `--max_clarification_budget` | `1.0` |
| `--num_samples` | `1` |
| `--split` | `val` |
| Other options / algorithm overrides | *(none — `DEFAULT_CONFIG` as published above)* |

**Exact commands run:**

```bash
python generate_responses.py clarify/algorithms/curiosity_by_design.py \
    --split val \
    --output_path runs/curiosity_val.jsonl

python evaluate_responses.py \
    --split val \
    --generation_path runs/curiosity_val.jsonl \
    --output_path runs/curiosity_val_results.jsonl
```

Generation was sharded ten ways over the val split purely for wall-clock reasons and the shards were concatenated before evaluation; this is equivalent to the single command above, since the algorithm holds no state across tasks.

## OPTIONAL - Validation results

| TDS | nDCG | Pass@1 | Clarification rate | Over-asking rate | Avg. cost / task (USD) |
| --- | --- | --- | --- | --- | --- |
| 0.6161 | 0.8675 | 64.16% | 99.87% | 100.00% | 0.0069 |

770/770 tasks produced a row, with no exceptions and no task falling back to an empty program. High-quality clarification rate 86.87%. Breakdown, for whatever it is worth to a reviewer: HumanEval 72.86% (n=350) against MBPP 56.90% (n=420); prompts with no hidden ambiguity 73.63% (n=91) against ambiguous prompts 62.89% (n=679).

The over-asking rate is 100% by construction: `ask_when_agree=True` means a question is asked even when the candidates agree, and one question costs roughly 4% of the task's score under TDS. We measured the alternative and kept asking, because the pass-rate gain on prompts that *look* unambiguous but are not exceeded the discount. We would rather be told this is the wrong trade than hide it.

**Generation / result files:** available on request — happy to attach them to a release or a gist if that is useful for reproduction. Not committed, per CONTRIBUTING.md.

## Leaderboard

- [x] No leaderboard change in this pull request (organizers will add a confirmed row after reproduction), **or**
- [ ] `docs/data/leaderboard.csv` contains exactly one added/updated row for our algorithm, generated with `evaluate_responses.py ... --submit "<Team name>"`, with `confirmed=false`
- [x] No other rows (baselines, other teams) and no header were modified
- [x] The `model` column matches `--language_model` above

## Submission checklist

- [x] The pull request adds/changes only `clarify/algorithms/<name>.py` (and optionally our leaderboard row)
- [x] The file starts with the SPDX header and the docstring contains `Team`, `Team Members`, and `Main Contact`
- [x] Exactly one public class inherits from `ClarificationAlgorithmBase`; prototypes are prefixed with `_`
- [x] All LLM calls, clarifications, and code execution go through `env.llm`, `env.ask_human` / `env.can_ask`, and `env.exec_code`
- [x] Only the standard library and packages already in `pyproject.toml` are imported; `pyproject.toml` and `uv.lock` are unchanged (additional libraries were requested via a *Library request* issue: n/a)
- [x] No model name is hard-coded; the algorithm runs with the default environment settings
- [x] `python generate_responses.py clarify/algorithms/<name>.py --split val` runs without errors on a fresh `uv sync`
- [x] We developed on the released splits only and did not tune on validation instances
- [x] We have read [CONTRIBUTING.md](../CONTRIBUTING.md) and agree to the competition rules

## Notes for the organizers (optional)

**Docker is required.** `env.exec_code` is load-bearing: the behaviour table is how ambiguity is detected at all. Without a sandbox the algorithm degrades to a single direct question and scores far below the number above, so please run it with the `ganler/evalplus` image available. One `exec_code` round trip is about 0.9s and the algorithm makes one per round, so runtime is dominated by model latency rather than by the sandbox.

**Cost and call volume.** About 13.7 `env.llm` calls per task, $0.0069/task on `gpt-4.1-mini`. This is at the expensive end of the leaderboard and we are not claiming it is efficient.

**Nondeterminism.** Temperature is fixed at 0.7 by the harness and the algorithm deliberately relies on sampling diversity, so results vary run to run. We measure the spread at roughly ±1.7pp on Pass@1 at n=770, so please read the table above as 64% ± 2 rather than as 64.16%.

**Logging.** The algorithm emits one JSON record per task through `logging.getLogger("curiosity_by_design")` for our own offline analysis. It is silent unless a handler is attached, attaches no handler itself, and opens no files, so it is inert under your runner. Nothing in it is needed for the result.

**Two harness details we worked around**, in case they are useful to you independently:

- `clarify/runtime.py` stringifies ground truth during evaluation, and one task's expected answer exceeds Python 3.11's 4300-digit integer-to-string limit, raising `ValueError` and aborting the whole evaluation pass. `PYTHONINTMAXSTRDIGITS=0` works around it.
- `clarify/env.py` parses the simulated user's answer with a backtick-delimited pattern, so a backtick inside an answer truncates it. Our questions are stripped of backticks before being asked.
