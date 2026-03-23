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

import re
from collections import defaultdict
from typing import Any

import reportlab.pdfgen.canvas as _rl_canvas
import toyplot
import toyplot.reportlab
import toyplot.reportlab.pdf
import toyplot.svg
import toytree
import toytree.mod

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


class TreeParseError(Exception):
    """Raised when a Newick string or file cannot be parsed as a tree."""


def parse_label(label: str) -> tuple[str | None, int | None, str]:
    """Parse a node label encoding font style, colour index and display text.

    Labels may optionally carry a font flag (``i`` or ``b``) and a numeric
    colour index from :data:`COLOUR_LIST`, separated from the actual display
    text by ``!!``.  Examples: ``test``, ``i!!test``, ``b2!!test``.

    :param label: Raw node name string.
    :type label: str
    :raises ValueError: If the label contains ``!!`` but is not well-formed.
    :raises ValueError: If the colour index is out of range.
    :return: ``(font_flag, colour_index, display_text)`` where *font_flag* is
        ``"i"``, ``"b"``, or ``None``; *colour_index* is an ``int`` or
        ``None``.
    :rtype: Tuple[str | None, int | None, str]
    """
    match = LABEL_RE.match(label)
    _colourindex: int | None = None
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


def interpolate(start: float, end: float, t: float) -> float:
    """For t between 0 and 1, returns a number between start and end."""
    return (1 - t) * start + end * t


def get_optimal_font_size(t: toytree.ToyTree) -> int:
    """Return an appropriate font size for the number of leaves in *t*.

    :param t: Tree to size labels for.
    :type t: toytree.ToyTree
    :return: Font size in points.
    :rtype: int
    """
    leaf_count = t.ntips
    x = min(1, leaf_count / 120)
    return round(interpolate(12, 4, x))


def _reverse_node(node: "toytree.Node") -> None:
    """Recursively reverse the children tuple of *node* in place."""
    node._children = node._children[::-1]
    for child in node._children:
        _reverse_node(child)


def reverse_tree(t: toytree.ToyTree) -> None:
    """Recursively reverse the child order of every node in *t*.

    Modifies *t* in place.  The resulting tip order is the reverse of the
    original parse order, preserving the historical ordering behaviour.

    :param t: Tree to reverse.
    :type t: toytree.ToyTree
    """
    _reverse_node(t.treenode)
    t._update()


def process_tree_labels(t: toytree.ToyTree) -> toytree.ToyTree:
    """Normalise negative branch lengths and apply REF_ROOT semantics.

    Steps performed (in order):

    1. For any node with a negative ``dist``, shift ``abs(dist)`` onto each
       sibling edge and zero the negative edge.
    2. If any node name contains ``REF_ROOT`` or ``REF_ROOT_HIDE``, reroot
       the tree on that node.
    3. If any node name contains ``REF_ROOT_HIDE``, drop that tip from the
       tree and clean up any resulting unary nodes.

    Because rerooting and tip-removal return new :class:`toytree.ToyTree`
    objects, always use the *returned* tree rather than the argument.

    :param t: Tree to preprocess.
    :type t: toytree.ToyTree
    :return: Preprocessed tree (may be a new object if rerooted/pruned).
    :rtype: toytree.ToyTree
    """
    # Fix negative branch lengths
    for node in t.traverse():
        if node.dist is not None and node.dist < 0:
            d = abs(node.dist)
            for sibling in node.up.children:
                sibling._dist = (sibling.dist or 0) + d
            node._dist = 0.0
    t._update()

    # Reroot on the first node whose name contains REF_ROOT or REF_ROOT_HIDE
    for node in t.traverse():
        if node.name and ("REF_ROOT" in node.name or "REF_ROOT_HIDE" in node.name):
            t = t.root(node.name)
            break

    # Drop the REF_ROOT_HIDE tip and clean up any resulting unary nodes
    for node in t.traverse():
        if node.name and "REF_ROOT_HIDE" in node.name and node.is_leaf():
            t = toytree.mod.drop_tips(t, node.name)
            t = toytree.mod.remove_unary_nodes(t)
            break

    return t


