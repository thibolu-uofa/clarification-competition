# SPDX-FileCopyrightText: 2026 Thibaud <lutellie@ualberta.ca>
#
# SPDX-License-Identifier: MIT

"""Curiosity by Design.

Finds what a task leaves open by differential testing. Several candidate
programs are sampled for the same task and executed on generated inputs. An
input on which the candidates disagree points at an underspecified requirement
and is turned into one clarifying question about the behaviour behind it. The
final implementation is generated from the problem and the user's answer.

Team: Curiosity by Design
Team Members: Thibaud
Main Contact: lutellie@ualberta.ca
"""

# STATUS: outline only. `run` currently returns a direct solution without asking, so the file
# loads and can serve as the registration stub. The steps below are not implemented yet.
#
# Plan
# ----
# 1. Sample `num_candidates` programs for the task. Each request states a different persona
#    for the USER who asks for the code (see USER_PERSONAS), so that the model makes
#    different assumptions per candidate; with `use_personas` off, only the model's
#    sampling randomness makes the candidates differ.
# 2. Generate `num_inputs` varied and edge-case inputs (inputs only, no expected outputs).
# 3. Run every candidate on every input in ONE sandbox script and collect the outputs.
# 4. Group the candidates by behaviour; drop candidates that crash.
# 5. Take the few best distinguishing inputs, have the model name the behavioural choice
#    behind each and draft a question for it, then rank the drafted questions against the
#    judging criteria and keep the best one.
# 6. If no input separates the candidates, widen the search once (more inputs for branches
#    not yet taken, or one candidate that deliberately reads the task differently) and go
#    back to step 3. If they still agree, ask the model directly for the most critical
#    question (or, with `ask_when_agree` off, return a candidate without asking).
# 7. Ask the user, then repeat steps 1-4 with the answer as part of the specification and
#    return a program from the largest behaviour group (majority vote).
#
# Step 7 revisited: spend the answer as an oracle, not just as prompt text
# ----------------------------------------------------------------------
# Measured on a 160-example train subsample (data/splits/train_sample.txt, seed 20261001):
# TDS 0.4441, Pass@1 46.25%, nDCG 0.95. Because a question is asked on 99.4% of tasks,
# TDS == Pass@1 x 0.9603 to four decimals, so the whole score is Pass@1 and question
# tactics are second-order. Step 7's vote predicts the outcome sharply:
#
#     unanimous vote          n=124   Pass@1 52.4%
#     split vote              n= 19   Pass@1 15.8%
#     every candidate failed  n= 17   Pass@1 41.2%
#
# Unanimous already sits near the 57.1% Pass@1 measured on prompts that were never
# ambiguous, so there is no headroom there. The 36 tasks (22.5%) where the vote splits or
# every candidate fails are the only place left to win, and majority voting is what fails
# on them: sampling at the fixed temperature 0.7 (the algorithm cannot change it; `env.llm`
# takes messages only) produces splits that are mostly noise rather than real readings -
# 62% of round-1 splits cut across persona boundaries.
#
# The answer is currently used only as text in CODE_WITH_SPEC_TEMPLATE, and
# `questions_from_differences` returns bare strings, so the input that motivated the
# question is discarded. That throws away the one oracle available: only 16% of prompts
# carry a doctest, but after a clarification the input, each group's observed behaviour on
# it, and the author's ruling are all in hand.
#
# Plan:
# - Keep (input_index, question) through `best_question` so the motivating input survives.
# - After `ask_human`, one model call turns the answer into assertions: ask for a handful of
#   (input, expected output) pairs that the answer determines, as Python literals, centred
#   on the behaviour the question was about. Deriving these is allowed; ASKING the user what
#   `f(x)` returns is not (the simulated user refuses it as a test-case request, and
#   DIFFERENCE_TEMPLATE already forbids it).
# - Append those inputs to the existing input list so step 7 still runs every candidate in
#   ONE `env.exec_code` call. The sandbox cost of this stage is zero.
# - Score each behaviour group by agreement with the derived expectations and select the
#   best-agreeing group instead of the largest.
# - Only if no group agrees, repair: send the spec, the answer, the selected program and the
#   concrete mismatch (expected X, got Y) and ask for a fix. A candidate that already agrees
#   needs no repair call.
# - Gate the whole stage on `final_vote_shape` in ("split", "all_failed"). Derived
#   expectations are model-generated and can be wrong; a unanimous vote that already passes
#   52.4% must not be overridden by them. Gated, this costs ~3 extra calls on 22.5% of tasks
#   (~+5%); ungated it is ~+23% for no expected gain.
# - Measure against runs/results_base.jsonl with tools/score.py, which breaks TDS down by
#   path and computes the real over-asking rate (the built-in one is always 0.00% on train,
#   because `need_clarification` defaults to True there).
#
# Optional extension: mutation testing (after steps 1-7 work)
# - Mutate the candidates with `ast.NodeTransformer` / `ast.unparse` (relational operators,
#   off-by-one constants, inclusive/exclusive bounds, sort order, and/or). No model call.
# - Use A, input quality: keep the inputs that kill mutants; a low mutation score means the
#   inputs are too weak to separate nearby behaviours.
# - Use B, extra interpretations: a mutant that still agrees with every example in the prompt
#   but differs from its original on a valid input marks a boundary the task does not pin
#   down. Treat it as one more candidate in step 4. Most mutants are plain bugs, so this
#   filter (or a model call asking whether the task text decides between the two) is needed.
#
# Logging (for analysis on the train split)
# - Emit one JSON record per task with `logging.getLogger("curiosity_by_design").info(...)`.
#   Standard library, silent unless a handler is attached, and it does not write files from
#   this module. Attach a file handler from a personal runner script that then calls
#   `generate_responses.main` (keep that script out of the PR).
# - `problem` has no task id: log a hash of `problem["prompt"]` and join it with the `prompt`
#   field of the generated .jsonl file.
# - Fields: persona per candidate, number of usable candidates and inputs, branch coverage,
#   behaviour groups (sizes and personas), path taken (difference / widened / fallback / no
#   question), drafted and chosen questions, the answer, vote sizes in step 7, number of
#   model calls and `env.prompt_cost`.
#
# What is scored (see README, "Evaluation Criteria")
# --------------------------------------------------
# - Rank = TDS: 1 if the final code passes the hidden tests, times 0.96 after one question
#   (0.93 after two). Question quality (nDCG) only breaks ties.
# - The simulated user answers precisely only if the question is critical, not guessable,
#   about exactly one fact, objective, and not about the implementation or test cases.
# - Default budget: one question per task (`env.can_ask()`), 1 USD of model calls per task.
#
# Constraints on this file (see CONTRIBUTING.md)
# ----------------------------------------------
# - Only `env.llm`, `env.ask_human` / `env.can_ask` and `env.exec_code`; standard library and
#   the packages in pyproject.toml; no model name, environment variable or file access.
# - The PR check rejects every attribute access that starts with an underscore, including
#   `self._helper()` and `super().__init__()`. Name helpers without a leading underscore; the
#   base class already merges `DEFAULT_CONFIG` with the command-line overrides.
# - Exactly one public subclass of `ClarificationAlgorithmBase`; prefix experiments with `_`.

