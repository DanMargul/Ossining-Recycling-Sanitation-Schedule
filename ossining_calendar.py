"""Village of Ossining sanitation and recycling calendar."""

from __future__ import annotations

import argparse
import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from xml.sax.saxutils import escape

WEEKDAYS_PER_ROW = 5
WEEK_ROWS_PER_MONTH = 5
MONTHS_PER_YEAR = 12
WEDNESDAY = 2


class Pickup(Enum):
    GARBAGE = "Garbage"
    PAPER = "Paper"
    METAL_PLASTIC_GLASS = "Metal/Plastic/Glass"
    YARD_WASTE = "Yard Waste"
    LARGE_METAL_AND_ELECTRONICS = "Large Metal/Electronics"
    OTHER_LARGE_ITEMS = "Other Large Items"


LARGE_ITEM_PICKUPS = (Pickup.LARGE_METAL_AND_ELECTRONICS, Pickup.OTHER_LARGE_ITEMS)

RECYCLING_GOES_HERE = None

NORMAL_WEEK_BY_ZONE: dict[int, list[Pickup | None]] = {
    1: [
        Pickup.OTHER_LARGE_ITEMS,
        Pickup.YARD_WASTE,
        RECYCLING_GOES_HERE,
        Pickup.LARGE_METAL_AND_ELECTRONICS,
        None,
    ],
    2: [
        Pickup.YARD_WASTE,
        Pickup.OTHER_LARGE_ITEMS,
        RECYCLING_GOES_HERE,
        None,
        Pickup.LARGE_METAL_AND_ELECTRONICS,
    ],
}

ZONES = tuple(sorted(NORMAL_WEEK_BY_ZONE))

FIRST_PAPER_WEDNESDAY = date(2026, 1, 7)


@dataclass
class Month:
    index: int
    year: int
    weeks: list[list[int]] = field(init=False)

    def __post_init__(self) -> None:
        weeks_including_weekends = calendar.Calendar(
            firstweekday=calendar.MONDAY
        ).monthdayscalendar(self.year, self.index)
        self.weeks = [
            week[:WEEKDAYS_PER_ROW]
            for week in weeks_including_weekends
            if any(week[:WEEKDAYS_PER_ROW])
        ]

    @property
    def name(self) -> str:
        return calendar.month_name[self.index]

    def date_of(self, day: int) -> date:
        return date(self.year, self.index, day)


def months(year: int) -> list[Month]:
    return [Month(index, year) for index in range(1, MONTHS_PER_YEAR + 1)]


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    matching_days = [
        week[weekday] for week in calendar.monthcalendar(year, month) if week[weekday]
    ]
    return date(year, month, matching_days[n - 1])


def last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    matching_days = [
        week[weekday] for week in calendar.monthcalendar(year, month) if week[weekday]
    ]
    return date(year, month, matching_days[-1])


def moved_off_weekend(holiday: date) -> date:
    if holiday.weekday() == calendar.SATURDAY:
        return holiday - timedelta(days=1)
    if holiday.weekday() == calendar.SUNDAY:
        return holiday + timedelta(days=1)
    return holiday


def observed_holidays(year: int) -> frozenset[date]:
    new_years_day = moved_off_weekend(date(year, 1, 1))
    memorial_day = last_weekday_of_month(year, 5, calendar.MONDAY)
    independence_day = moved_off_weekend(date(year, 7, 4))
    labor_day = nth_weekday_of_month(year, 9, calendar.MONDAY, 1)
    thanksgiving = nth_weekday_of_month(year, 11, calendar.THURSDAY, 4)
    christmas = moved_off_weekend(date(year, 12, 25))
    next_new_years_day = moved_off_weekend(date(year + 1, 1, 1))

    return frozenset(
        holiday
        for holiday in (
            new_years_day,
            memorial_day,
            independence_day,
            labor_day,
            thanksgiving,
            christmas,
            next_new_years_day,
        )
        if holiday.year == year
    )


def recycling_stream(wednesday: date) -> Pickup:
    weeks_since_first_paper = (wednesday - FIRST_PAPER_WEDNESDAY).days // 7
    if weeks_since_first_paper % 2 == 0:
        return Pickup.PAPER
    return Pickup.METAL_PLASTIC_GLASS


