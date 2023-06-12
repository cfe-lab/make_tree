import os
import pytest
import ete3
from make_tree.make_tree import parse_label, reverse_tree, interpolate, get_optimal_font_size, process_tree_labels, export_tree

def test_parse_label_basic():
    assert parse_label("test") == (None, None, "test")
    assert parse_label("i!!test") == ("i", None, "test")
    assert parse_label("b2!!test") == ("b", 2, "test")

def test_parse_label_errors():
    with pytest.raises(ValueError):
        parse_label("!!test")
    with pytest.raises(ValueError):
        parse_label("b0!!test")
    with pytest.raises(ValueError):
        parse_label("z2!!test")
    with pytest.raises(ValueError):
        parse_label("b100!!test")

@pytest.mark.parametrize(
    "tree_input, expected_output",
    [
        (None, None),
        ("(A);", "(A);"),
        ("(A,B,C);", "(C,B,A);"),
        ("(A,B,(C,D,(E,F)));", "(((F,E),D,C),B,A);")
    ],
    ids=["Empty Tree", "One Node", "Three Node", "Six Node"]
)
def test_reverse_tree(tree_input, expected_output):
    t = ete3.Tree(tree_input)
    reverse_tree(t)
    expected = ete3.Tree(expected_output)
    assert str(t) == str(expected)

@pytest.mark.parametrize(
    "a, b, c, exp_output",
    [
        (0, 10, 0.5, 5.0),
        (-10, 10, 0.5, 0.0),
        (0, 100, 0.75, 75.0)
    ]
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
    "tree_str",
    [
        "(A,B,(C,REF_ROOT),E);",
        "(A,B,(C,REF_ROOT_HIDE),E);"
    ]
)
def test_process_tree_labels_reroots(tree_str):
    t = ete3.Tree(tree_str)
    s1 = str(t)
    process_tree_labels(t)
    s2 = str(t)
    assert not s1 == s2

def test_export(tmp_path):
    t = ete3.Tree("(A,B,(C,D),E);")
    output_path = os.path.join(tmp_path, "output.pdf")
    export_tree(t, output_path, "my title")
    assert os.path.exists(output_path)
