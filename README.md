[![Lint](https://github.com/cfe-lab/make_tree/actions/workflows/lint.yml/badge.svg)](https://github.com/cfe-lab/make_tree/actions/workflows/lint.yml)
[![Typecheck](https://github.com/cfe-lab/make_tree/actions/workflows/typecheck.yml/badge.svg)](https://github.com/cfe-lab/make_tree/actions/workflows/typecheck.yml)
[![types - Mypy](https://img.shields.io/badge/types-Mypy-blue.svg)](https://github.com/python/mypy)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

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
uv tool install .
```

#### Option 2: Install directly from the repository

```shell
uv tool install git+https://github.com/cfe-lab/make_tree
```

#### Development

Use [uv](https://github.com/astral-sh/uv) to manage the environment.

Install all dev dependencies:

```shell
uv sync --extra test --extra dev
```

Test:

```shell
uv run pytest
```

Lint:

```shell
uv run ruff check
```

Format:

```shell
uv run ruff format
```

Type-check:

```shell
uv run mypy make_tree tests
```

# Usage

> **Note:** tree_maker requires trees be generated from [Clustal](http://www.clustal.org/)!

> **IMPORTANT:** You will need `libgl1` to use this, `apt install libgl1` for Debian based systems.

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
