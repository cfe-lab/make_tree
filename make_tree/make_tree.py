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

import argparse
import os
import sys
import re
import ete3  # Tree drawing library

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


def parse_label(label: str) -> (str, int, str):
    match = LABEL_RE.match(label)
    if match:
        font, colourindex, name = match.groups()
    else:
        font, colourindex, name = (None, None, label)

    if "!!" in label and not font and not colourindex:
        raise ValueError(f'Bad label "{label}". Should look like "b7!!E12345".')

    if colourindex:
        colourindex = int(colourindex)
        if not 1 <= colourindex <= len(COLOUR_LIST) - 1:
            raise ValueError(
                f'Bad colour index in "{label}". '
                + f"Expecting a number between 1 and {len(COLOUR_LIST) - 1}"
            )

    return (font, colourindex, name)


def get_result_dimensions(result: dict) -> (int, int):
    """Returns the width and the height of exported tree image."""

    get_x2 = lambda m: m[2]
    get_y2 = lambda m: m[3]
    w = max([get_x2(m) for m in result["node_areas"].values()])
    h = max([get_y2(m) for m in result["node_areas"].values()])
    return (w, h)


def export_tree(
    t: ete3.Tree, output_path: str, title: str, variable_height: bool = False
):
    ts = ete3.TreeStyle()
    ts.show_leaf_name = False
    ts.margin_left = 15
    ts.margin_right = 15
    ts.branch_vertical_margin = -2  # This only affects trees with many leaves
    ts.min_leaf_separation = 0

    w = 8.5
    h = 11 if not variable_height else None

    if not variable_height:
        # Here we are adjusting the tree width to maintain the aspect ratio.
        # To do this we get the desired aspect ratio (var_h/var_w)
        # by generating a variable-height output image,
        # and divide it by the required one (h/w)
        # to get the "stretch factor".
        var = export_tree(t, output_path, title, variable_height=True)
        var_w, var_h = get_result_dimensions(var)
        ts.tree_width *= (var_h / var_w) / (h / w)

    if title:
        ts.title.add_face(ete3.TextFace(title, fsize=12, bold=True), column=0)

    # The ete3 library uses PyQt, which only works on servers
    # with physical screens, unless the following option is used:
    # More info: https://github.com/NVlabs/instant-ngp/discussions/300#discussioncomment-4814215
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    return t.render(output_path, w=w, h=h, units="in", tree_style=ts)


def reverse_tree(node: ete3.Tree) -> None:
    node.children = node.children[::-1]
    for child in node.children:
        reverse_tree(child)


def interpolate(start: float, end: float, t: float) -> float:
    """For t between 0 and 1, returns a number between start and end."""
    return (1 - t) * start + end * t


def get_optimal_font_size(t: ete3.Tree) -> int:
    leaf_count = sum(1 for _ in t.iter_leaves())
    t = min(1, leaf_count / 120)
    return round(interpolate(12, 4, t))


def process_tree_labels(t: ete3.Tree) -> None:
    # Some edge lengths can be negative.
    # For those cases we follow instructions from http://www.icp.ucl.ac.be/~opperd/private/neighbor.html
    for node in t.traverse():
        if node.dist < 0:
            d = abs(node.dist)
            for c in node.up.children:
                c.dist += d
            node.dist = 0

    # Sometimes the tree root can be moved to a chosen node.
    # It is signified by the label "REF_ROOT" or "REF_ROOT_HIDE".
    for node in t.traverse():
        if "REF_ROOT" in node.name or "REF_ROOT_HIDE" in node.name:
            t.set_outgroup(node)

    # Node with label "REF_ROOT_HIDE" must not be visible on the resulting picture.
    # We simply remove it from the tree. It is not expected to be the actual tree root.
    for node in t.traverse():
        if "REF_ROOT_HIDE" in node.name and node.up:
            node.up.children.remove(node)

    # Style individual nodes and labels.
    fsize = get_optimal_font_size(t)
    for node in t.traverse():
        (font, colourindex, name) = (
            parse_label(node.name) if node.name != "" else (None, None, "")
        )
        colour = COLOUR_LIST[colourindex or 0]

        bold = True if font == "b" else False
        fstyle = "italic" if font == "i" else "normal"
        face = ete3.TextFace(
            name, fgcolor=colour, bold=bold, fstyle=fstyle, fsize=fsize
        )
        nstyle = ete3.NodeStyle(size=0, hz_line_width=1, vt_line_width=1)

        node.set_style(nstyle)
        node.add_face(face, column=0)


def load_tree(input_path: str) -> ete3.Tree:
    t = ete3.Tree(input_path)
    reverse_tree(t)  # TODO: make sure this is still required.
    process_tree_labels(t)
    return t


def main():
    parser = argparse.ArgumentParser(
        description="Tree maker script. Produces pretty PDFs."
    )
    parser.add_argument(
        "input_path",
        help="Input (.ph) file path. Expected to have the input tree definition. Newick format is supported",
    )
    parser.add_argument("output_path", help="Output (.pdf) file path")
    parser.add_argument(
        "title", nargs=argparse.OPTIONAL, default=None, help="Tree title"
    )
    args = parser.parse_args()

    try:
        t = load_tree(args.input_path)
    except ete3.parser.newick.NewickError as e:
        print(
            "Error: The tree file is not in the expected format. Please make sure it uses the standard Newick format.",
            file=sys.stderr,
        )
        exit(1)

    export_tree(t, args.output_path, args.title)

