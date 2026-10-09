"""Regression tests for the pure helpers of CuriosityByDesign.

Every assertion here corresponds to a named entry under "Traps in our own code" in
CLAUDE.md. Those are deterministic-logic bugs with no config flag, so an end-to-end arm
cannot isolate them — and at ~$1 and +-5pp per arm it could not resolve them anyway. They
are cheap to pin down here instead, and a reintroduced bug then costs a second rather than
a run.

No `env`, no Docker, no API calls. `pytest` is not a dependency of the project, so these
are plain asserts, run with:

    .venv/bin/python tests/test_helpers.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_responses import _load_clarification_algorithm

ALGORITHM_PATH = "clarify/algorithms/curiosity_by_design.py"


def fresh(**overrides):
    """A configured instance. The base class merges DEFAULT_CONFIG and rejects unknown keys."""
    algorithm = _load_clarification_algorithm(ALGORITHM_PATH)(overrides)
    # `group_by_behaviour` records counters through `trace_note`, which tolerates a missing
    # trace, but a test that asserts on counters needs one.
    algorithm.start_trace({"prompt": "test prompt", "entry_point": "f"})
    return algorithm


def value(form, **extra):
    return {"kind": "value", "value": form, **extra}


def error(name="ValueError"):
    return {"kind": "error", "error": name}


SKIPPED = {"kind": "skipped"}

CHECKS = []


def check(function):
    CHECKS.append(function)
    return function


# --- the sandbox deadline: a `skipped` cell is not a behaviour --------------------------


@check
def test_skipped_column_is_not_evidence():
    """The 20s deadline fills the rest of a row with `skipped` to keep its width.

    Comparing those split two identical programs into two groups and drafted the single
    question from where the clock stopped.
    """
    algorithm = fresh()
    outputs = [
        [value(["int", 1]), value(["int", 2])],
        [value(["int", 1]), SKIPPED],
    ]
    assert algorithm.valid_indices(outputs) == [0], algorithm.valid_indices(outputs)
    # ... and therefore the two programs are one group, not two.
    assert algorithm.group_by_behaviour(outputs) == [[0, 1]]


@check
def test_input_every_voter_rejects_is_suspect():
    algorithm = fresh()
    outputs = [
        [error(), value(["int", 2])],
        [error(), value(["int", 2])],
    ]
    assert algorithm.suspect_inputs(outputs) == {0}
    assert algorithm.valid_indices(outputs) == [1]


@check
def test_candidate_that_failed_everywhere_gets_no_vote():
    """Without that rule every input looks suspect exactly when all candidates are broken."""
    algorithm = fresh()
    outputs = [
        [error(), error()],          # no value anywhere: not a voter
        [error(), value(["int", 2])],
    ]
    assert algorithm.suspect_inputs(outputs) == {0}


@check
def test_partitioning_off_means_no_suspect_filtering():
    algorithm = fresh(partition_inputs=False)
    outputs = [[error(), value(["int", 2])], [error(), value(["int", 2])]]
    assert algorithm.suspect_inputs(outputs) == set()
    assert algorithm.valid_indices(outputs) == [0, 1]


# --- only module-level definitions count ------------------------------------------------


@check
def test_method_is_not_the_entry_point():
    """`ast.walk` found `class S: def f(self, a)` and reported arity (2, 2) including `self`,

    which rejected every correct input and emitted a hint naming `self` as a parameter.
    """
    algorithm = fresh()
    code = "class S:\n    def f(self, a):\n        return a\n"
    assert algorithm.entry_point_arity(code, "f") is None
    assert algorithm.entry_point_params(code, "f") is None


@check
def test_nested_function_is_not_the_entry_point():
    algorithm = fresh()
    code = "def outer():\n    def f(a, b):\n        return a\n    return f\n"
    assert algorithm.entry_point_arity(code, "f") is None


@check
def test_later_definition_wins():
    algorithm = fresh()
    code = "def f(a):\n    return a\n\ndef f(a, b):\n    return a + b\n"
    assert algorithm.entry_point_arity(code, "f") == (2, 2)
    assert algorithm.entry_point_params(code, "f") == ["a", "b"]


@check
def test_definition_under_if_or_try_is_module_level():
    """An `if`/`try` body does execute on import, so a definition there is reachable."""
    algorithm = fresh()
    guarded = "import sys\nif sys.version_info:\n    def f(a, b):\n        return a\n"
    assert algorithm.entry_point_arity(guarded, "f") == (2, 2)
    tried = "try:\n    def f(a):\n        return a\nexcept Exception:\n    pass\n"
    assert algorithm.entry_point_arity(tried, "f") == (1, 1)


@check
def test_arity_edges():
    algorithm = fresh()
    assert algorithm.entry_point_arity("def f(a, *rest):\n    return a\n", "f") == (1, None)
    assert algorithm.entry_point_arity("def f(a, b=1):\n    return a\n", "f") == (1, 2)
    # Keyword-only without a default can never be supplied the way the sandbox calls it,
    # so the arity is unknown rather than a count that would license rewrapping.
    assert algorithm.entry_point_arity("def f(a, *, k):\n    return a\n", "f") is None
    assert algorithm.entry_point_arity("def f(:\n", "f") is None
    # Unknown arity must never be used to judge an input.
    assert algorithm.arity_accepts(None, 7) is True


# --- inputs reconciled against the signature, not discarded -----------------------------


@check
def test_single_tuple_argument_is_rewrapped_not_dropped():
    """`parse_input_lines` reads every line as a tuple of positional arguments, so a

    function taking ONE tuple gets its input read as N arguments and every candidate
    raises TypeError.
    """
    algorithm = fresh()
    assert algorithm.resolve_input_arity("(1, 2)", [(1, 1)]) == "((1, 2),)"
    # It fits as-is for a two-parameter function, so it is left alone.
    assert algorithm.resolve_input_arity("(1, 2)", [(2, 2)]) == "(1, 2)"
    # Nothing accepts it: too FEW arguments is the common direction and is unfixable.
    assert algorithm.resolve_input_arity("(1, 2)", [(3, 3)]) is None
    # No signature could be read: never judge the input by it.
    assert algorithm.resolve_input_arity("(1, 2)", [None]) == "(1, 2)"


@check
def test_rewrap_that_would_not_parse_is_dropped():
    """`repr` does not round-trip non-finite floats, and the sandbox parses with literal_eval."""
    algorithm = fresh()
    assert algorithm.resolve_input_arity("(1e400, 2)", [(1, 1)]) is None


@check
def test_arity_fit_reports_its_counts():
    algorithm = fresh()
    candidates = [{"code": "def f(pair):\n    return pair\n"}]
    resolved, dropped, rewrapped = algorithm.arity_fit(["(1, 2)", "[3]", "("], candidates, "f")
    assert resolved == ["((1, 2),)", "[3]"], resolved
    assert (dropped, rewrapped) == (1, 1)


# --- prompts must use Python syntax ------------------------------------------------------


@check
def test_readable_emits_python_not_json():
    """`json.dumps` produced `returns true` and `returns null`, and canon's own encoding

    leaked as `[["int", 1]]`. Both reached DIFFERENCE_TEMPLATE, the one prompt that has to
    make a disagreement legible.
    """
    algorithm = fresh()
    assert algorithm.readable(["bool", True]) == "True"
    assert algorithm.readable(["none", None]) == "None"
    assert algorithm.readable(["str", "ab"]) == "'ab'"
    assert algorithm.readable(["int", 1]) == "1"
    assert algorithm.readable(["list", [["int", 1], ["int", 2]]]) == "[1, 2]"
    assert algorithm.readable(["tuple", [["int", 1]]]) == "(1,)"
    assert algorithm.readable(["float", "nan"]) == "nan"
    assert algorithm.readable(["set", [json.dumps(["int", 1])]]) == "{1}"
    assert algorithm.readable(["dict", [[json.dumps(["str", "k"]), json.dumps(["int", 1])]]]) == "{'k': 1}"
    rendered = algorithm.readable(["list", [["int", 1]]])
    assert "true" not in rendered and "null" not in rendered and '"int"' not in rendered


@check
def test_describe_reads_as_a_sentence():
    algorithm = fresh()
    assert algorithm.describe(value(["list", [["int", 1]]])) == "returns [1] of type list"
    assert algorithm.describe(error("ValueError: empty")) == "raises ValueError: empty"
    assert algorithm.describe({"kind": "timeout"}) == "does not terminate"
    assert "modifies its arguments in place" in algorithm.describe(
        value(["int", 1], mutated=True)
    )
    assert "prints 'hi'" in algorithm.describe(value(["int", 1], printed="hi\n"))


@check
def test_call_repr_renders_a_call():
    """A bare literal such as `[1, 2, 3]` rendered as `f[1, 2, 3]` rather than a call."""
    algorithm = fresh()
    algorithm.current_inputs = ["[1, 2, 3]", "(1, 2)", "not a literal"]
    assert algorithm.call_repr([], 0) == "([1, 2, 3],)"
    assert algorithm.call_repr([], 1) == "(1, 2)"
    assert algorithm.call_repr([], 2) == "not a literal"
    assert algorithm.call_repr([], 9) == "(...)"


# --- list distinct behaviours, not groups ------------------------------------------------


@check
def test_groups_that_agree_here_are_not_rival_behaviours():
    """Two groups can agree at the chosen input and differ elsewhere, which rendered

    "Behaviour 1: returns 5 / Behaviour 2: returns 5" under a template that says two
    implementations disagree. With fewer than two distinct behaviours there is nothing to
    ask, so no model call is made - which is why `env` can be None here.
    """
    algorithm = fresh()
    outputs = [
        [value(["int", 5]), value(["int", 1])],
        [value(["int", 5]), value(["int", 2])],
    ]
    groups = [[0], [1]]
    assert algorithm.questions_from_differences(None, {}, [], outputs, groups, [0]) == []


@check
def test_unclean_candidate_is_discarded_when_a_clean_one_exists():
    algorithm = fresh()
    outputs = [
        [value(["int", 1]), value(["int", 2])],
        [value(["int", 1]), error()],
    ]
    assert algorithm.group_by_behaviour(outputs) == [[0]]
    assert algorithm.trace["discarded_unclean_search"] == 1
    assert algorithm.trace["grouping_fallback_search"] is False


@check
def test_grouping_falls_back_when_nothing_is_clean():
    """`run` must always return something, so the strict rule cannot empty the pool."""
    algorithm = fresh()
    # Each candidate fails one input that the other answers, so neither column is suspect
    # (a suspect column would be filtered out and both candidates would come back clean)
    # and no candidate is clean on every valid input.
    outputs = [
        [value(["int", 1]), error()],
        [error(), value(["int", 9])],
    ]
    groups = algorithm.group_by_behaviour(outputs)
    assert sorted(index for group in groups for index in group) == [0, 1]
    assert algorithm.trace["grouping_fallback_search"] is True


@check
def test_counters_use_per_stage_keys():
    """Counters that run twice per task must not overwrite the field being measured."""
    algorithm = fresh()
    outputs = [[value(["int", 1])], [error()]]
    algorithm.group_by_behaviour(outputs, stage="search")
    algorithm.group_by_behaviour(outputs, stage="vote")
    assert "discarded_unclean_search" in algorithm.trace
    assert "discarded_unclean_vote" in algorithm.trace


# --- the clarification turn is spent before the answer is read ---------------------------


@check
def test_terse_but_complete_answer_is_kept():
    """Discarding "Descending order." pays the score penalty for nothing."""
    algorithm = fresh()
    assert algorithm.usable_answer("Descending order.") is True
    assert algorithm.usable_answer("Yes.") is True
    assert algorithm.usable_answer("Return an empty list instead") is True


@check
def test_refusals_and_fragments_are_rejected():
    algorithm = fresh()
    assert algorithm.usable_answer("Cannot answer the given question.") is False
    assert algorithm.usable_answer("Irrelevant question.") is False
    assert algorithm.usable_answer("") is False
    assert algorithm.usable_answer("Should the") is False  # truncated mid-sentence


@check
def test_question_carries_no_backticks():
    """`env.py` reads the reply with ANSWERS=`(.+?)`, so one backtick truncates the answer."""
    algorithm = fresh()
    plain = algorithm.plain_question("Should `f`  return\na list?")
    assert "`" not in plain
    assert plain == "Should f return a list?"


@check
def test_field_reads_to_the_last_backtick_on_the_line():
    """A question quoting an identifier was otherwise cut off at the inner backtick."""
    algorithm = fresh()
    reply = "DECIDED=no\nQUESTION=`Should `f` return a list?`"
    assert algorithm.field(reply, "QUESTION") == "Should `f` return a list?".strip("`")
    assert algorithm.field(reply, "DECIDED") == "no"


# --- config plumbing ---------------------------------------------------------------------


@check
def test_unknown_override_fails_fast():
    """An A/B arm must not run 160 tasks with a silently ignored flag."""
    try:
        _load_clarification_algorithm(ALGORITHM_PATH)({"partition_input": False})
    except ValueError:
        return
    raise AssertionError("an unknown config key was accepted")


@check
def test_overrides_reach_the_config():
    algorithm = fresh(partition_inputs=False, repair_attempts=0)
    assert algorithm.config["partition_inputs"] is False
    assert algorithm.config["repair_attempts"] == 0
    assert algorithm.config["num_candidates"] == 4  # untouched default


# --- the inlined fenced-code parser ------------------------------------------------------


@check
def test_fenced_code_parser_matches_the_harness():
    """The submission inlines `clarify.runtime`'s private parser; it must not drift from it.

    Importing a `_`-prefixed harness name would break the submission outright if the harness
    were refactored, so the parser is duplicated. That is only safe while the copy behaves
    identically, including the exception message - `ask_for_code` feeds it back to the model
    as a correction prompt, so the text is behaviour, not decoration.
    """
    import random

    from clarify.runtime import _validate_and_parse_evalplus_result as harness

    from clarify.algorithms.curiosity_by_design import parse_fenced_code as ours

    def outcome(parser, text):
        try:
            return ("ok", parser(text))
        except ValueError as error:
            return ("error", str(error))

    cases = [
        "", "no fence at all", "```python", "```python\nx=1\n```", "```\nx=1\n```",
        "```python```", "```python\n```", "prefix ```python\ndef f():\n    pass\n```",
        "```python\na\n```\n```python\nb\n```", "```PYTHON\nx\n```",
    ]
    alphabet = ["```python", "```", "\n", "x=1", "a", " "]
    random.seed(0)
    cases += ["".join(random.choice(alphabet) for _ in range(random.randint(0, 8)))
              for _ in range(2000)]

    for text in cases:
        assert outcome(ours, text) == outcome(harness, text), repr(text)


if __name__ == "__main__":
    failures = []
    for test in CHECKS:
        try:
            test()
            print(f"  ok   {test.__name__}")
        except Exception as exception:  # noqa: BLE001 - a test runner reports, it does not raise
            failures.append((test.__name__, exception))
            print(f"  FAIL {test.__name__}: {type(exception).__name__}: {exception}")

    print(f"\n{len(CHECKS) - len(failures)}/{len(CHECKS)} passed")
    if failures:
        sys.exit(1)
