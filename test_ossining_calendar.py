import calendar
from datetime import date
from itertools import pairwise

import pytest

from ossining_calendar import (
    Month,
    Pickup,
    observed_holidays,
    week_pickups,
    year_pickups,
)

OFF = None
GARBAGE = Pickup.GARBAGE
PAPER = Pickup.PAPER
COMINGLED = Pickup.METAL_PLASTIC_GLASS
YARD = Pickup.YARD_WASTE
LARGE_METAL = Pickup.LARGE_METAL_AND_ELECTRONICS
LARGE_OTHER = Pickup.OTHER_LARGE_ITEMS

NO_HOLIDAYS = frozenset()
A_FULL_WEEK_IN_JUNE = [8, 9, 10, 11, 12]
THE_FOLLOWING_WEEK = [15, 16, 17, 18, 19]


def june_2026() -> Month:
    return Month(6, 2026)


def days_in_grid(month: Month) -> list[int]:
    return sorted(day for week in month.weeks for day in week if day)


def june_holidays(*days: int) -> frozenset[date]:
    return frozenset(date(2026, 6, day) for day in days)


def test_zone_1_normal_week():
    week = week_pickups(june_2026(), A_FULL_WEEK_IN_JUNE, 1, NO_HOLIDAYS)
    assert week == [LARGE_OTHER, YARD, PAPER, LARGE_METAL, OFF]


def test_zone_2_normal_week():
    week = week_pickups(june_2026(), A_FULL_WEEK_IN_JUNE, 2, NO_HOLIDAYS)
    assert week == [YARD, LARGE_OTHER, PAPER, OFF, LARGE_METAL]


def test_days_outside_the_month_get_no_pickup():
    january = Month(1, 2026)
    assert january.weeks[0] == [0, 0, 0, 1, 2]

    opening_week = week_pickups(january, january.weeks[0], 1, NO_HOLIDAYS)
    assert opening_week[:3] == [OFF, OFF, OFF]


def test_recycling_alternates_every_wednesday():
    schedule = year_pickups(2026, zone=1)
    wednesdays = sorted(day for day in schedule if day.weekday() == calendar.WEDNESDAY)
    streams = [schedule[wednesday] for wednesday in wednesdays]

    assert streams[0] == PAPER
    assert all(earlier != later for earlier, later in pairwise(streams))


def test_alternation_continues_across_month_boundaries():
    schedule = year_pickups(2026, zone=1)
    assert schedule[date(2026, 6, 24)] != schedule[date(2026, 7, 1)]
    assert schedule[date(2026, 9, 30)] != schedule[date(2026, 10, 7)]


@pytest.mark.parametrize(
    "closed_column, expected",
    [
        (0, [OFF, GARBAGE, YARD, COMINGLED, GARBAGE]),
        (1, [GARBAGE, OFF, YARD, COMINGLED, GARBAGE]),
        (2, [GARBAGE, YARD, OFF, COMINGLED, GARBAGE]),
        (3, [GARBAGE, YARD, COMINGLED, OFF, GARBAGE]),
        (4, [GARBAGE, YARD, COMINGLED, GARBAGE, OFF]),
    ],
)
def test_a_holiday_slides_the_week_into_the_remaining_days(closed_column, expected):
    holiday = june_holidays(THE_FOLLOWING_WEEK[closed_column])
    assert week_pickups(june_2026(), THE_FOLLOWING_WEEK, 1, holiday) == expected


def test_large_items_are_not_collected_during_a_holiday_week():
    shortened = week_pickups(june_2026(), THE_FOLLOWING_WEEK, 1, june_holidays(15))
    assert LARGE_METAL not in shortened
    assert LARGE_OTHER not in shortened


def test_two_holidays_in_one_week_drop_the_last_two_collections():
    week = week_pickups(june_2026(), THE_FOLLOWING_WEEK, 1, june_holidays(15, 16))
    assert week == [OFF, OFF, GARBAGE, YARD, COMINGLED]


def test_new_years_day_2026_falls_in_a_two_day_opening_week():
    january = Month(1, 2026)
    opening_week = week_pickups(january, january.weeks[0], 1, observed_holidays(2026))
    assert opening_week == [OFF, OFF, OFF, OFF, GARBAGE]


@pytest.mark.parametrize("zone", [1, 2])
def test_nothing_is_collected_on_a_holiday(zone):
    assert not set(year_pickups(2026, zone)) & observed_holidays(2026)


def test_observed_holidays_2026():
    assert observed_holidays(2026) == {
        date(2026, 1, 1),
        date(2026, 5, 25),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 11, 26),
        date(2026, 12, 25),
    }


def test_weekend_holidays_move_to_the_nearest_weekday():
    holidays_2021 = observed_holidays(2021)
    assert date(2021, 7, 5) in holidays_2021
    assert date(2021, 12, 24) in holidays_2021
    assert date(2021, 12, 31) in holidays_2021


def test_february_length_follows_the_leap_year():
    assert days_in_grid(Month(2, 2028))[-1] == 29
    assert 29 not in days_in_grid(Month(2, 2026))


@pytest.mark.parametrize("year", [2026, 2027, 2028])
def test_grid_holds_every_weekday_and_nothing_else(year):
    for index in range(1, 13):
        days_in_month = calendar.monthrange(year, index)[1]
        weekdays = [
            day
            for day in range(1, days_in_month + 1)
            if date(year, index, day).weekday() < 5
        ]
        assert days_in_grid(Month(index, year)) == weekdays
