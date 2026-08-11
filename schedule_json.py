"""Machine-readable collection schedule for the web page's current-week strip."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from ossining_calendar import ZONES, year_pickups

SCHEDULE_FILENAME = "schedule.json"


def schedule_document(years: list[int]) -> dict:
    zones = {}
    for zone in ZONES:
        collections = {}
        for year in years:
            for day, pickup in year_pickups(year, zone).items():
                collections[day.isoformat()] = pickup.name.lower()
        zones[str(zone)] = dict(sorted(collections.items()))
    return {"years": years, "zones": zones}


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    this_year = date.today().year
    parser = argparse.ArgumentParser(
        description="Write the collection schedule as JSON for the web page."
    )
    parser.add_argument("--start-year", type=int, default=this_year)
    parser.add_argument("--years", type=int, default=2)
    parser.add_argument("--out", type=Path, default=Path("."))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    arguments = parse_arguments(argv)
    arguments.out.mkdir(parents=True, exist_ok=True)
    years = [arguments.start_year + offset for offset in range(arguments.years)]

    destination = arguments.out / SCHEDULE_FILENAME
    destination.write_text(
        json.dumps(schedule_document(years), separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {destination}")


if __name__ == "__main__":
    main()
