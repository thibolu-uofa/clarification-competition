## Submission type

- [x] **New submission** — adds `clarify/algorithms/curiosity_by_design.py`
- [ ] **Update of an existing submission** — replaces our earlier file
- [ ] **Leaderboard update only** — adds/updates our row in `docs/data/leaderboard.csv` (`confirmed=false`)

## Team

| | |
| --- | --- |
| **Team name** | Curiosity by Design |
| **Team members** | Thibaud Lutellier (University of Alberta) |
| **Main contact** | Thibaud Lutellier — lutellie@ualberta.ca |
| **License** | MIT |

## Algorithm

**File:** `clarify/algorithms/curiosity_by_design.py`
**Class name:** `CuriosityByDesign`

Still a draft (idea could evolve a bit) the main idea is:

The algorithm finds what a task leaves open by differential testing, and asks about that. An underspecified requirement shows itself as a disagreement between independent readings of the same prompt. Several candidate implementations are sampled under different stated user personas, executed against generated input, and grouped by observed behaviour; the input that splits the candidates most evenly becomes the topic of the question. The answer is folded back into the specification, the candidates are regenerated from it, and the returned program is the largest group that fails no valid input.

## Algorithm parameters and defaults

These are the current defaults. The algorithm is still a draft, so they may change before the
submission deadline; the table will be updated with the final version of the pull request.

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

## OPTIONAL - Evaluation settings used

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

## Leaderboard

- [x] No leaderboard change in this pull request


## Submission checklist

- [x] The pull request adds/changes only `clarify/algorithms/curiosity_by_design.py` 
- [x] The file starts with the SPDX header and the docstring contains `Team`, `Team Members`, and `Main Contact`
- [x] Exactly one public class inherits from `ClarificationAlgorithmBase`; 
- [x] All LLM calls, clarifications, and code execution go through `env.llm`, `env.ask_human` / `env.can_ask`, and `env.exec_code`
- [x] Only the standard library and packages already in `pyproject.toml` are imported; `pyproject.toml` and `uv.lock` are unchanged (additional libraries were requested via a *Library request* issue: n/a)
- [x] No model name is hard-coded; the algorithm runs with the default environment settings
- [x] We developed on the released splits only and did not tune on validation instances
- [x] We have read [CONTRIBUTING.md](../CONTRIBUTING.md) and agree to the competition rules

## Notes for the organizers (optional)

**Docker is required.** `env.exec_code` is load-bearing: the behaviour table is how ambiguity is detected at all. Without a sandbox the algorithm degrades to asking a single direct question and scores far below its normal result, so please run it with the `ganler/evalplus` image available.

**Nondeterminism.** Temperature is fixed at 0.7 by the harness and the algorithm deliberately relies on sampling diversity, so results vary between runs. We measure the spread at roughly ±1.7pp on Pass@1 at n=770.

**Logging.** The algorithm emits one JSON record per task through `logging.getLogger("curiosity_by_design")` for our own offline analysis. It is silent unless a handler is attached, attaches no handler itself, and opens no files, so it is inert under your runner. Nothing in it is needed to produce a result.

**Use of AI coding assistance.** This submission was developed with substantial use of Claude Code (Anthropic) as a coding assistant: it wrote much of the implementation and our local measurement tooling, working from our direction. The design decisions, the experiments we chose to run, the interpretation of the results and the decision of what to submit are ours, and the branch's commit history carries `Co-Authored-By` trailers recording this. We state it here rather than leave it to be inferred. We take full responsibility for the submitted file and are happy to explain any part of it.