def wednesday_of_row(month: Month, row: list[int]) -> date:
    column, day = next((i, day) for i, day in enumerate(row) if day)
    return month.date_of(day) + timedelta(days=WEDNESDAY - column)


def without_large_items(pickup: Pickup | None) -> Pickup | None:
    if pickup in LARGE_ITEM_PICKUPS:
        return Pickup.GARBAGE
    return pickup


def week_pickups(
    month: Month,
    row: list[int],
    zone: int,
    holidays: frozenset[date],
) -> list[Pickup | None]:
    normal_week = list(NORMAL_WEEK_BY_ZONE[zone])
    normal_week[WEDNESDAY] = recycling_stream(wednesday_of_row(month, row))

    closed_days = [bool(day) and month.date_of(day) in holidays for day in row]
    if not any(closed_days):
        return [pickup if day else None for pickup, day in zip(normal_week, row)]

    pending = [
        without_large_items(pickup)
        for pickup, day in zip(normal_week, row)
        if day and pickup is not None
    ]
    working_days = [
        column for column, day in enumerate(row) if day and not closed_days[column]
    ]

    shifted: list[Pickup | None] = [None] * WEEKDAYS_PER_ROW
    for column, pickup in zip(working_days, pending):
        shifted[column] = pickup
    return shifted


def month_pickups(
    month: Month, zone: int, holidays: frozenset[date]
) -> list[list[Pickup | None]]:
    return [week_pickups(month, row, zone, holidays) for row in month.weeks]


def year_pickups(year: int, zone: int) -> dict[date, Pickup]:
    holidays = observed_holidays(year)
    schedule = {}
    for month in months(year):
        for row, pickups in zip(month.weeks, month_pickups(month, zone, holidays)):
            for day, pickup in zip(row, pickups):
                if day and pickup is not None:
                    schedule[month.date_of(day)] = pickup
    return schedule


BLACK = "rgb(0,0,0)"
WHITE = "rgb(255,255,255)"
RED = "rgb(255,0,0)"
NO_FILL = "none"

FILL_COLORS = {
    Pickup.GARBAGE: "rgb(170,170,170)",
    Pickup.PAPER: "rgb(50,180,50)",
    Pickup.METAL_PLASTIC_GLASS: "rgb(30,120,255)",
    Pickup.YARD_WASTE: "rgb(176,101,0)",
    Pickup.LARGE_METAL_AND_ELECTRONICS: "rgb(170,170,170)",
    Pickup.OTHER_LARGE_ITEMS: "rgb(170,170,170)",
}

CORNER_FLAG_COLORS = {
    Pickup.LARGE_METAL_AND_ELECTRONICS: "rgb(255,105,180)",
    Pickup.OTHER_LARGE_ITEMS: "rgb(255,255,0)",
}

LEGEND_ROWS = [
    [Pickup.YARD_WASTE, Pickup.GARBAGE, Pickup.PAPER, Pickup.METAL_PLASTIC_GLASS],
    [Pickup.LARGE_METAL_AND_ELECTRONICS, Pickup.OTHER_LARGE_ITEMS],
]

DAY_OF_WEEK_LABELS = ("M", "T", "W", "Th", "F")

HEADING = "Village of Ossining"
WARNING = (
    "Items put out on the wrong day are subject to fines from the "
    "Building Department. Please use your calendar."
)
NOTICE = (
    "PLEASE NOTE: All collections must be out by 6:00 AM on the day of "
    "collection and no earlier than 5:00 PM the day prior."
)

PAGE_WIDTH = 850
PAGE_HEIGHT = 1100
PAGE_CENTER_X = PAGE_WIDTH // 2
BORDER_WIDTH = 2
SERIF_WIDTH_PER_POINT = 0.52

HEADING_Y = 40
HEADING_FONT_SIZE = 25
TITLE_Y = 75
TITLE_FONT_SIZE = 30

LEGEND_TOP_Y = 100
LEGEND_ROW_SPACING = 40
LEGEND_BOX_HEIGHT = 30
LEGEND_BOX_GAP = 10
LEGEND_BOX_PADDING = 10
LEGEND_LABEL_BASELINE = 22
LEGEND_FONT_SIZE = 20

