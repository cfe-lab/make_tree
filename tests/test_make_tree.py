import os
from pathlib import Path
from typing import Any, Tuple

import ete3
import pytest

from make_tree.make_tree import (
    export_tree,
    get_optimal_font_size,
    interpolate,
    load_tree,
    parse_label,
    process_tree_labels,
    reverse_tree,
)


@pytest.mark.parametrize(
    "input, exp_output",
    [
        ("test", (None, None, "test")),
        ("i!!test", ("i", None, "test")),
        ("b2!!test", ("b", 2, "test")),
    ],
)
def test_parse_label_basic(input: str, exp_output: Tuple[str | None, int | None, str]):
    assert parse_label(input) == exp_output


@pytest.mark.parametrize("input", ["!!test", "b0!!test", "z2!!test", "b100!!test"])
def test_parse_label_errors(input: str):
    with pytest.raises(ValueError):
        parse_label(input)


@pytest.mark.parametrize(
    "tree_input, expected_output",
    [
        (None, None),
        ("(A);", "(A);"),
        ("(A,B,C);", "(C,B,A);"),
        ("(A,B,(C,D,(E,F)));", "(((F,E),D,C),B,A);"),
    ],
    ids=["Empty Tree", "One Node", "Three Node", "Six Node"],
)
def test_reverse_tree(tree_input, expected_output):
    t = ete3.Tree(tree_input)
    reverse_tree(t)
    expected = ete3.Tree(expected_output)
    assert str(t) == str(expected)


@pytest.mark.parametrize(
    "a, b, c, exp_output",
    [(0, 10, 0.5, 5.0), (-10, 10, 0.5, 0.0), (0, 100, 0.75, 75.0)],
)
def test_interpolate(a: float, b: float, c: float, exp_output: float):
    assert interpolate(a, b, c) == exp_output


def test_get_optimal_font_size_small_tree():
    t = ete3.Tree("(A,B,C);")
    assert get_optimal_font_size(t) > 8


def test_get_optimal_font_size_big_tree():
    t = ete3.Tree("(" + "A,B,C" * 100 + ");")
    assert get_optimal_font_size(t) < 8


def test_process_tree_labels_idempotent():
    t = ete3.Tree("(A,B,(C,D),E);")
    process_tree_labels(t)
    s1 = str(t)
    process_tree_labels(t)
    s2 = str(t)
    assert s1 == s2


@pytest.mark.parametrize(
    "tree_str", ["(A,B,(C,REF_ROOT),E);", "(A,B,(C,REF_ROOT_HIDE),E);"]
)
def test_process_tree_labels_reroots(tree_str: str):
    t = ete3.Tree(tree_str)
    s1 = str(t)
    process_tree_labels(t)
    s2 = str(t)
    assert not s1 == s2


def test_export(tmp_path: Path):
    t = ete3.Tree("(A,B,(C,D),E);")
    output_path = os.path.join(tmp_path, "output.pdf")
    result = export_tree(t, output_path, "my title")
    assert isinstance(result, dict)
    assert os.path.exists(output_path)


@pytest.mark.parametrize(
    "input",
    [
        "(A,B,(C,D),E);",
        "(A);",
        "(A,B,C);",
        "(A,B,(C,D,(E,F)));",
    ],
)
def test_load_tree(input: str):
    t1 = ete3.Tree(input)

    t2 = load_tree(input)

    assert [str(line) for line in t1][::-1] == [str(line) for line in t2]
