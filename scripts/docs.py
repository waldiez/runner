# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Handle docs (before, after or build)."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent


def before() -> None:
    """Before build docs."""
    jupyter_example = ROOT_DIR / "examples" / "jupyter" / "task_demo.ipynb"
    docs_example = ROOT_DIR / "docs" / "examples" / "task_demo.ipynb"
    if docs_example.exists():
        os.remove(docs_example)
    shutil.copyfile(jupyter_example, docs_example)
    streamlit_example = ROOT_DIR / "examples" / "streamlit" / "app.py"
    docs_streamlit_example = ROOT_DIR / "docs" / "examples" / "app.py"
    if docs_streamlit_example.exists():
        os.remove(docs_streamlit_example)
    shutil.copyfile(streamlit_example, docs_streamlit_example)
    # Install the requirements for building docs
    requirements_file = ROOT_DIR / "requirements" / "docs.txt"
    if requirements_file.exists():
        pip_install = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_file),
        ]
        subprocess.run(pip_install, check=True)


def after() -> None:
    """After build docs."""
    docs_example = ROOT_DIR / "docs" / "examples" / "task_demo.ipynb"
    if docs_example.exists():
        os.remove(docs_example)
    docs_streamlit_example = ROOT_DIR / "docs" / "examples" / "app.py"
    if docs_streamlit_example.exists():
        os.remove(docs_streamlit_example)


def build(out_dir: Path) -> None:
    """Build docs.

    Parameters
    ----------
    out_dir : Path
        Output directory for the built docs.
    """
    # Run the command to build the docs
    # $(PYTHON) -m mkdocs build -d site
    if out_dir.exists():
        shutil.rmtree(out_dir)
    mkdocs_build = [
        sys.executable,
        "-m",
        "mkdocs",
        "build",
        "-d",
        str(out_dir),
    ]
    subprocess.run(mkdocs_build, check=True)
    output_parent = out_dir.parent
    dir_name = out_dir.name
    msg = (
        f"Docs built successfully in {output_parent}/{dir_name}"
        f"Use: `open file://{output_parent}/{dir_name}/index.html`"
        f"Or `cd {output_parent}/{dir_name}`\n"
        f"and run `python -m http.server --directory {dir_name}`"
    )
    print(msg)


def main() -> None:
    """Main function to handle docs (before, after or build)."""
    parser = argparse.ArgumentParser(
        description="Handle docs (before, after or build)."
    )
    parser.add_argument(
        "command",
        type=str,
        default="build",
        nargs="?",
        choices=["before", "after", "build"],
        help="Command to run: before, after or build.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="site",
        help="Output directory for the built docs.",
    )
    args, _ = parser.parse_known_args()

    if args.command == "before":
        before()
    elif args.command == "after":
        after()
    elif args.command == "build":
        before()
        if args.output:
            resolved_output = Path(str(args.output)).resolve()
        else:
            resolved_output = ROOT_DIR / "site"
        build(resolved_output)
        after()


if __name__ == "__main__":
    main()
