#! /usr/bin/env python3

"""
Tree maker script.

I am responsible for (automated) production of pretty PDFs.

Global Variables:
- `COLOUR_LIST`: Tree labels are displayed in these colours.
- `LABEL_RE`: Tree labels encode the colour information and italic/bold style.
   They are parsed according to the this regex.
   Basically it's (i)talic/(b)old flag first, then colour index, then the actual label.
"""

import os
import re
from typing import Any, Dict, Optional, Tuple

from ete4 import Tree  # Tree drawing library

COLOUR_LIST = [
    "#000000",
    "#e6194b",
    "#0082c8",
    "#3cb44b",
    "#f58231",
    "#911eb4",
    "#46f0f0",
    "#f032e6",
    "#d2f53c",
    "#008080",
    "#800000",
    "#aaffc3",
    "#808000",
    "#000080",
    "#808080",
    "#88c6ed",
    "#0B610B",
    "#663399",
]

LABEL_RE = re.compile(r"(i|b)?([0-9]+)?!!(.*)")


def parse_label(label: str) -> Tuple[Optional[str], Optional[int], str]:
    """
    _summary_

    :param label: _description_
    :type label: str
    :raises ValueError: _description_
    :raises ValueError: _description_
    :return: _description_
    :rtype: Tuple[str | None, int | None, str]
    """
    match = LABEL_RE.match(label)
    _colourindex: Optional[int] = None
    font, colourindex, name = (None, None, label)

    if match:
        font, colourindex, name = match.groups()

    if "!!" in label and not font and not colourindex:
        raise ValueError(f'Bad label "{label}". Should look like "b7!!E12345".')

    if colourindex and colourindex.isnumeric():
        _colourindex = int(colourindex)
        if not 1 <= _colourindex <= len(COLOUR_LIST) - 1:
            raise ValueError(
                f'Bad colour index in "{label}". '
                + f"Expecting a number between 1 and {len(COLOUR_LIST) - 1}"
            )

    return (font, _colourindex, name)


def get_result_dimensions(result: Dict[str, Any]) -> Tuple[int, int]:
    """Returns the width and the height of exported tree image."""

    w = max(m[2] for m in result["node_areas"].values())
    h = max(m[3] for m in result["node_areas"].values())
    return (w, h)


def export_tree(
    t: Tree,
    output_path: str,
    title: Optional[str] = None,
    variable_height: bool = False,
) -> Dict[str, Any]:
    """
    Exports tree to a file

    :param t: ...
    :type t: Tree
    :param output_path: ...
    :type output_path: str
    :param title: Title rendered on output
    :type title: str | None
    :param variable_height: If set to true the page will be sized to fit the
    tree, otherwise the tree will be resized to fit a 8.5x11" page,
    defaults to False
    :type variable_height: bool, optional
    :return: ...
    :rtype: Dict[str, Any]
    """
    from ete4.treeview import TextFace, TreeStyle

    ts = TreeStyle()
    ts.show_leaf_name = False
    ts.margin_left = 15
    ts.margin_right = 15
    ts.branch_vertical_margin = -2  # This only affects trees with many leaves
    ts.min_leaf_separation = 0

    w = 8.5
    h: Optional[int] = None

    if not variable_height:
        h = 11
        # Here we are adjusting the tree width to maintain the aspect ratio.
        # To do this we get the desired aspect ratio (var_h/var_w)
        # by generating a variable-height output image,
        # and divide it by the required one (h/w)
        # to get the "stretch factor".
        var = export_tree(t, output_path, title, variable_height=True)
        var_w, var_h = get_result_dimensions(var)
        ts.tree_width *= (var_h / var_w) / (h / w)

    if title:
        ts.title.add_face(TextFace(title, fsize=12, bold=True), column=0)

    # The ete4 library uses PyQt6, which only works on servers
    # with physical screens, unless the following option is used:
    # More info: https://github.com/NVlabs/instant-ngp/discussions/300#discussioncomment-4814215
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    _apply_node_styles(t)
    result: Dict[str, Any] = t.render(output_path, w=w, h=h, units="in", tree_style=ts)
    return result


def reverse_tree(node: Tree) -> None:
    node.children = node.children[::-1]
    for child in node.children:
        reverse_tree(child)


def interpolate(start: float, end: float, t: float) -> float:
    """For t between 0 and 1, returns a number between start and end."""
    return (1 - t) * start + end * t


def get_optimal_font_size(t: Tree) -> int:
    """
    Performs a calculation for the best font size with respect to the number of
    leaves in the tree

    :param t: ...
    :type t: Tree
    :return: ...
    :rtype: int
    """
    leaf_count = sum(1 for _ in t.leaves())
    x = min(1, leaf_count / 120)
    return round(interpolate(12, 4, x))


def process_tree_labels(t: Tree) -> None:
    # Some edge lengths can be negative.
    # For those cases we follow instructions from http://www.icp.ucl.ac.be/~opperd/private/neighbor.html
    for node in t.traverse():
        if node.dist is not None and node.dist < 0:
            d = abs(node.dist)
            for c in node.up.children:
                c.dist = (c.dist or 0) + d
            node.dist = 0

    # Sometimes the tree root can be moved to a chosen node.
    # It is signified by the label "REF_ROOT" or "REF_ROOT_HIDE".
    for node in t.traverse():
        if node.name and ("REF_ROOT" in node.name or "REF_ROOT_HIDE" in node.name):
            t.set_outgroup(node)

    # Node with label "REF_ROOT_HIDE" must not be visible on the resulting picture.
    # We simply remove it from the tree. It is not expected to be the actual tree root.
    for node in t.traverse():
        if node.name and "REF_ROOT_HIDE" in node.name and node.up:
            node.up.children.remove(node)


def _apply_node_styles(t: Tree) -> None:
    """Apply visual styles (TextFace, NodeStyle) to all nodes. Requires PyQt6."""
    from ete4.treeview import NodeStyle, TextFace

    fsize = get_optimal_font_size(t)
    for node in t.traverse():
        (font, colourindex, name) = (
            parse_label(node.name) if node.name else (None, None, "")
        )
        colour = COLOUR_LIST[colourindex or 0]

        bold = font == "b"
        fstyle = "italic" if font == "i" else "normal"
        face = TextFace(name, fgcolor=colour, bold=bold, fstyle=fstyle, fsize=fsize)
        nstyle = NodeStyle()
        nstyle["size"] = 0
        nstyle["hz_line_width"] = 1
        nstyle["vt_line_width"] = 1

        node.set_style(nstyle)
        node.add_face(face, column=0)


def load_tree(input_path: str) -> Tree:
    """
    Load a tree into a Tree object.

    :param input_path: Can be either a file path or a newick string.
    For example `(A,B,C);`
    :type input_path: str
    :return: ...
    :rtype: Tree
    """
    if os.path.isfile(input_path):
        with open(input_path) as f:
            t = Tree(f)
    else:
        t = Tree(input_path)
    reverse_tree(t)
    process_tree_labels(t)
    return t
