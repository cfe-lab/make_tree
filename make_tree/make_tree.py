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
import toyplot.font as _toyplot_font
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

# ---------------------------------------------------------------------------
# Page geometry & font metrics
# ---------------------------------------------------------------------------

_PAGE_W: float = 612.0  # letter width  (8.5 in × 72 pt/in)
_PAGE_H: float = 792.0  # letter height (11 in × 72 pt/in)
_PADDING: float = 50.0  # canvas padding passed to every draw() call
_TIP_XSHIFT: int = 5  # rightward shift (canvas units) for tip labels

# toyplot.font measures widths/heights in points; canvas units match PDF
# points 1-to-1, BUT the font library converts `Npx` → `N*0.75 pt` internally.
# To get canvas-unit widths we therefore scale back: pt × (1/0.75) = pt × 4/3.
_PT_TO_CU: float = 4.0 / 3.0

_FONT_LIB = _toyplot_font.ReportlabLibrary()


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


# ---------------------------------------------------------------------------
# Font measurement & layout helpers
# ---------------------------------------------------------------------------


def _text_width_cu(text: str, size_px: int, bold: bool = False) -> float:
    """Return the rendered width of *text* in canvas units.

    Uses the toyplot ReportLab font library for accurate glyph metrics.
    """
    style: dict[str, str] = {"font-size": f"{size_px}px", "font-family": "helvetica"}
    if bold:
        style["font-weight"] = "bold"
    return float(_FONT_LIB.font(style).width(text)) * _PT_TO_CU


def _font_height_cu(size_px: int) -> float:
    """Return the total line height (ascent + |descent|) in canvas units."""
    f = _FONT_LIB.font({"font-size": f"{size_px}px", "font-family": "helvetica"})
    return float(f.ascent - f.descent) * _PT_TO_CU


def _required_gutter(
    node_styles: list[dict[str, Any]], ntips: int, font_size: int
) -> int:
    """Return the horizontal gutter (canvas units) needed for the widest tip label.

    This value is passed directly to ``ToyTree.draw(shrink=...)`` so the
    trunk never overlaps the labels.
    """
    max_w = 0.0
    for info in node_styles[:ntips]:
        text = info["text"]
        if text:
            max_w = max(max_w, _text_width_cu(text, font_size, info["bold"]))
    return int(max_w + _TIP_XSHIFT + 12)  # 12 cu safety margin


def _layout_fits(
    node_styles: list[dict[str, Any]], ntips: int, font_size: int
) -> tuple[bool, int]:
    """Return ``(fits, gutter)`` for *font_size*.

    A layout *fits* when the font line height is at most 160 % of the
    vertical pitch between adjacent tip rows.  The font metric height
    includes internal leading and descenders; visible cap-height is roughly
    70 % of it, so at factor 1.6 the glyph bodies leave a slightly more
    obvious gap between rows while still allowing compact dense layouts.
    """
    gutter = _required_gutter(node_styles, ntips, font_size)
    font_h = _font_height_cu(font_size)
    vertical_pitch = (_PAGE_H - 2 * _PADDING) / max(1, ntips)
    fits = font_h <= vertical_pitch * 1.6
    return fits, gutter


def _find_best_font_size(
    node_styles: list[dict[str, Any]], ntips: int
) -> tuple[int, int]:
    """Binary-search the largest integer font size in ``[4, 18]`` that fits.

    The upper bound of 18 pt prevents absurdly large labels on very sparse
    trees.  Fit is determined purely from font metrics and page geometry —
    no rendering pass is needed.  Returns ``(best_size, best_gutter)``.
    """
    lo, hi = 4, 18
    best_size, best_gutter = 4, _required_gutter(node_styles, ntips, 4)
    while lo <= hi:
        mid = (lo + hi) // 2
        ok, gutter = _layout_fits(node_styles, ntips, mid)
        if ok:
            best_size = mid
            best_gutter = gutter
            lo = mid + 1
        else:
            hi = mid - 1
    return best_size, best_gutter


def _add_labels(
    t: toytree.ToyTree,
    axes: Any,
    node_styles: list[dict[str, Any]],
    font_size: int,
) -> None:
    """Add per-node text labels to *axes* with proper CSS anchoring.

    Tip labels use ``text-anchor: start`` so text originates immediately to
    the right of the tip node.  Internal labels use ``text-anchor: middle``
    to stay centred on the node.  Both use ``alignment-baseline: middle``
    for vertical centring.
    """
    ntips = t.ntips
    nnodes = t.nnodes

    groups: dict[tuple[bool, bool, bool, str], list[tuple[int, str]]] = defaultdict(
        list
    )
    for idx, info in enumerate(node_styles):
        if info["text"]:
            key = (idx < ntips, info["bold"], info["italic"], info["color"])
            groups[key].append((idx, info["text"]))

    for (is_tip, bold, italic, color), node_list in groups.items():
        labels: list[str] = [""] * nnodes
        mask: list[bool] = [False] * nnodes
        for idx, text in node_list:
            labels[idx] = f"<i>{text}</i>" if italic else text
            mask[idx] = True

        style: dict[str, str] = {
            "alignment-baseline": "middle",
            "text-anchor": "start" if is_tip else "middle",
        }
        if bold:
            style["font-weight"] = "bold"

        t.annotate.add_node_labels(
            axes,
            labels,
            mask=mask,
            color=color,
            font_size=font_size,
            xshift=_TIP_XSHIFT if is_tip else 0,
            style=style,
        )


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
    """Export *t* to a letter-size (8.5 x 11 in) PDF or SVG.

    Renders a right-facing rectangular phylogram with per-node label colours
    and bold/italic styling derived from the :func:`parse_label` encoding.
    All named nodes — tips and internal — receive labels.

    The font size is chosen by binary search (largest integer in ``[4, 40]``
    that fits vertically).  The horizontal gutter for tip labels is computed
    from measured text widths and passed to ``ToyTree.draw(shrink=...)`` so
    the tree trunk never collides with labels.  Tip labels use
    ``text-anchor: start`` so they originate flush with the tip node;
    internal labels use ``text-anchor: middle``.

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
    node_styles = _collect_node_styles(t)
    fsize, shrink = _find_best_font_size(node_styles, t.ntips)

    canvas, axes, _ = t.draw(
        scale_bar=True,
        layout="r",
        width=_PAGE_W,
        height=_PAGE_H,
        padding=_PADDING,
        shrink=shrink,
        node_sizes=0,
        node_mask=True,
        tip_labels=False,
        edge_widths=1.5,
        edge_style={"stroke": "#2c3e50", "stroke-linecap": "round"},
        label=title or "",
    )

    _add_labels(t, axes, node_styles, fsize)

    is_pdf = output_path.lower().endswith(".pdf")

    if is_pdf:
        svg_elem = toyplot.svg.render(canvas)
        surface = _rl_canvas.Canvas(output_path, pagesize=(_PAGE_W, _PAGE_H))
        surface.translate(0, _PAGE_H)
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
