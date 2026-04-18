#!/usr/bin/env python3
"""
Fix Kobo/EPUB chapter-heading links that jump back to the TOC.

What it does:
- Opens an EPUB as a ZIP archive
- Scans .xhtml / .html / .htm files
- Finds headings like <h1>...</h1>, <h2>...</h2>, etc.
- If a heading contains a direct <a href="...">...</a> that points to a TOC-like file,
  it removes the <a> wrapper but keeps the inner content

Example:
    <h1 id="ch1"><a href="B1004_toc.xhtml#rch1"><span>1</span> Title</a></h1>

becomes:
    <h1 id="ch1"><span>1</span> Title</h1>

Usage:
    python fix_epub_toc_links.py input.epub
    python fix_epub_toc_links.py input.epub -o output.epub
    python fix_epub_toc_links.py input.epub --in-place
    python fix_epub_toc_links.py input.epub --dry-run

Notes:
- Default behavior writes a new file next to the original:
    original_fixed.epub
- Use --in-place only if you really want to overwrite the original.
- This script is conservative: it only unwraps anchors that are the sole content
  inside a heading and whose href looks TOC-like.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


# Matches heading blocks like <h1 ...>...</h1>, <h2 ...>...</h2>, etc.
HEADING_RE = re.compile(
    r"(?P<open><h(?P<level>[1-6])\b(?P<hattrs>[^>]*)>)"
    r"(?P<inner>.*?)"
    r"(?P<close></h(?P=level)>)",
    re.IGNORECASE | re.DOTALL,
)

# Matches a single anchor that occupies the whole heading content, allowing whitespace around it.
ANCHOR_ONLY_RE = re.compile(
    r"^\s*"
    r"<a\b(?P<aattrs>[^>]*)>"
    r"(?P<acontent>.*?)"
    r"</a>"
    r"\s*$",
    re.IGNORECASE | re.DOTALL,
)

HREF_RE = re.compile(
    r"""\bhref\s*=\s*(?P<q>["'])(?P<href>.*?)(?P=q)""",
    re.IGNORECASE | re.DOTALL,
)

# TOC-like targets. Adjust if needed.
TOC_HINT_RE = re.compile(
    r"(?:^|[/\\._-])(toc|contents|tableofcontents|nav)(?:[/\\._-]|$)|(?:toc|contents|tableofcontents|nav)\.x?html?$",
    re.IGNORECASE,
)


def looks_like_toc_href(href: str) -> bool:
    href = href.strip()
    return bool(TOC_HINT_RE.search(href))


def unwrap_toc_links_in_headings(text: str, file_name: str, verbose: bool = False) -> tuple[str, int]:
    changes = 0

    def replace_heading(match: re.Match[str]) -> str:
        nonlocal changes

        open_tag = match.group("open")
        inner = match.group("inner")
        close_tag = match.group("close")

        anchor_match = ANCHOR_ONLY_RE.match(inner)
        if not anchor_match:
            return match.group(0)

        aattrs = anchor_match.group("aattrs")
        acontent = anchor_match.group("acontent")

        href_match = HREF_RE.search(aattrs)
        if not href_match:
            return match.group(0)

        href = href_match.group("href")
        if not looks_like_toc_href(href):
            return match.group(0)

        changes += 1
        if verbose:
            print(f"[CHANGED] {file_name}: unwrapped heading link -> {href}")

        return f"{open_tag}{acontent}{close_tag}"

    new_text = HEADING_RE.sub(replace_heading, text)
    return new_text, changes


def process_epub(input_path: Path, output_path: Path, dry_run: bool = False, verbose: bool = False) -> int:
    total_changes = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        extract_dir = tmpdir_path / "epub"
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(input_path, "r", metadata_encoding="cp1252") as zin:
            zin.extractall(extract_dir)

        text_extensions = {".xhtml", ".html", ".htm"}

        for file_path in extract_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in text_extensions:
                continue

            raw = file_path.read_bytes()
            original = raw.decode("utf-8", errors="replace")

            # try:
            #     original = file_path.read_text(encoding="utf-8")
            # except UnicodeDecodeError:
            #     try:
            #         original = file_path.read_text(encoding="utf-8-sig")
            #     except UnicodeDecodeError:
            #         try:
            #             original = file_path.read_text(encoding="cp1252")
            #         except UnicodeDecodeError:
            #             if verbose:
            #                 print(f"[SKIP] {file_path.relative_to(extract_dir)}: could not decode")
            #             continue

            updated, changes = unwrap_toc_links_in_headings(
                original,
                str(file_path.relative_to(extract_dir)),
                verbose=verbose,
            )

            if changes > 0:
                total_changes += changes
                if not dry_run:
                    file_path.write_text(updated, encoding="utf-8")

        if dry_run:
            return total_changes

        # Rebuild EPUB. The mimetype file must be first and stored without compression.
        mimetype_file = extract_dir / "mimetype"
        with zipfile.ZipFile(output_path, "w") as zout:
            if mimetype_file.exists():
                zout.write(mimetype_file, "mimetype", compress_type=zipfile.ZIP_STORED)

            for file_path in sorted(extract_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(extract_dir).as_posix()
                if rel == "mimetype":
                    continue
                zout.write(file_path, rel, compress_type=zipfile.ZIP_DEFLATED)

    return total_changes


def build_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_fixed{input_path.suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix TOC links wrapped around chapter headings inside EPUB files.")
    parser.add_argument("input_epub", help="Path to the input EPUB file")
    parser.add_argument("-o", "--output", help="Path to the output EPUB file")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the input EPUB")
    parser.add_argument("--dry-run", action="store_true", help="Only report changes; do not write output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print each change")

    args = parser.parse_args()

    input_path = Path(args.input_epub)
    if not input_path.is_file():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    if input_path.suffix.lower() != ".epub":
        print(f"Warning: input does not have .epub extension: {input_path}", file=sys.stderr)

    if args.in_place and args.output:
        print("Error: use either --in-place or --output, not both.", file=sys.stderr)
        return 1

    if args.dry_run:
        output_path = input_path
    elif args.in_place:
        backup_path = input_path.with_name(f"{input_path.stem}.backup{input_path.suffix}")
        if not backup_path.exists():
            shutil.copy2(input_path, backup_path)
            print(f"Backup created: {backup_path}")
        else:
            print(f"Backup already exists: {backup_path}")
        output_path = input_path
    else:
        output_path = Path(args.output) if args.output else build_output_path(input_path)

    try:
        changes = process_epub(
            input_path=input_path,
            output_path=output_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    except zipfile.BadZipFile:
        print("Error: input file is not a valid EPUB/ZIP archive.", file=sys.stderr)
        return 1
    # except Exception as exc:
    #     print(f"Error: {exc}", file=sys.stderr)
    #     return 1
    except Exception:
        raise

    if args.dry_run:
        print(f"Dry run complete. Changes that would be made: {changes}")
    else:
        print(f"Done. Total heading links unwrapped: {changes}")
        print(f"Output: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())