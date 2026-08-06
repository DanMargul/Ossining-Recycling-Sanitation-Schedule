from datetime import date, datetime, timezone

import pytest
from icalendar import Calendar

from calendar_feed import (
    MAXIMUM_OCTETS_PER_LINE,
    escaped,
    event_uid,
    folded,
    vcalendar,
)
from ossining_calendar import Pickup, observed_holidays, year_pickups

GENERATED_AT = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
OFFICIAL_THROUGH = 2026


def feed(zone: int = 1, years: list[int] | None = None) -> str:
    return vcalendar(zone, years or [2026], GENERATED_AT, OFFICIAL_THROUGH)


def events_in(feed_text: str) -> list:
    return list(Calendar.from_ical(feed_text.encode("utf-8")).walk("VEVENT"))


def summaries_on(feed_text: str, day: date) -> list[str]:
    return [
        str(event["SUMMARY"])
        for event in events_in(feed_text)
        if event.decoded("DTSTART") == day
    ]


def test_every_collection_day_becomes_one_event():
    assert len(events_in(feed())) == len(year_pickups(2026, zone=1))


def test_events_are_all_day_and_do_not_mark_you_busy():
    first_event = events_in(feed())[0]
    assert first_event.decoded("DTSTART") == date(2026, 1, 2)
    assert first_event.decoded("DTEND") == date(2026, 1, 3)
    assert str(first_event["TRANSP"]) == "TRANSPARENT"


def test_reminder_fires_the_evening_before():
    alarm = events_in(feed())[0].walk("VALARM")[0]
    assert alarm.decoded("TRIGGER").total_seconds() == -6 * 60 * 60


def test_uids_are_unique_and_stable_across_regeneration():
    uids = [str(event["UID"]) for event in events_in(feed())]
    assert len(set(uids)) == len(uids)

    later_generation = vcalendar(
        1, [2026], datetime(2027, 1, 1, tzinfo=timezone.utc), OFFICIAL_THROUGH
    )
    assert [str(event["UID"]) for event in events_in(later_generation)] == uids


def test_uid_distinguishes_the_zones():
    assert event_uid(date(2026, 1, 2), 1) != event_uid(date(2026, 1, 2), 2)


def test_nothing_is_scheduled_on_a_holiday():
    scheduled = {event.decoded("DTSTART") for event in events_in(feed())}
    assert not scheduled & observed_holidays(2026)


def test_large_item_days_name_both_collections():
    assert summaries_on(feed(), date(2026, 1, 5)) == ["Garbage + Other Large Items"]


def test_recycling_days_name_the_stream():
    assert summaries_on(feed(), date(2026, 1, 7)) == ["Recycling: Paper"]
    assert summaries_on(feed(), date(2026, 1, 14)) == ["Recycling: Metal/Plastic/Glass"]


def test_zones_differ():
    assert summaries_on(feed(zone=1), date(2026, 1, 6)) != summaries_on(
        feed(zone=2), date(2026, 1, 6)
    )


def test_years_beyond_the_official_calendar_are_flagged():
    two_years = feed(years=[2026, 2027])
    descriptions = {
        event.decoded("DTSTART").year: str(event["DESCRIPTION"])
        for event in events_in(two_years)
    }
    assert "Projected" not in descriptions[2026]
    assert "Projected" in descriptions[2027]


def test_summary_covers_every_pickup():
    from calendar_feed import EVENT_SUMMARIES

    assert set(EVENT_SUMMARIES) == set(Pickup)


def test_special_characters_are_escaped():
    assert escaped("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"


@pytest.mark.parametrize(
    "line",
    [
        "SUMMARY:short",
        "DESCRIPTION:" + "x" * 200,
        "DESCRIPTION:" + "café " * 30,
        "DESCRIPTION:" + "\U0001f600" * 40,
    ],
)
def test_folding_respects_the_octet_limit_and_round_trips(line):
    lines = folded(line).split("\r\n")
    assert all(len(part.encode("utf-8")) <= MAXIMUM_OCTETS_PER_LINE for part in lines)
    assert all(part.startswith(" ") for part in lines[1:])
    assert lines[0] + "".join(part[1:] for part in lines[1:]) == line


def test_feed_uses_crlf_endings():
    text = feed()
    assert text.startswith("BEGIN:VCALENDAR\r\n")
    assert text.rstrip("\r\n").endswith("END:VCALENDAR")
    assert "\n" not in text.replace("\r\n", "")


def test_regenerating_unchanged_data_produces_identical_bytes():
    assert vcalendar(1, [2026], GENERATED_AT, OFFICIAL_THROUGH) == vcalendar(
        1, [2026], GENERATED_AT, OFFICIAL_THROUGH
    )


def test_the_generation_timestamp_does_not_depend_on_the_clock():
    from calendar_feed import stable_generation_timestamp

    assert stable_generation_timestamp([2026, 2027]) == stable_generation_timestamp(
        [2026, 2027]
    )
    assert stable_generation_timestamp([2026]) != stable_generation_timestamp([2027])