GRID_LEFT = 10
GRID_TOP = 245
GRID_COLUMNS = 4
MONTH_BOX_SPACING_X = 210
MONTH_BOX_SPACING_Y = 285

DAY_BOX_WIDTH = 40
DAY_BOX_HEIGHT = 44
MONTH_BOX_WIDTH = DAY_BOX_WIDTH * WEEKDAYS_PER_ROW
MONTH_BOX_HEIGHT = DAY_BOX_HEIGHT * WEEK_ROWS_PER_MONTH

MONTH_LABEL_OFFSET_X = 100
MONTH_LABEL_OFFSET_Y = -30
MONTH_LABEL_FONT_SIZE = 30
DAY_OF_WEEK_LABEL_OFFSET_X = 20
DAY_OF_WEEK_LABEL_OFFSET_Y = -7
DAY_OF_WEEK_LABEL_FONT_SIZE = 20
DAY_NUMBER_BASELINE = 33
DAY_NUMBER_FONT_SIZE = 24

FOOTER_MARGIN = 15
WARNING_Y = 1055
NOTICE_Y = 1075
FOOTER_FONT_SIZE = 16


def legend_color(pickup: Pickup) -> str:
    return CORNER_FLAG_COLORS.get(pickup, FILL_COLORS[pickup])


def text_width(text: str, font_size: int) -> float:
    return len(text) * font_size * SERIF_WIDTH_PER_POINT


def largest_font_size_that_fits(
    text: str, available_width: int, preferred_size: int
) -> int:
    size = preferred_size
    while size > 1 and text_width(text, size) > available_width:
        size -= 1
    return size


def svg_rect(x: int, y: int, width: int, height: int, fill: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'fill="{fill}" stroke="{BLACK}" stroke-width="{BORDER_WIDTH}"/>\n'
    )


def svg_centered_text(
    x: int, y: int, content: str, font_size: int, fill: str = BLACK
) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" text-anchor="middle" '
        f'font-family="serif" font-size="{font_size}">{escape(content)}</text>\n'
    )


def svg_corner_flag(x: int, y: int, fill: str) -> str:
    corners = f"{x},{y} {x + DAY_BOX_WIDTH},{y} {x},{y + DAY_BOX_HEIGHT}"
    return f'<polygon points="{corners}" fill="{fill}"/>\n'


def svg_titles(year: int, zone: int) -> str:
    title = f"{year} Sanitation and Recycling Schedule (Zone {zone})"
    return svg_centered_text(
        PAGE_CENTER_X, HEADING_Y, HEADING, HEADING_FONT_SIZE
    ) + svg_centered_text(PAGE_CENTER_X, TITLE_Y, title, TITLE_FONT_SIZE)


def svg_legend() -> str:
    parts = []
    for row_number, row in enumerate(LEGEND_ROWS):
        box_widths = [
            round(text_width(pickup.value, LEGEND_FONT_SIZE)) + 2 * LEGEND_BOX_PADDING
            for pickup in row
        ]
        row_width = sum(box_widths) + LEGEND_BOX_GAP * (len(row) - 1)
        x = PAGE_CENTER_X - row_width // 2
        y = LEGEND_TOP_Y + row_number * LEGEND_ROW_SPACING

        for pickup, box_width in zip(row, box_widths):
            parts.append(
                svg_rect(x, y, box_width, LEGEND_BOX_HEIGHT, legend_color(pickup))
            )
            parts.append(
                svg_centered_text(
                    x + box_width // 2,
                    y + LEGEND_LABEL_BASELINE,
                    pickup.value,
                    LEGEND_FONT_SIZE,
                )
            )
            x += box_width + LEGEND_BOX_GAP
    return "".join(parts)


def month_box_corner(month_index: int) -> tuple[int, int]:
    column = (month_index - 1) % GRID_COLUMNS
    row = (month_index - 1) // GRID_COLUMNS
    return (
        GRID_LEFT + column * MONTH_BOX_SPACING_X,
        GRID_TOP + row * MONTH_BOX_SPACING_Y,
    )


