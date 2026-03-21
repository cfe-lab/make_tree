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
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

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

# SVG namespace used by toyplot
_SVG_NS = "http://www.w3.org/2000/svg"


class TreeParseError(Exception):
    """Raised when a Newick string or file cannot be parsed as a tree."""


def parse_label(label: str) -> Tuple[Optional[str], Optional[int], str]:
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


def _collect_node_styles(t: toytree.ToyTree) -> List[Dict[str, Any]]:
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


def _apply_text_styles_to_svg(
    svg_elem: ET.Element,
    italic_texts: Set[str],
    bold_texts: Set[str],
) -> None:
    """Inject ``font-style`` / ``font-weight`` overrides into SVG ``<text>`` elements.

    toyplot's style validator rejects ``font-style``, so italic must be
    applied via direct XML manipulation after the element tree is built.
    Bold is handled the same way for tip labels (which have no per-label
    bold API), and harmlessly reinforces bold already set on internal labels.
    The reportlab renderer honours both properties in element ``style``
    attributes.
    """
    for text_elem in svg_elem.iter(f"{{{_SVG_NS}}}text"):
        text = text_elem.text
        if text not in italic_texts and text not in bold_texts:
            continue
        extra: List[str] = []
        if text in italic_texts:
            extra.append("font-style:italic")
        if text in bold_texts:
            extra.append("font-weight:bold")
        existing = text_elem.get("style", "")
        text_elem.set(
            "style", existing + ";" + ";".join(extra) if existing else ";".join(extra)
        )


def export_tree(
    t: toytree.ToyTree,
    output_path: str,
    title: Optional[str] = None,
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

    # --- Tip labels: handed to draw() for native right-aligned positioning ---
    tip_texts: List[str] = [node_styles[i]["text"] for i in range(ntips)]
    tip_colors: List[str] = [node_styles[i]["color"] for i in range(ntips)]

    # --- Internal node labels: grouped by (bold, italic, color) ---
    int_groups: Dict[Tuple[bool, bool, str], List[Tuple[int, str]]] = defaultdict(list)
    for idx in range(ntips, nnodes):
        info = node_styles[idx]
        if info["text"]:
            key = (info["bold"], info["italic"], info["color"])
            int_groups[key].append((idx, info["text"]))

    # Collect texts that need SVG font-style / font-weight injection
    italic_texts: Set[str] = set()
    bold_texts: Set[str] = set()
    for _idx, info in enumerate(node_styles):
        if info["text"]:
            if info["italic"]:
                italic_texts.add(info["text"])
            if info["bold"]:
                bold_texts.add(info["text"])

    # Draw the base tree
    canvas, axes, mark = t.draw(
        layout="r",
        width=PAGE_W,
        height=PAGE_H,
        padding=50,
        node_sizes=0,
        node_mask=True,
        # Tip labels: built-in positioning with a right-side padding gap
        tip_labels=tip_texts,
        tip_labels_colors=tip_colors,
        tip_labels_style={
            "-toyplot-anchor-shift": "1px",
            "font-size": f"{fsize}px",
        },
        # Slightly thicker, softer edges
        edge_widths=1.5,
        edge_style={"stroke": "#2c3e50", "stroke-linecap": "round"},
        label=title or "",
    )

    # Add internal-node labels, one call per unique (bold, italic, color) group
    for (_bold, _italic, color), node_list in int_groups.items():
        labels: List[str] = [""] * nnodes
        mask: List[bool] = [False] * nnodes
        for idx, text in node_list:
            labels[idx] = text
            mask[idx] = True
        t.annotate.add_node_labels(
            axes,
            labels,
            mask=mask,
            color=color,
            font_size=fsize,
        )

    is_pdf = output_path.lower().endswith(".pdf")

    # SVG post-processing: inject italic / bold into matching text elements
    svg_elem = toyplot.svg.render(canvas)
    if italic_texts or bold_texts:
        _apply_text_styles_to_svg(svg_elem, italic_texts, bold_texts)

    if is_pdf:
        surface = _rl_canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
        surface.translate(0, PAGE_H)
        surface.scale(1, -1)
        toyplot.reportlab.render(svg_elem, surface)
        surface.showPage()
        surface.save()
    else:
        # SVG and other formats: serialize the (possibly italic-patched) tree
        ET.register_namespace("", _SVG_NS)
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
        ET.register_namespace("toyplot", "http://www.sandia.gov/toyplot")
        ET.ElementTree(svg_elem).write(
            output_path, xml_declaration=True, encoding="utf-8"
        )


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
