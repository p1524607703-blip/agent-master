import contextlib
import io
import json
from pathlib import Path

root = Path.cwd()
report_dir = root / "outputs/amazon-intent-cluster/AJ2-Y90/report"
source = report_dir / "AJ2-Y90意图需求分析.py"
target = report_dir / "AJ2-Y90意图需求分析.ipynb"

cells = []
kind = None
buffer = []


def flush():
    global buffer, kind
    if kind is None:
        buffer = []
        return
    text = "".join(buffer)
    if kind == "markdown":
        lines = []
        for line in text.splitlines():
            if line.startswith("# "):
                lines.append(line[2:])
            elif line == "#":
                lines.append("")
            else:
                lines.append(line)
        cells.append({"cell_type": "markdown", "metadata": {}, "source": "\n".join(lines).strip().splitlines(keepends=True)})
    else:
        cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip().splitlines(keepends=True)})
    buffer = []


for line in source.read_text(encoding="utf-8").splitlines(keepends=True):
    if line.startswith("# %% [markdown]"):
        flush()
        kind = "markdown"
    elif line.startswith("# %%"):
        flush()
        kind = "code"
    else:
        buffer.append(line)
flush()

namespace = {"__name__": "__main__"}
execution_count = 0
for cell in cells:
    if cell["cell_type"] != "code":
        continue
    execution_count += 1
    cell["execution_count"] = execution_count
    stream = io.StringIO()
    code = "".join(cell["source"])
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        exec(compile(code, str(source), "exec"), namespace)
    output = stream.getvalue()
    if output:
        cell["outputs"] = [{"name": "stdout", "output_type": "stream", "text": output.splitlines(keepends=True)}]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

target.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(target)