from __future__ import annotations

from typing import Any

from clarify.baselines import ClarificationAlgorithmBase
from clarify.env import ClarificationEnvironment
from clarify.runtime import _validate_and_parse_evalplus_result

CODE_TEMPLATE = """
Write a self-contained Python script implementing `{entry_point}` that solves the following problem.

{prompt}

Enclose your complete solution in a single block starting with ```python and ending with ```.
""".strip()


# User personas for sampling candidates (step 1). The persona describes the user who asks for
# the code, not a role the model should play, and is placed at the start of the user message.
# Starting points to experiment with, not a tested set; add further user descriptions here.
USER_PERSONAS = [
    "I'm a beginner who is still learning Python.",
    "I'm a senior software developer.",
]


class CuriosityByDesign(ClarificationAlgorithmBase):
    DEFAULT_CONFIG = {
        "num_candidates": 4,  # candidate programs sampled per task
        "use_personas": True,  # vary the persona per candidate; False = same prompt for all
        "num_inputs": 10,  # generated inputs used to compare the candidates
        "search_rounds": 2,  # rounds of looking for a distinguishing input before giving up
        "ask_when_agree": True,  # still ask one question when all candidates behave the same
        "max_questions": 1,  # questions asked per task (also limited by the environment)
        "generation_attempts": 3,  # retries when a response contains no usable implementation
    }

    # Step 1 -------------------------------------------------------------------------------

    def sample_candidates(self, env: ClarificationEnvironment, problem: dict[str, Any]) -> list:
        """Returns `num_candidates` implementations of `problem["entry_point"]`.

        TODO: call `env.llm` once per candidate and keep the responses that parse, compile
        (`ast.parse`) and define the entry point. Some benchmark prompts name the function
        `candidate`; the solution must use `problem["entry_point"]`.

        With `use_personas`, the user message of candidate `i` starts with
        `USER_PERSONAS[i % len(USER_PERSONAS)]`, followed by the request for the code. The
        response may then contain more explanation, but the code block is still required.
        Remember which persona each candidate was written for so the groups in step 4 can
        be analysed per persona. To measure the effect, compare on the train split how often
        the candidates split into more than one behaviour group with `--use_personas True`
        and `False`.
        """
        raise NotImplementedError

    # Step 2 -------------------------------------------------------------------------------

    def generate_inputs(self, env: ClarificationEnvironment, problem: dict[str, Any]) -> list:
        """Returns `num_inputs` argument tuples to call the candidates with.

        Option A (model): one `env.llm` call asking for varied and edge-case inputs as Python
        literals, one call per line, parsed with `ast.literal_eval`. Optionally add a
        targeted variant: show two candidates and ask for an input on which they would differ.

        Option B (input space partitioning from the candidates, no model call for sampling):
        - Input specification: one `env.llm` call that returns, for the task, the type of
          each argument, a few seed calls, and the input constraints as code, e.g. a
          function `is_valid(*args) -> bool`. Run `is_valid` in the sandbox to filter the
          sampled inputs. The specification is the model's reading of an unclear task, so
          treat it as an assumption: if the candidates disagree with it or with each other
          on the number or types of the arguments (visible with `ast`, without running
          anything), that disagreement is itself a candidate for the question.
        - Walk every candidate with `ast` and collect the conditions (`if`, `while`,
          comparisons) and the constants they compare against; the boundaries of the
          partitions are these constants and their neighbours (c - 1, c, c + 1, empty and
          one-element containers, the strings and characters that are tested for).
        - Mutate the seeds with those boundary values and sample randomly around them.
        - Most conditions are on internal variables, not on the arguments, and there is no
          constraint solver among the allowed packages, so partitions cannot be solved for
          directly. Approximate them in the sandbox instead: record which decisions each
          input takes in each candidate and keep one input per distinct signature.
        - Coverage criterion. The reference solutions are small (HumanEval+: median 6 code
          lines and 2 decisions, 96% have at most 6; MBPP+: median 2 lines and 1 decision,
          93% have at most 3), so path coverage is affordable when loops are bounded to
          zero, one and several iterations (about half the solutions have a loop or a
          comprehension). Record at the level of conditions, not lines: instrument each
          condition with `ast.NodeTransformer` so that ternaries, comprehension filters and
          the operands of and/or are seen (a line trace misses them in 33% / 16% of the
          solutions). Requiring every condition to be seen both true and false is close to
          MC/DC under short-circuit evaluation; full MC/DC only adds something for
          compound conditions, which are rare (18% / 7%).
        - Structural coverage is not enough on its own: 44% of the MBPP+ solutions (20% of
          HumanEval+) have no decision at all, so one input covers them fully although
          candidates can still differ (sort order, ties, return type). Always include
          boundary values derived from the argument types as well.
          Full symbolic execution is out of scope for now; revisit only if the branch
          coverage reached this way turns out to be poor on the train split.
        - Random inputs can violate what the task takes for granted (negative sizes, empty
          lists). A difference on such an input leads to a question that is not critical;
          keep only inputs that pass `is_valid` and prefer those close to a seed.
        """
        raise NotImplementedError

    # Step 3 -------------------------------------------------------------------------------

    def run_candidates(self, env: ClarificationEnvironment, candidates: list, inputs: list) -> list:
        """Returns `outputs[c][i]`: what candidate `c` produced on input `i`.

        TODO: build ONE self-contained script (standard library only) that `exec`s each
        candidate in its own namespace, calls it on each input inside try/except, and prints
        a JSON table of `repr(result)` or the exception type. Pass it to `env.exec_code`,
        which returns the script's stdout. Guard against candidates that never terminate.
        Needs Docker on the machine that runs `generate_responses.py`.

        Record everything a caller can observe, not only the return value: its type
        (`1.0`, `'1.0'` and `1` differ, so do a list and a tuple), the exception type if it
        raises, whether the arguments were modified in place, and anything printed. Compare
        floats with a tolerance so rounding does not split groups. Do not compare internal
        states across candidates: they differ for programs that behave identically, and a
        question about them would be about the implementation.
        """
        raise NotImplementedError

    # Step 4 -------------------------------------------------------------------------------

    def group_by_behaviour(self, outputs: list) -> list:
        """Returns groups of candidate indices that produced identical outputs on all inputs.

        TODO: plain Python, no model call. Drop candidates that crash on inputs the others
        handle: a lone failing candidate is a bug, not an open requirement.
        """
        raise NotImplementedError

    # Step 5 -------------------------------------------------------------------------------

    def pick_distinguishing_inputs(self, outputs: list, groups: list) -> list:
        """Returns the indices of the best few distinguishing inputs, best first (may be empty).

        TODO: plain Python, no model call. Rank the inputs on which the groups differ by:
        how evenly they split the candidates (2-versus-2 before 3-versus-1), whether every
        group returns a value instead of raising, and how close the input is to a seed.
        Keep two or three: different inputs can expose different open requirements.
        """
        raise NotImplementedError

    def questions_from_differences(
        self,
        env: ClarificationEnvironment,
        problem: dict[str, Any],
        differences: list,
    ) -> list:
        """Returns one drafted question per difference (input plus the outputs per group).

        TODO: one `env.llm` call per difference (or one call for all) that receives the task,
        the input, the differing outputs and one representative program per group, and
        (a) names the behavioural choice that separates the groups,
        (b) says whether the task text already decides it; if it does, one group is simply
            wrong: drop the difference and that group instead of asking,
        (c) drafts a question about that choice, offering the concrete alternatives.
        Never ask what the function should return for the input itself: that counts as
        asking for a test case and gets a vague answer.

        Making the difference easier to explain, in order of expected value:
        - Use the simplest input that still separates the groups (shrink lists, numbers and
          strings while the split stays the same), and give two or three inputs that show
          the same split so the model can see the rule behind it.
        - Traces: do not align traces across programs (different variable names and
          structure make them incomparable). Give each representative program together with
          its OWN branch decisions on the input, e.g. "line 4: `if n <= 0` -> True", so the
          model sees which condition decided the output. The trace comes for free if step 3
          already records branches. The programs are short, so try without it first.
        """
        raise NotImplementedError

    def best_question(
        self, env: ClarificationEnvironment, problem: dict[str, Any], questions: list
    ) -> str:
        """Returns the drafted question that best fits the judging criteria.

        TODO: one `env.llm` call that scores each question on the five criteria (critical,
        not guessable, exactly one fact, objective, not about implementation or tests) and
        returns the index of the best one. Skip the call when there is only one question.
        """
        raise NotImplementedError

    # Step 6 -------------------------------------------------------------------------------

    def widen_search(
        self,
        env: ClarificationEnvironment,
        problem: dict[str, Any],
        candidates: list,
        inputs: list,
        coverage: Any,
    ) -> tuple[list, list]:
        """Returns extended (candidates, inputs) when all candidates agreed in the first round.

        TODO: at most `search_rounds - 1` extra rounds. The branch coverage of the first
        round tells which of the two causes of agreement applies:
        - Branches not yet taken: the inputs were too weak. Add inputs aimed at those
          branches (boundary values from their conditions) and run again.
        - All branches taken and still no difference: more inputs will not help, the
          candidates share one reading of the task. Ask the model for one more candidate
          that reads the task differently but defensibly, and run it on the inputs. If it
          behaves differently, that difference goes to step 5.
        """
        raise NotImplementedError

    def fallback_question(self, env: ClarificationEnvironment, problem: dict[str, Any]) -> str:
        """Returns the most critical question when no input separates the candidates.

        TODO: one `env.llm` call listing the blockers (missing information, vague wording,
        contradictions, suspicious requirements) and asking about the most severe one. All
        candidates agreeing does not mean the task is clear: they can share a wrong assumption.

        A question is not free: a passing task scores 0.96 instead of 1. Asking pays off when
        pass rate with the question x 0.96 > pass rate without it. Measure both on the train
        split for the tasks where all candidates agree and set `ask_when_agree` accordingly.
        """
        raise NotImplementedError

    # Step 7 -------------------------------------------------------------------------------

    def final_program(
        self,
        env: ClarificationEnvironment,
        problem: dict[str, Any],
        clarifications: list[tuple[str, str]],
    ) -> str:
        """Returns the implementation given the problem and the (question, answer) pairs.

        TODO: repeat steps 1-4 with the answers stated as part of the specification (they
        take precedence over the problem text, whose examples can be wrong in the
        contradictory variants). Sample without personas here, reuse the inputs of step 2,
        and return a program from the largest behaviour group (majority vote). No second
        question: the budget is spent, so remaining disagreement is settled by the vote.
        Break ties with one `env.llm` call asking which group matches the answer. Retry a
        candidate up to `generation_attempts` times when its response is unusable.
        """
        raise NotImplementedError

    # ---------------------------------------------------------------------------------------

    def run(self, env: ClarificationEnvironment, problem: dict[str, Any]) -> str:
        # TODO: replace this direct solution with steps 1-7. Intended flow:
        #
        #   candidates = self.sample_candidates(env, problem)
        #   inputs = self.generate_inputs(env, problem)
        #   outputs = self.run_candidates(env, candidates, inputs)
        #   groups = self.group_by_behaviour(outputs)
        #   indices = self.pick_distinguishing_inputs(outputs, groups)
        #   if not indices: widen_search(...) once, then repeat the three lines above
        #   if indices: question = best_question(questions_from_differences(...))
        #   elif ask_when_agree: question = fallback_question(...)
        #   else: return a candidate
        #   if env.can_ask(): answer = env.ask_human(question)
        #   return self.final_program(env, problem, [(question, answer)])
        #
        # `env.llm` raises LimitsExceededException when the per-task budget is spent and
        # `env.ask_human` raises TooManyQuestionException when no question is left.
        prompt = CODE_TEMPLATE.replace("{entry_point}", problem["entry_point"]).replace(
            "{prompt}", problem["prompt"].strip()
        )
        response = env.llm(prompt)

        try:
            return _validate_and_parse_evalplus_result(response)
        except ValueError:
            return response
