import argparse
import sys
from .make_tree import export_tree, load_tree
from ete3.parser.newick import NewickError


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
    except NewickError as e:
        print(
            "Error: The tree file is not in the expected format. Please make sure it uses the standard Newick format.",
            file=sys.stderr,
        )
        exit(1)

    export_tree(t, args.output_path, args.title)


if __name__ == "__main__":
    main()
