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
    """Returns the rendered pixel width and height from an export_tree result dict."""
    w = max(m[2] for m in result["node_areas"].values())
    h = max(m[3] for m in result["node_areas"].values())
    return (w, h)


def _natural_scene_ratio(t: Tree, ts: Any) -> float:
    """Return the natural height/width ratio of the tree scene built in memory.

    Builds the full Qt scene (with all faces already applied) without writing
    any file, then reads ``scene.sceneRect()`` for the intrinsic dimensions.
    This is used to adjust ``ts.tree_width`` before the real render so that
    Qt's ``IgnoreAspectRatio`` stretch (applied when both w and h are fixed)
    does not distort the tree.
    """
    from ete4.treeview import drawer as _drawer
    from ete4.treeview.qt_render import render as _qt_render

    # render_tree also assigns _nid; mirror that here so the probe is identical
    for nid, n in enumerate(t.traverse("preorder")):
        n.add_prop("_nid", nid)

    scene, img = _drawer.init_scene(t, None, ts)
    tree_item, n2i, n2f = _qt_render(t, img)
    scene.init_values(t, img, n2i, n2f)
    tree_item.setParentItem(scene.master_item)
    scene.master_item.setPos(0, 0)
    scene.addItem(scene.master_item)

    sr = scene.sceneRect()
    return sr.height() / sr.width()


def export_tree(
    t: Tree,
    output_path: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Exports tree to a letter-size (8.5×11") PDF.

    The tree is scaled horizontally so that its natural aspect ratio matches
    the page, preventing any distortion when Qt renders into fixed dimensions.
    The ratio is probed by building the Qt scene in memory (no file I/O) and
    reading ``scene.sceneRect()`` before the single final render.

    :param t: Tree to render.
    :type t: Tree
    :param output_path: Destination file path (PDF recommended).
    :type output_path: str
    :param title: Optional title drawn at the top of the page.
    :type title: str | None
    :return: ete4 image-map dict with ``node_areas``, ``nodes``, and ``faces``.
    :rtype: Dict[str, Any]
    """
    from ete4.treeview import TextFace, TreeStyle
    from ete4.treeview import drawer as _drawer

    # PyQt6 requires this on headless servers.
    # More info: https://github.com/NVlabs/instant-ngp/discussions/300#discussioncomment-4814215
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    ts = TreeStyle()
    ts.show_leaf_name = False
    ts.margin_left = 15
    ts.margin_right = 15
    ts.branch_vertical_margin = -2  # only affects trees with many leaves
    ts.min_leaf_separation = 0

    if title:
        ts.title.add_face(TextFace(title, fsize=12, bold=True), column=0)

    # Apply visual styles once, before probing — the probe must see the same
    # faces that the final render will use so the ratio measurement is accurate.
    _apply_node_styles(t)

    # Probe the natural scene ratio in memory (no file write).
    # When both w and h are fixed, ete4 uses IgnoreAspectRatio, which distorts
    # the tree if its intrinsic ratio differs from the target page ratio.
    # Adjusting tree_width makes the two ratios match, so the stretch is neutral.
    PAGE_W, PAGE_H = 8.5, 11.0
    natural_ratio = _natural_scene_ratio(t, ts)
    ts.tree_width *= natural_ratio / (PAGE_H / PAGE_W)

    return _drawer.render_tree(
        t, output_path, w=PAGE_W, h=PAGE_H, units="in", tree_style=ts
    )


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
