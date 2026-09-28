"""Tests für den Kostenschutz der Live-KI."""

from datetime import date

from src.ai_usage import MAX_CALLS_PER_DAY, MAX_CALLS_PER_SESSION, MAX_MESSAGE_LENGTH, calls_today, limit_reason, register_call

TODAY = date(2026, 9, 28)


def test_calls_are_counted_per_day(writable_conn):
    assert calls_today(writable_conn, TODAY) == 0
    register_call(writable_conn, TODAY)
    register_call(writable_conn, TODAY)
    assert calls_today(writable_conn, TODAY) == 2
    assert calls_today(writable_conn, date(2026, 9, 29)) == 0


def test_normal_request_is_allowed():
    assert limit_reason("5 Fass Helles", session_calls=0, day_calls=0) is None


def test_limits_block_requests():
    assert "eingeben" in limit_reason("   ", 0, 0)
    assert "zu lang" in limit_reason("x" * (MAX_MESSAGE_LENGTH + 1), 0, 0)
    assert "Besuch" in limit_reason("5 Fass", MAX_CALLS_PER_SESSION, 0)
    assert "Tageslimit" in limit_reason("5 Fass", 0, MAX_CALLS_PER_DAY)