def _collect_node_styles(t: toytree.ToyTree) -> list[dict[str, Any]]:
    """Return a list of style dicts for every node in idx order.

    Each dict has keys: ``text`` (display string), ``color`` (hex),
    ``bold`` (bool), ``italic`` (bool).
    """
    result = []
    for node in t[:]:  # idx-ordered slice
        if node.name:
            font, ci, text = parse_label(node.name)
        else:
            font, ci, text = None, None, ""
        result.append(
            {
                "text": text,
                "color": COLOUR_LIST[ci or 0],
                "bold": font == "b",
                "italic": font == "i",
            }
        )
    return result


def export_tree(
    t: toytree.ToyTree,
    output_path: str,
    title: str | None = None,
) -> None:
    """Export *t* to a letter-size (8.5 x 11 in) PDF.

    Renders a rectangular phylogram with per-node label colours and
    bold/italic styling derived from the :func:`parse_label` encoding.
    All named nodes — tips and internal — receive labels.

    PDF output uses toyplot and reportlab; no Qt or PyQt dependency is
    required.  SVG output is also supported when *output_path* ends with
    ``.svg``.

    :param t: Preprocessed tree to render.
    :type t: toytree.ToyTree
    :param output_path: Destination file path (PDF or SVG).
    :type output_path: str
    :param title: Optional title drawn above the tree.
    :type title: str | None
    :return: None
    """
    # Letter size: 8.5 x 11 inches expressed as points (1 pt = 1/72 in)
    PAGE_W, PAGE_H = 612.0, 792.0

    fsize = get_optimal_font_size(t)
    node_styles = _collect_node_styles(t)
    ntips = t.ntips
    nnodes = t.nnodes

    # Group nodes by (is_tip, bold, italic, color) — one add_node_labels() per group.
    # Tip labels receive an xshift so they don't overlap branch lines.
    groups: dict[tuple[bool, bool, bool, str], list[tuple[int, str]]] = defaultdict(
        list
    )
    for idx, info in enumerate(node_styles):
        if info["text"]:
            key = (idx < ntips, info["bold"], info["italic"], info["color"])
            groups[key].append((idx, info["text"]))

    # Draw the base tree (tip labels off — handled uniformly by add_node_labels)
    canvas, axes, mark = t.draw(
        scale_bar=True,
        layout="r",
        width=PAGE_W,
        height=PAGE_H,
        padding=50,
        node_sizes=0,
        node_mask=True,
        tip_labels=False,
        edge_widths=1.5,
        edge_style={"stroke": "#2c3e50", "stroke-linecap": "round"},
        label=title or "",
    )

    # Add labels for each (is_tip, bold, italic, color) group.
    # Italic is expressed via toyplot rich-text <i>…</i> markup in the label
    # text itself, because toyplot's CSS validator does not allow font-style.
    for (is_tip, bold, italic, color), node_list in groups.items():
        labels: list[str] = [""] * nnodes
        mask: list[bool] = [False] * nnodes
        for idx, text in node_list:
            labels[idx] = f"<i>{text}</i>" if italic else text
            mask[idx] = True
        style: dict[str, str] = {"font-weight": "bold"} if bold else {}
        t.annotate.add_node_labels(
            axes,
            labels,
            mask=mask,
            color=color,
            font_size=fsize,
            xshift=10 if is_tip else 0,
            style=style or None,
        )

    is_pdf = output_path.lower().endswith(".pdf")

    if is_pdf:
        svg_elem = toyplot.svg.render(canvas)
        surface = _rl_canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
        surface.translate(0, PAGE_H)
        surface.scale(1, -1)
        toyplot.reportlab.render(svg_elem, surface)
        surface.showPage()
        surface.save()
    else:
        toyplot.svg.render(canvas, output_path)


def load_tree(input_path: str) -> toytree.ToyTree:
    """Load a tree from a file path or a raw Newick string.

    After parsing, the tree is preprocessed by :func:`reverse_tree` and
    :func:`process_tree_labels`.

    :param input_path: Either a path to a Newick file or a Newick string
        such as ``"(A,B,C);"``
    :type input_path: str
    :raises TreeParseError: If the input cannot be parsed as a valid tree.
    :return: Loaded and preprocessed tree.
    :rtype: toytree.ToyTree
    """
    try:
        t = toytree.tree(input_path)
    except Exception as exc:
        raise TreeParseError(
            f"Could not parse tree from {input_path!r}: {exc}"
        ) from exc

    reverse_tree(t)
    t = process_tree_labels(t)
    return t
