import os
from pathlib import Path
from typing import Optional, Tuple

import pytest
import toytree

from make_tree.make_tree import (
    TreeParseError,
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
def test_parse_label_basic(
    input: str, exp_output: Tuple[Optional[str], Optional[int], str]
) -> None:
    assert parse_label(input) == exp_output


@pytest.mark.parametrize("input", ["!!test", "b0!!test", "z2!!test", "b100!!test"])
def test_parse_label_errors(input: str) -> None:
    with pytest.raises(ValueError):
        parse_label(input)


@pytest.mark.parametrize(
    "tree_input, original_tips, expected_reversed",
    [
        ("(A,B,C);", ["A", "B", "C"], ["C", "B", "A"]),
        ("(A,B,(C,D,(E,F)));", ["A", "B", "C", "D", "E", "F"], ["F", "E", "D", "C", "B", "A"]),
    ],
    ids=["Three Node", "Six Node"],
)
def test_reverse_tree(
    tree_input: str, original_tips: list, expected_reversed: list
) -> None:
    t = toytree.tree(tree_input)
    assert list(t.get_tip_labels()) == original_tips
    reverse_tree(t)
    assert list(t.get_tip_labels()) == expected_reversed


@pytest.mark.parametrize(
    "a, b, c, exp_output",
    [(0, 10, 0.5, 5.0), (-10, 10, 0.5, 0.0), (0, 100, 0.75, 75.0)],
)
def test_interpolate(a: float, b: float, c: float, exp_output: float) -> None:
    assert interpolate(a, b, c) == exp_output


def test_get_optimal_font_size_small_tree() -> None:
    t = toytree.tree("(A,B,C);")
    assert get_optimal_font_size(t) > 8


def test_get_optimal_font_size_big_tree() -> None:
    tips = ",".join(f"T{i}" for i in range(200))
    t = toytree.tree(f"({tips});")
    assert get_optimal_font_size(t) < 8


def test_process_tree_labels_idempotent() -> None:
    t = toytree.tree("(A,B,(C,D),E);")
    tips_before = list(t.get_tip_labels())
    t = process_tree_labels(t)
    tips_after = list(t.get_tip_labels())
    # A tree without REF_ROOT should have the same tip set
    assert set(tips_before) == set(tips_after)


@pytest.mark.parametrize(
    "tree_str, ref_root_name",
    [
        ("(A,B,(C,REF_ROOT),E);", "REF_ROOT"),
        ("(A,B,(C,REF_ROOT_HIDE),E);", "REF_ROOT_HIDE"),
    ],
)
def test_process_tree_labels_reroots(tree_str: str, ref_root_name: str) -> None:
    t = toytree.tree(tree_str)
    original_tips = set(t.get_tip_labels())
    t2 = process_tree_labels(t)
    # Tree should now be rooted differently
    root_children_names = {n.name for n in t2.treenode.children}
    assert ref_root_name in root_children_names or ref_root_name not in t2.get_tip_labels(), (
        f"{ref_root_name} should be near the root or already removed"
    )


def test_process_tree_labels_hides_ref_root_hide() -> None:
    t = toytree.tree("(A,B,(C,REF_ROOT_HIDE),E);")
    t2 = process_tree_labels(t)
    assert "REF_ROOT_HIDE" not in t2.get_tip_labels()


def test_export_pdf(tmp_path: Path) -> None:
    t = toytree.tree("(A,B,(C,D),E);")
    output_path = str(tmp_path / "output.pdf")
    result = export_tree(t, output_path, "my title")
    assert result is None
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0


def test_export_svg(tmp_path: Path) -> None:
    t = toytree.tree("(A,B,C);")
    output_path = str(tmp_path / "output.svg")
    result = export_tree(t, output_path)
    assert result is None
    assert os.path.exists(output_path)
    content = open(output_path).read()
    assert "<svg" in content


def test_export_with_styled_labels(tmp_path: Path) -> None:
    t = toytree.tree("(b2!!BoldRed,i!!ItalicBlack,plain);")
    output_path = str(tmp_path / "styled.pdf")
    export_tree(t, output_path, "Styled Tree")
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0


@pytest.mark.parametrize(
    "newick",
    [
        "(A,B,(C,D),E);",
        "(A);",
        "(A,B,C);",
        "(A,B,(C,D,(E,F)));",
    ],
)
def test_load_tree_reverses_tips(newick: str) -> None:
    original = toytree.tree(newick)
    original_tips = list(original.get_tip_labels())

    loaded = load_tree(newick)
    loaded_tips = list(loaded.get_tip_labels())

    # load_tree reverses the tree, so tip order should be reversed
    assert loaded_tips == original_tips[::-1]


def test_load_tree_bad_newick_raises() -> None:
    with pytest.raises(TreeParseError):
        load_tree("not_a_newick_string!!!")


def test_load_tree_missing_file_raises() -> None:
    with pytest.raises(TreeParseError):
        load_tree("/nonexistent/path/to/tree.nwk")
