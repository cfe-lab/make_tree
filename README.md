# Tree Maker

Tree Maker is a Python script that allows you to create and visualize phylogenetic trees in a simple and automated way.

## Features

- Produces phylogenetic trees in PDF format.
- Customizable label colors and styles.
- Supports Python 3.8 and higher.

## Installation

#### Option 1: Clone the repository

```shell
git clone https://github.com/cfe-lab/make_tree.git
pip install  .
```

#### Option 2: Install directly from the repository

```shell
pip install git+https://github.com/cfe-lab/make_tree
```

#### Development

For development dependencies use [hatch](https://github.com/pypa/hatch).

Activate an environment with `hatch env create [dev|test]`.

Test with `hatch env run -e test cov`

# Usage

> **Note:** tree_maker requires trees be generated from [Clustal](http://www.clustal.org/)!

To use Tree Maker, run the following command:

```shell
make_tree input.newick output.pdf
```

Alternatively, import it into your own project:

```python
from make_tree import load_tree, export_tree

t = load_tree("A,B,C;")
export_tree(t, "/tmp/tree.pdf", "My tree")
```

This will generate a PDF file containing the phylogenetic tree.

# Contributing

Contributions to Tree Maker are welcome!
If you find any issues or have suggestions for improvements, please open an issue or submit a pull request on the GitHub repository.

# License

Tree Maker is licensed under the GNU General Public License v3.0. See the LICENSE file for more details.
