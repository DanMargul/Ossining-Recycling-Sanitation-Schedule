from datetime import date, datetime, timezone

import pytest

import check_published_feeds
from calendar_feed import vcalendar
from check_published_feeds import FeedProblem, check_feed

GENERATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
DURING_THE_2026_SEASON = date(2026, 6, 1)
LONG_AFTER_THE_2026_SEASON = date(2030, 1, 1)
ANY_URL = "https://example.org/zone-1.ics"


def healthy_feed() -> bytes:
    return vcalendar(1, [2026], GENERATED_AT, 2026).encode("utf-8")


def serving(body: bytes, content_type: str = "text/calendar; charset=utf-8"):
    def fake_fetch(url: str) -> tuple[bytes, str]:
        return body, content_type

    return fake_fetch


def test_a_healthy_feed_passes_without_warnings(monkeypatch):
    monkeypatch.setattr(check_published_feeds, "fetch", serving(healthy_feed()))
    assert check_feed(ANY_URL, DURING_THE_2026_SEASON) == []


def test_a_plain_text_content_type_warns_but_does_not_fail(monkeypatch):
    monkeypatch.setattr(
        check_published_feeds, "fetch", serving(healthy_feed(), "text/plain")
    )
    warnings = check_feed(ANY_URL, DURING_THE_2026_SEASON)
    assert len(warnings) == 1
    assert "text/plain" in warnings[0]


def test_a_feed_that_ran_out_of_years_fails(monkeypatch):
    monkeypatch.setattr(check_published_feeds, "fetch", serving(healthy_feed()))
    with pytest.raises(FeedProblem, match="last collection day"):
        check_feed(ANY_URL, LONG_AFTER_THE_2026_SEASON)


def test_an_almost_empty_feed_fails(monkeypatch):
    nearly_empty = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"
    monkeypatch.setattr(check_published_feeds, "fetch", serving(nearly_empty))
    with pytest.raises(FeedProblem, match="only 0 events"):
        check_feed(ANY_URL, DURING_THE_2026_SEASON)


def test_a_page_of_html_fails(monkeypatch):
    monkeypatch.setattr(
        check_published_feeds, "fetch", serving(b"<html>404</html>", "text/html")
    )
    with pytest.raises(FeedProblem):
        check_feed(ANY_URL, DURING_THE_2026_SEASON)
