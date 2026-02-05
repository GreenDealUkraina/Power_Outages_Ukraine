#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Dict, List, Tuple


RAW_DATE_FMT = "%d.%m.%Y"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean outage survey data and aggregate to oblast-day averages."
    )
    parser.add_argument(
        "--raw",
        default="data/Raw_survey_data.csv",
        help="Path to raw survey CSV.",
    )
    parser.add_argument(
        "--regions",
        default="data/region_IDs.csv",
        help="Path to region ID mapping CSV.",
    )
    parser.add_argument(
        "--out",
        default="data/clean_outages.csv",
        help="Output path for cleaned CSV.",
    )
    parser.add_argument(
        "--start-date",
        default="31.01.2026",
        help="Earliest reporting date to include (dd.mm.yyyy).",
    )
    return parser.parse_args()


def parse_float(value: str) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def load_region_ids(path: Path) -> Dict[str, str]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        mapping = {}
        for row in reader:
            oblast = row.get("What Oblast are you reporting from?", "").strip()
            gid = row.get("GID_1", "").strip()
            if oblast:
                mapping[oblast] = gid
        return mapping


def load_raw_data(
    path: Path,
    start_date: datetime,
) -> Dict[Tuple[str, str], Dict[str, object]]:
    data: Dict[Tuple[str, str], Dict[str, object]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_date = (row.get("What date are you reporting for?") or "").strip()
            oblast = (row.get("What Oblast are you reporting from?") or "").strip()
            if not raw_date or not oblast:
                continue
            try:
                date_obj = datetime.strptime(raw_date, RAW_DATE_FMT)
            except ValueError:
                continue
            if date_obj < start_date:
                continue

            subqueue = (row.get("What sub-queue are you reporting from?") or "").strip()
            scheduled = parse_float(
                row.get(
                    "How many hours of scheduled outages were planned for today in your sub-queue?",
                    "",
                )
            )
            actual = parse_float(
                row.get(
                    "How many hours of actual outages occurred today in your sub-queue?",
                    "",
                )
            )

            key = (date_obj.strftime(RAW_DATE_FMT), oblast)
            data.setdefault(key, {"scheduled": [], "actual": [], "subqueues": set()})
            if scheduled is not None:
                data[key]["scheduled"].append(scheduled)
            if actual is not None:
                data[key]["actual"].append(actual)
            if subqueue:
                data[key]["subqueues"].add(subqueue)
    return data


def main() -> None:
    args = parse_args()
    raw_path = Path(args.raw)
    regions_path = Path(args.regions)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    start_date = datetime.strptime(args.start_date, RAW_DATE_FMT)

    region_ids = load_region_ids(regions_path)
    aggregated = load_raw_data(raw_path, start_date)

    date_strings = {d for (d, _) in aggregated.keys()}
    dates = sorted(
        date_strings, key=lambda d: datetime.strptime(d, RAW_DATE_FMT)
    )
    oblasts = sorted(region_ids.keys())

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Date",
                "Oblast",
                "GID_1",
                "Scheduled_outages",
                "Actual_outages",
                "Subqueues",
            ]
        )
        for date in dates:
            for oblast in oblasts:
                values = aggregated.get(
                    (date, oblast), {"scheduled": [], "actual": [], "subqueues": set()}
                )
                scheduled_avg = (
                    mean(values["scheduled"]) if values["scheduled"] else ""
                )
                actual_avg = mean(values["actual"]) if values["actual"] else ""
                subqueues = sorted(values["subqueues"])
                subqueue_text = ", ".join(subqueues)
                writer.writerow(
                    [
                        date,
                        oblast,
                        region_ids.get(oblast, ""),
                        scheduled_avg,
                        actual_avg,
                        subqueue_text,
                    ]
                )


if __name__ == "__main__":
    main()
