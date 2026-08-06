"""Fetch published feeds and fail loudly if a subscriber would get nothing usable."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from datetime import date

from icalendar import Calendar

from calendar_feed import FEED_FILENAME_TEMPLATE
from ossining_calendar import ZONES

EXPECTED_CONTENT_TYPE = "text/calendar"
MINIMUM_EVENTS = 100
FETCH_TIMEOUT_SECONDS = 30
USER_AGENT = "ossining-calendar-feed-check"


class FeedProblem(Exception):
    pass


def fetch(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        raise FeedProblem(f"HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise FeedProblem(f"unreachable: {error.reason}") from error


def events_in(body: bytes) -> list:
    try:
        return list(Calendar.from_ical(body).walk("VEVENT"))
    except ValueError as error:
        raise FeedProblem(f"does not parse as iCalendar: {error}") from error


def check_feed(url: str, today: date) -> list[str]:
    body, content_type = fetch(url)
    warnings = []

    if not content_type.startswith(EXPECTED_CONTENT_TYPE):
        warnings.append(f"served as {content_type or 'no Content-Type'}")

    events = events_in(body)
    if len(events) < MINIMUM_EVENTS:
        raise FeedProblem(f"only {len(events)} events")

    collection_days = sorted(event.decoded("DTSTART") for event in events)
    if collection_days[-1] < today:
        raise FeedProblem(f"last collection day was {collection_days[-1]}")

    upcoming = [day for day in collection_days if day >= today]
    if not upcoming:
        raise FeedProblem("no upcoming collection days")

    print(
        f"  {len(events)} events, "
        f"{len(upcoming)} upcoming, next {upcoming[0]}, last {collection_days[-1]}"
    )
    return warnings


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that published feeds are reachable and usable."
    )
    parser.add_argument("base_url")
    parser.add_argument(
        "--zone", type=int, choices=ZONES, action="append", dest="zones"
    )
    parser.add_argument("--warnings-are-failures", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    base_url = arguments.base_url.rstrip("/")
    today = date.today()

    failures = 0
    warnings = 0
    for zone in arguments.zones or ZONES:
        url = f"{base_url}/{FEED_FILENAME_TEMPLATE.format(zone=zone)}"
        print(f"checking {url}")
        try:
            for warning in check_feed(url, today):
                print(f"  WARNING: {warning}")
                warnings += 1
        except FeedProblem as problem:
            print(f"  FAILED: {problem}")
            failures += 1

    if failures:
        return 1
    if warnings and arguments.warnings_are_failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