def svg_month_headings(month: Month, left: int, top: int) -> str:
    parts = [
        svg_rect(left, top, MONTH_BOX_WIDTH, MONTH_BOX_HEIGHT, WHITE),
        svg_centered_text(
            left + MONTH_LABEL_OFFSET_X,
            top + MONTH_LABEL_OFFSET_Y,
            month.name,
            MONTH_LABEL_FONT_SIZE,
        ),
    ]
    for column, label in enumerate(DAY_OF_WEEK_LABELS):
        parts.append(
            svg_centered_text(
                left + DAY_OF_WEEK_LABEL_OFFSET_X + column * DAY_BOX_WIDTH,
                top + DAY_OF_WEEK_LABEL_OFFSET_Y,
                label,
                DAY_OF_WEEK_LABEL_FONT_SIZE,
            )
        )
    return "".join(parts)


def svg_empty_cells(left: int, top: int) -> str:
    return "".join(
        svg_rect(
            left + column * DAY_BOX_WIDTH,
            top + row * DAY_BOX_HEIGHT,
            DAY_BOX_WIDTH,
            DAY_BOX_HEIGHT,
            WHITE,
        )
        for row in range(WEEK_ROWS_PER_MONTH)
        for column in range(WEEKDAYS_PER_ROW)
    )


def svg_filled_cell(x: int, y: int, pickup: Pickup) -> str:
    filled = svg_rect(x, y, DAY_BOX_WIDTH, DAY_BOX_HEIGHT, FILL_COLORS[pickup])
    corner_color = CORNER_FLAG_COLORS.get(pickup)
    if corner_color is None:
        return filled
    return (
        filled
        + svg_corner_flag(x, y, corner_color)
        + svg_rect(x, y, DAY_BOX_WIDTH, DAY_BOX_HEIGHT, NO_FILL)
    )


def svg_month(month: Month, weeks_of_pickups: list[list[Pickup | None]]) -> str:
    left, top = month_box_corner(month.index)
    parts = [svg_month_headings(month, left, top), svg_empty_cells(left, top)]

    for row_number, (row, pickups) in enumerate(zip(month.weeks, weeks_of_pickups)):
        y = top + row_number * DAY_BOX_HEIGHT
        for column, (day, pickup) in enumerate(zip(row, pickups)):
            x = left + column * DAY_BOX_WIDTH
            if pickup is not None:
                parts.append(svg_filled_cell(x, y, pickup))
            if day:
                parts.append(
                    svg_centered_text(
                        x + DAY_BOX_WIDTH // 2,
                        y + DAY_NUMBER_BASELINE,
                        str(day),
                        DAY_NUMBER_FONT_SIZE,
                    )
                )
    return "".join(parts)


def svg_footer() -> str:
    available_width = PAGE_WIDTH - 2 * FOOTER_MARGIN
    font_size = min(
        largest_font_size_that_fits(text, available_width, FOOTER_FONT_SIZE)
        for text in (WARNING, NOTICE)
    )
    return svg_centered_text(
        PAGE_CENTER_X, WARNING_Y, WARNING, font_size, RED
    ) + svg_centered_text(PAGE_CENTER_X, NOTICE_Y, NOTICE, font_size)


def render_calendar(year: int, zone: int) -> str:
    holidays = observed_holidays(year)
    opening_tag = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {PAGE_WIDTH} {PAGE_HEIGHT}">\n'
    )
    parts = [
        opening_tag,
        svg_titles(year, zone),
        svg_legend(),
    ]
    for month in months(year):
        parts.append(svg_month(month, month_pickups(month, zone, holidays)))
    parts.append(svg_footer())
    parts.append("</svg>\n")
    return "".join(parts)


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the Village of Ossining sanitation calendar as SVG."
    )
    parser.add_argument("--year", type=int, default=date.today().year)
    parser.add_argument(
        "--zone", type=int, choices=ZONES, action="append", dest="zones"
    )
    parser.add_argument("--out", type=Path, default=Path("."))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    arguments = parse_arguments(argv)
    arguments.out.mkdir(parents=True, exist_ok=True)
    for zone in arguments.zones or ZONES:
        destination = arguments.out / f"{arguments.year}_calendar_zone_{zone}.svg"
        destination.write_text(render_calendar(arguments.year, zone), encoding="utf-8")
        print(f"wrote {destination}")


if __name__ == "__main__":
    main()
