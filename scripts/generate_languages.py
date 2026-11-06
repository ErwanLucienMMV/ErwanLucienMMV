"""Render a self-contained SVG from selected public repositories.

Run from any directory: python scripts/generate_languages.py
No file is replaced until every API response and the final SVG are valid.
"""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import os
import sys
import tempfile
import xml.etree.ElementTree as ET

if __package__:
    from .language_data import GitHubClient, StatsError, collect_languages, distribution, load_config
else:
    from language_data import GitHubClient, StatsError, collect_languages, distribution, load_config

ROOT = Path(__file__).resolve().parents[1]


def render_svg(totals: dict[str, int], top_n: int = 7, show_other: bool = True) -> bytes:
    rows = distribution(totals, top_n, show_other)
    height = 190 + 32 * len(rows) if rows else 210
    total = sum(row["bytes"] for row in rows)
    scope = "selected public projects" if show_other else "displayed languages only"
    description = "; ".join(f"{row['name']}: {row['tenths'] / 10:.1f}%" for row in rows)
    if not description:
        description = "No language data available"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="720" height="{height}" viewBox="0 0 720 {height}" role="img" aria-labelledby="title description">',
        '<title id="title">Languages across my projects</title>',
        f'<desc id="description">Share of GitHub Linguist code bytes in {scope}. {escape(description)}. This measures repository code, not skill or personal contributions.</desc>',
        '<style>',
        'text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #1f2328; }',
        '.muted { fill: #59636e; } .card { fill: #ffffff; stroke: #d1d9e0; }',
        '.track { fill: #eaeef2; } .swatch { stroke: #59636e; stroke-width: 0.5; }',
        '@media (prefers-color-scheme: dark) { text { fill: #f0f6fc; } .muted { fill: #b1bac4; } .card { fill: #0d1117; stroke: #3d444d; } .track { fill: #212830; } .swatch { stroke: #b1bac4; } }',
        '</style>',
        f'<rect class="card" x="0.5" y="0.5" width="719" height="{height - 1}" rx="16"/>',
        '<text x="28" y="42" font-size="22" font-weight="600">Languages across my projects</text>',
        f'<text class="muted" x="28" y="68" font-size="13">Share of code bytes · {scope}</text>',
    ]
    if rows:
        parts.extend([
            '<defs><clipPath id="bar"><rect x="28" y="90" width="664" height="16" rx="8"/></clipPath></defs>',
            '<rect class="track" x="28" y="90" width="664" height="16" rx="8"/>',
            '<g clip-path="url(#bar)">',
        ])
        consumed = 0
        for row in rows:
            left = 28 + 664 * consumed / total
            consumed += row["bytes"]
            right = 28 + 664 * consumed / total
            parts.append(f'<rect x="{left:.4f}" y="90" width="{right - left:.4f}" height="16" fill="{row["color"]}"/>')
        parts.append('</g>')
        for index, row in enumerate(rows):
            y = 142 + index * 32
            # Keep unusual API labels on one line with an accessible full title.
            name = row["name"].replace("\n", " ").replace("\r", " ").replace("\t", " ")
            label = name if len(name) <= 48 else name[:47] + "…"
            fit = ' textLength="530" lengthAdjust="spacingAndGlyphs"' if len(label) > 36 else ''
            parts.extend([
                f'<circle class="swatch" cx="35" cy="{y - 5}" r="5" fill="{row["color"]}"/>',
                f'<text x="50" y="{y}" font-size="15"{fit}><title>{escape(name)}</title>{escape(label)}</text>',
                f'<text x="692" y="{y}" text-anchor="end" font-size="15" font-weight="600">{row["tenths"] / 10:.1f}%</text>',
            ])
    else:
        parts.append('<text class="muted" x="28" y="118" font-size="16">No language data available</text>')
    parts.append(f'<text class="muted" x="28" y="{height - 26}" font-size="12">Repository code distribution · Not skill or personal contribution</text>')
    parts.append('</svg>')
    result = ("\n".join(parts) + "\n").encode("utf-8")
    ET.fromstring(result)
    return result


def write_if_changed(path: Path, content: bytes) -> bool:
    """Atomic replacement; leave both contents and mtime alone if unchanged."""
    if path.exists() and path.read_bytes() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return True


def generate(config_path: Path, output_path: Path, client: GitHubClient | None = None) -> bool:
    config = load_config(config_path)
    totals = collect_languages(config, client or GitHubClient())
    svg = render_svg(totals, config["top_n"], config["show_other"])
    return write_if_changed(output_path, svg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/languages.json")
    parser.add_argument("--output", type=Path, default=ROOT / "assets/languages.svg")
    args = parser.parse_args(argv)
    # The only supported output is an SVG; refuse accidental README writes.
    if args.output.suffix.casefold() != ".svg":
        parser.error("--output must have an .svg extension")
    try:
        changed = generate(args.config, args.output)
    except (StatsError, OSError) as error:
        print(f"Language statistics update failed: {error}", file=sys.stderr)
        return 1
    print("Updated language SVG" if changed else "Language SVG unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
