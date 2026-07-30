"""Tests for split_message_parts — breaking one reply into multiple Telegram messages."""

from utils.telegram_formatting import split_message_parts, TELEGRAM_PART_SEPARATOR


def test_no_separator_returns_single_part():
    assert split_message_parts("hello world") == ["hello world"]


def test_two_parts_split_and_stripped():
    text = f"Part one.\n\n{TELEGRAM_PART_SEPARATOR}\n\nPart two."
    assert split_message_parts(text) == ["Part one.", "Part two."]


def test_three_parts():
    text = f"A{TELEGRAM_PART_SEPARATOR}B{TELEGRAM_PART_SEPARATOR}C"
    assert split_message_parts(text) == ["A", "B", "C"]


def test_empty_parts_dropped():
    text = f"Only this.{TELEGRAM_PART_SEPARATOR}{TELEGRAM_PART_SEPARATOR}   "
    assert split_message_parts(text) == ["Only this."]


def test_empty_string_returns_empty_list():
    assert split_message_parts("") == []


def test_whitespace_only_returns_empty_list():
    assert split_message_parts("   \n\n  ") == []
