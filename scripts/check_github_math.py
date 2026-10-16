"""Check GitHub Markdown preprocessing preserves public mathematical source.

Requires authenticated gh. This explicitly sends the selected Markdown files to
GitHub's rendering API; no repository or website state is modified. Client-side
MathJax rendering still requires a browser check after publication.
"""

import argparse
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path


class MathAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.renderers = 0
        self.display = 0
        self.expressions = []
        self._expression = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "math-renderer":
            self.renderers += 1
            self.display += "js-display-math" in attributes.get("class", "")
            self._expression = []

    def handle_endtag(self, tag):
        if tag == "math-renderer" and self._expression is not None:
            self.expressions.append("".join(self._expression))
            self._expression = None

    def handle_data(self, data):
        if self._expression is not None:
            self._expression.append(data)


def check(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    response = subprocess.run(
        ["gh", "api", "markdown", "--method", "POST", "--input", "-"],
        input=json.dumps({"text": text, "mode": "gfm", "context": "Elaybarnoam/LDO"}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    audit = MathAudit()
    audit.feed(response.stdout)
    expected_blocks = (
        len(re.findall(r"^```math\s*$", text, re.M))
        + len(re.findall(r"^\$\$\s*$", text, re.M)) // 2
    )
    if re.search(r"\\operatorname\b", text):
        raise ValueError(f"{path}: operatorname is rejected by GitHub's current math renderer")
    if re.search(
        r"The following macros are not allowed|Undefined control sequence|TeX parse error",
        response.stdout,
    ):
        raise ValueError(f"{path}: GitHub reports a math-rendering error")
    if audit.display != expected_blocks:
        raise ValueError(f"{path}: a mathematical display block was not recognized")
    processed = "\n".join(audit.expressions)
    if r"\{" in text and r"\{" not in processed:
        raise ValueError(f"{path}: Markdown stripped mathematical set delimiters")
    if r"\|" in text and r"\|" not in processed:
        raise ValueError(f"{path}: Markdown stripped double-bar norm delimiters")
    print(
        f"{path}: {audit.renderers} expressions, {audit.display} display blocks; math source preserved"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        type=Path,
        nargs="*",
        default=[Path("README.md"), Path("docs/method.md"), Path("docs/notation.md")],
    )
    for path in parser.parse_args().paths:
        check(path)


if __name__ == "__main__":
    main()
