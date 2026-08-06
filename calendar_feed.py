"""iCalendar feed of Ossining collection days, for phone calendar subscriptions."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ossining_calendar import ZONES, Pickup, year_pickups

PRODUCT_IDENTIFIER = "-//Village of Ossining//Sanitation Calendar//EN"
UID_DOMAIN = "sanitation.ossiningny.gov"
LOCAL_TIMEZONE_NAME = "America/New_York"
REFRESH_INTERVAL = "P7D"
REMINDER_BEFORE_COLLECTION_DAY = "-PT6H"
MAXIMUM_OCTETS_PER_LINE = 75
LAST_YEAR_CHECKED_AGAINST_PRINTED_CALENDAR = 2026
FEED_FILENAME_TEMPLATE = "zone-{zone}.ics"
LINE_ENDING = "\r\n"
CONTINUATION_PREFIX = " "

EVENT_SUMMARIES = {
    Pickup.GARBAGE: "Garbage",
    Pickup.PAPER: "Recycling: Paper",
    Pickup.METAL_PLASTIC_GLASS: "Recycling: Metal/Plastic/Glass",
    Pickup.YARD_WASTE: "Yard Waste",
    Pickup.LARGE_METAL_AND_ELECTRONICS: "Garbage + Large Metal/Electronics",
    Pickup.OTHER_LARGE_ITEMS: "Garbage + Other Large Items",
}

PUT_OUT_INSTRUCTIONS = (
    "Out by 6:00 AM. Not before 5:00 PM the day before. Wrong-day items may be fined."
)

UNOFFICIAL_YEAR_WARNING = (
    "Projected from the collection rules; confirm against the Village "
    "calendar when it is published."
)


def escaped(text: str) -> str:
    for character, replacement in (
        ("\\", "\\\\"),
        (";", "\\;"),
        (",", "\\,"),
        ("\n", "\\n"),
    ):
        text = text.replace(character, replacement)
    return text


def split_at_octet_boundary(octets: bytes, limit: int) -> tuple[str, bytes]:
    chunk = octets[:limit]
    while chunk:
        try:
            return chunk.decode("utf-8"), octets[len(chunk) :]
        except UnicodeDecodeError:
            chunk = chunk[:-1]
    return "", octets


def folded(line: str) -> str:
    octets = line.encode("utf-8")
    if len(octets) <= MAXIMUM_OCTETS_PER_LINE:
        return line

    first_chunk, remaining = split_at_octet_boundary(octets, MAXIMUM_OCTETS_PER_LINE)
    chunks = [first_chunk]

    continuation_limit = MAXIMUM_OCTETS_PER_LINE - len(CONTINUATION_PREFIX)
    while remaining:
        chunk, remaining = split_at_octet_boundary(remaining, continuation_limit)
        chunks.append(CONTINUATION_PREFIX + chunk)
    return LINE_ENDING.join(chunks)


def as_ics_date(day: date) -> str:
    return day.strftime("%Y%m%d")


def as_ics_timestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def stable_generation_timestamp(years: list[int]) -> datetime:
    return datetime(min(years), 1, 1, tzinfo=timezone.utc)


def event_uid(day: date, zone: int) -> str:
    return f"{as_ics_date(day)}-zone{zone}@{UID_DOMAIN}"


def event_description(day: date, official_through_year: int) -> str:
    if day.year <= official_through_year:
        return PUT_OUT_INSTRUCTIONS
    return f"{PUT_OUT_INSTRUCTIONS}\n\n{UNOFFICIAL_YEAR_WARNING}"


def vevent(
    day: date,
    pickup: Pickup,
    zone: int,
    generated_at: datetime,
    official_through_year: int,
) -> list[str]:
    summary = EVENT_SUMMARIES[pickup]
    return [
        "BEGIN:VEVENT",
        f"UID:{event_uid(day, zone)}",
        f"DTSTAMP:{as_ics_timestamp(generated_at)}",
        f"DTSTART;VALUE=DATE:{as_ics_date(day)}",
        f"DTEND;VALUE=DATE:{as_ics_date(day + timedelta(days=1))}",
        f"SUMMARY:{escaped(summary)}",
        f"DESCRIPTION:{escaped(event_description(day, official_through_year))}",
        "TRANSP:TRANSPARENT",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"TRIGGER:{REMINDER_BEFORE_COLLECTION_DAY}",
        f"DESCRIPTION:{escaped(f'Put out tonight: {summary}')}",
        "END:VALARM",
        "END:VEVENT",
    ]


def vcalendar(
    zone: int,
    years: list[int],
    generated_at: datetime,
    official_through_year: int,
) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODUCT_IDENTIFIER}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escaped(f'Ossining Sanitation - Zone {zone}')}",
        f"X-WR-TIMEZONE:{LOCAL_TIMEZONE_NAME}",
        f"REFRESH-INTERVAL;VALUE=DURATION:{REFRESH_INTERVAL}",
        f"X-PUBLISHED-TTL:{REFRESH_INTERVAL}",
    ]
    for year in years:
        schedule = year_pickups(year, zone)
        for day in sorted(schedule):
            lines.extend(
                vevent(day, schedule[day], zone, generated_at, official_through_year)
            )
    lines.append("END:VCALENDAR")

    return LINE_ENDING.join(folded(line) for line in lines) + LINE_ENDING


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    this_year = date.today().year
    parser = argparse.ArgumentParser(
        description="Generate subscribable iCalendar feeds of collection days."
    )
    parser.add_argument("--start-year", type=int, default=this_year)
    parser.add_argument("--years", type=int, default=2)
    parser.add_argument(
        "--official-through-year",
        type=int,
        default=LAST_YEAR_CHECKED_AGAINST_PRINTED_CALENDAR,
    )
    parser.add_argument(
        "--zone", type=int, choices=ZONES, action="append", dest="zones"
    )
    parser.add_argument("--out", type=Path, default=Path("."))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    arguments = parse_arguments(argv)
    arguments.out.mkdir(parents=True, exist_ok=True)
    years = [arguments.start_year + offset for offset in range(arguments.years)]
    generated_at = stable_generation_timestamp(years)

    for zone in arguments.zones or ZONES:
        destination = arguments.out / FEED_FILENAME_TEMPLATE.format(zone=zone)
        destination.write_text(
            vcalendar(zone, years, generated_at, arguments.official_through_year),
            encoding="utf-8",
            newline="",
        )
        print(f"wrote {destination}")


if __name__ == "__main__":
    main()
