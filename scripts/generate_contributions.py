#!/usr/bin/env python3
"""Generate light and dark GitHub contribution calendars for the profile README."""

from __future__ import annotations

import argparse
import html
import json
import subprocess
from datetime import date
from pathlib import Path


CELL = 10
GAP = 2
GRID_X = 192
WIDTH = 920
ROW_HEIGHT = 108
HEADER_HEIGHT = 70
FOOTER_HEIGHT = 40

PALETTES = {
    "light": {
        "background": "#ffffff",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#636c76",
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
    },
    "dark": {
        "background": "#0d1117",
        "border": "#30363d",
        "text": "#f0f6fc",
        "muted": "#8b949e",
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    },
}

LEVEL_INDEX = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="xerrors")
    parser.add_argument("--years", nargs="+", type=int, default=[2025, 2026])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets",
    )
    return parser.parse_args()


def fetch_calendars(user: str, years: list[int]) -> dict[int, dict]:
    today = date.today()
    fields = []
    included_years = [year for year in years if year <= today.year]
    for year in included_years:
        end = today if year == today.year else date(year, 12, 31)
        fields.append(
            f'''y{year}: contributionsCollection(
              from: "{year}-01-01T00:00:00Z"
              to: "{end.isoformat()}T23:59:59Z"
            ) {{
              contributionCalendar {{
                totalContributions
                weeks {{
                  contributionDays {{
                    date
                    contributionCount
                    contributionLevel
                    weekday
                  }}
                }}
              }}
            }}'''
        )

    query = "query($login: String!) { user(login: $login) { " + " ".join(fields) + " } }"
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}", "-F", f"login={user}"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return {
        year: payload["data"]["user"][f"y{year}"]["contributionCalendar"]
        for year in included_years
    }


def month_labels(weeks: list[dict]) -> list[tuple[int, str]]:
    labels = []
    seen = set()
    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            current = date.fromisoformat(day["date"])
            if current.month not in seen and current.day <= 7:
                seen.add(current.month)
                labels.append((week_index, current.strftime("%b")))
    return labels


def svg_for_theme(
    user: str,
    calendars: dict[int, dict],
    theme: str,
    generated_on: date,
) -> str:
    palette = PALETTES[theme]
    years = sorted(calendars)
    height = HEADER_HEIGHT + ROW_HEIGHT * len(years) + FOOTER_HEIGHT
    title = f"{user} 的 GitHub 贡献记录"
    year_range = f"{years[0]}–{years[-1]}"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(title)} · {year_range}</title>',
        f'<desc id="desc">{year_range} 年 GitHub 贡献记录，生成于 {generated_on.isoformat()}。</desc>',
        "<style>",
        "text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }",
        ".heading { font-size: 18px; font-weight: 650; }",
        ".subheading { font-size: 12px; }",
        ".year { font-size: 16px; font-weight: 650; }",
        ".total { font-size: 12px; }",
        ".month { font-size: 10px; }",
        "</style>",
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="12" fill="{palette["background"]}" stroke="{palette["border"]}" />',
        f'<text x="28" y="30" class="heading" fill="{palette["text"]}">GitHub 贡献记录 · {year_range}</text>',
        f'<text x="28" y="51" class="subheading" fill="{palette["muted"]}">基于 GitHub GraphQL 生成 · {generated_on.isoformat()}</text>',
    ]

    for row_index, year in enumerate(years):
        calendar = calendars[year]
        weeks = calendar["weeks"]
        row_top = HEADER_HEIGHT + row_index * ROW_HEIGHT
        grid_y = row_top + 26
        parts.extend(
            [
                f'<text x="28" y="{row_top + 32}" class="year" fill="{palette["text"]}">{year}</text>',
                f'<text x="28" y="{row_top + 52}" class="total" fill="{palette["muted"]}">{calendar["totalContributions"]:,} 次贡献</text>',
            ]
        )

        for week_index, label in month_labels(weeks):
            x = GRID_X + week_index * (CELL + GAP)
            parts.append(
                f'<text x="{x}" y="{row_top + 16}" class="month" fill="{palette["muted"]}">{label}</text>'
            )

        for week_index, week in enumerate(weeks):
            for day in week["contributionDays"]:
                x = GRID_X + week_index * (CELL + GAP)
                y = grid_y + day["weekday"] * (CELL + GAP)
                level = LEVEL_INDEX[day["contributionLevel"]]
                tooltip = f'{day["contributionCount"]} contributions on {day["date"]}'
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{palette["levels"][level]}"><title>{tooltip}</title></rect>'
                )

    legend_y = height - 18
    legend_x = WIDTH - 174
    parts.append(
        f'<text x="{legend_x - 20}" y="{legend_y}" class="month" fill="{palette["muted"]}">少</text>'
    )
    for index, color in enumerate(palette["levels"]):
        x = legend_x + index * (CELL + GAP)
        parts.append(
            f'<rect x="{x}" y="{legend_y - CELL}" width="{CELL}" height="{CELL}" rx="2" fill="{color}" />'
        )
    parts.append(
        f'<text x="{legend_x + 67}" y="{legend_y}" class="month" fill="{palette["muted"]}">多</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    args = parse_args()
    calendars = fetch_calendars(args.user, args.years)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    generated_on = date.today()
    for theme in PALETTES:
        output = args.output_dir / f"contributions-{theme}.svg"
        output.write_text(
            svg_for_theme(args.user, calendars, theme, generated_on),
            encoding="utf-8",
        )
        print(output)


if __name__ == "__main__":
    main()
