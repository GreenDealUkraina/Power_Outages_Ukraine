#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the outage dashboard HTML from a template and YAML config."
    )
    parser.add_argument(
        "--template",
        default="templates/template.html",
        help="Path to HTML template.",
    )
    parser.add_argument(
        "--yaml",
        default="templates/dashboard.yaml",
        help="Path to dashboard YAML config.",
    )
    parser.add_argument(
        "--out",
        default="docs/index.html",
        help="Output HTML path.",
    )
    return parser.parse_args()


def join_lines(items: List[str]) -> str:
    return "<br>".join([item.strip() for item in items if item.strip()])


def normalize_authors(authors: List[Any]) -> List[Tuple[str, str]]:
    normalized: List[Tuple[str, str]] = []
    for item in authors:
        if isinstance(item, str):
            if item.strip():
                normalized.append((item.strip(), ""))
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            linkedin = str(item.get("linkedin", "")).strip()
            if name:
                normalized.append((name, linkedin))
    return normalized


def build_logos(logo_entries: List[Any]) -> str:
    rendered = []
    for entry in logo_entries:
        if isinstance(entry, str):
            rendered.append(f'<img src="{entry}" alt="Logo">')
            continue
        if isinstance(entry, dict):
            path = str(entry.get("file", "")).strip()
            url = str(entry.get("url", "")).strip()
            if not path:
                continue
            if url:
                rendered.append(
                    f'<a href="{url}" target="_blank" rel="noopener">'
                    f'<img src="{path}" alt="Logo"></a>'
                )
            else:
                rendered.append(f'<img src="{path}" alt="Logo">')
    return "\n".join(rendered)


def build_authors(authors: List[Tuple[str, str]]) -> str:
    rendered = []
    for name, link in authors:
        if link:
            rendered.append(
                f'<a href="{link}" target="_blank" rel="noopener">{name}</a>'
            )
        else:
            rendered.append(name)
    names = " &amp; ".join(rendered)
    return f"Prepared by the Data &amp; Modelling team from Green Deal Ukra\u00efna: {names}"


def build_insights_list(items: List[str]) -> str:
    return "\n".join([f"<li>{item}</li>" for item in items])


def main() -> None:
    args = parse_args()
    template_path = Path(args.template)
    yaml_path = Path(args.yaml)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    template = template_path.read_text(encoding="utf-8")
    config: Dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

    # Copy logos into docs so GitHub Pages can serve them.
    logo_entries = config.get("logos", [])
    docs_root = out_path.parent
    docs_logos = docs_root / "logos"
    docs_logos.mkdir(parents=True, exist_ok=True)
    normalized_entries = []
    for entry in logo_entries:
        if isinstance(entry, str):
            src = Path(entry)
            if src.exists():
                shutil.copy2(src, docs_logos / src.name)
            normalized_entries.append(f"logos/{src.name}")
            continue
        if isinstance(entry, dict):
            path = str(entry.get("file", "")).strip()
            url = str(entry.get("url", "")).strip()
            src = Path(path)
            if src.exists():
                shutil.copy2(src, docs_logos / src.name)
            normalized_entries.append({"file": f"logos/{src.name}", "url": url})
    config["logos"] = normalized_entries

    title = config.get("title", "")
    description = config.get("description", "")
    authors = build_authors(normalize_authors(config.get("authors", [])))
    contact = config.get("contact", "") or config.get("email contact", "")
    logos = build_logos(config.get("logos", []))
    citation = config.get("citation", "")
    license_text = config.get("license", "")

    header_link = config.get("header_link", {})
    link_prefix = header_link.get(
        "prefix",
        "Check out our other dashboard that focuses more generally on the",
    ).strip()
    link_text = header_link.get("text", "").strip()
    link_url = header_link.get("url", "").strip()
    header_link_html = ""
    if link_text and link_url:
        header_link_html = (
            f"{link_prefix} "
            f'<a href="{link_url}" target="_blank" rel="noopener">{link_text}</a>.'
        )

    purpose = config.get("purpose", {})
    purpose_title = purpose.get("heading", "Purpose")
    purpose_text = purpose.get("text", "")

    about = config.get("about", {})
    about_title = about.get("heading", "About the project")
    about_text = about.get("text", "")

    insights = config.get("key_insights", {})
    insights_enabled = bool(insights.get("enabled", True))
    insights_title = insights.get("heading", "Key insights")
    insights_list = build_insights_list(insights.get("bullets", []))
    insights_section = ""
    if insights_enabled:
        insights_section = (
            "<section class=\"summary collapsible\">"
            "<button class=\"collapsible-toggle\" type=\"button\" aria-expanded=\"false\">"
            "<span class=\"arrow\">▸</span>"
            f"<span>{insights_title}</span>"
            "</button>"
            "<div class=\"collapsible-content\">"
            f"<ul>{insights_list}</ul>"
            "</div>"
            "</section>"
        )

    maps = config.get("maps", {}).get("combined", {})
    maps_title = maps.get("title", "Outage maps")
    maps_file = maps.get("file", "")

    html = (
        template.replace("{{TITLE}}", title)
        .replace("{{DESCRIPTION}}", description)
        .replace("{{AUTHORS}}", authors)
        .replace("{{CONTACT}}", contact)
        .replace("{{LOGOS}}", logos)
        .replace("{{INSIGHTS_TITLE}}", insights_title)
        .replace("{{INSIGHTS_LIST}}", insights_list)
        .replace("{{INSIGHTS_SECTION}}", insights_section)
        .replace("{{PURPOSE_TITLE}}", purpose_title)
        .replace("{{PURPOSE_TEXT}}", purpose_text)
        .replace("{{ABOUT_TITLE}}", about_title)
        .replace("{{ABOUT_TEXT}}", about_text)
        .replace("{{CITATION_TEXT}}", citation)
        .replace("{{LICENSE_TEXT}}", license_text)
        .replace("{{HEADER_LINK}}", header_link_html)
        .replace("{{MAPS_TITLE}}", maps_title)
        .replace("{{MAPS_FILE}}", maps_file)
    )

    out_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
