"""Unit tests for the _markdown_to_html helper in telegram_service."""

import importlib.util
from pathlib import Path

# Load telegram_service directly to avoid triggering services/__init__.py,
# which imports modules that require unavailable credentials in test environments.
_spec = importlib.util.spec_from_file_location(
    "services.telegram_service",
    Path(__file__).parent.parent / "services" / "telegram_service.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_markdown_to_html = _mod._markdown_to_html


def test_plain_text_passthrough():
    assert _markdown_to_html("hello world") == "hello world"


def test_empty_string():
    assert _markdown_to_html("") == ""


def test_bold_asterisk():
    assert _markdown_to_html("**hello**") == "<b>hello</b>"


def test_bold_underscore():
    assert _markdown_to_html("__hello__") == "<b>hello</b>"


def test_italic_asterisk():
    assert _markdown_to_html("*hi*") == "<i>hi</i>"


def test_italic_underscore():
    assert _markdown_to_html("_hi_") == "<i>hi</i>"


def test_snake_case_untouched():
    assert _markdown_to_html("my_var_name") == "my_var_name"


def test_inline_code():
    result = _markdown_to_html("`x = 1`")
    assert result == "<code>x = 1</code>"


def test_fenced_code_block():
    result = _markdown_to_html("```python\nx = 1\n```")
    assert "<pre><code>" in result
    assert "x = 1" in result
    assert "</code></pre>" in result


def test_link():
    result = _markdown_to_html("[Google](https://google.com)")
    assert result == '<a href="https://google.com">Google</a>'


def test_strikethrough():
    assert _markdown_to_html("~~old~~") == "<s>old</s>"


def test_header_h1():
    assert _markdown_to_html("# Title") == "<b>Title</b>"


def test_header_h2():
    assert _markdown_to_html("## Section") == "<b>Section</b>"


def test_header_h3():
    assert _markdown_to_html("### Sub") == "<b>Sub</b>"


def test_html_chars_in_prose():
    result = _markdown_to_html("a < b & c > d")
    assert result == "a &lt; b &amp; c &gt; d"


def test_html_chars_in_inline_code():
    result = _markdown_to_html("`a < b`")
    assert result == "<code>a &lt; b</code>"


def test_html_chars_in_fenced_code():
    result = _markdown_to_html("```\na < b\n```")
    assert "<pre><code>" in result
    assert "a &lt; b" in result


def test_code_block_contents_not_formatted():
    # Markdown inside a code block must not be converted.
    result = _markdown_to_html("```\n**not bold**\n```")
    assert "<b>" not in result
    assert "**not bold**" in result


def test_inline_code_contents_not_formatted():
    result = _markdown_to_html("`**not bold**`")
    assert "<b>" not in result
    assert "**not bold**" in result


def test_bold_not_consumed_by_italic():
    result = _markdown_to_html("**bold**")
    assert result == "<b>bold</b>"
    assert "<i>" not in result


def test_link_with_ampersand_in_url():
    # & in URLs must be HTML-escaped to &amp; — this is correct HTML for href attributes.
    result = _markdown_to_html("[Search](https://example.com?a=1&b=2)")
    assert 'href="https://example.com?a=1&amp;b=2"' in result


def test_multiline_bold():
    result = _markdown_to_html("**line one\nline two**")
    assert result == "<b>line one\nline two</b>"


def test_mixed_formatting():
    result = _markdown_to_html("**bold** and *italic* and `code`")
    assert "<b>bold</b>" in result
    assert "<i>italic</i>" in result
    assert "<code>code</code>" in result
