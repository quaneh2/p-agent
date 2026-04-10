# Rebuilding the HN Digest Skill

The HN digest skill is responsible for fetching the top Hacker News stories each
day, filtering them for relevance, and producing a useful summary for the user. It
sounds straightforward — but the original implementation had three distinct flaws,
each worth understanding in its own right.

---

## The Original Design

When the skill was first written, the architecture was:

1. Fetch the HN front page as HTML via `FetchService`
2. Strip the HTML tags to get plain text
3. Regex-parse the plain text to extract story titles, scores, and URLs
4. Truncate the first 1,500 characters of each article as a "summary"
5. Save pre-formatted markdown files to the workspace and return a compact index to the user

Each of these steps had a problem.

---

## Problem 1: The URL Extraction Was Completely Broken

### What was happening

`FetchService._clean_html()` works by stripping all HTML tags with a regex. That
includes `<a href="...">` tags — the very things that carry the article URLs.

After cleaning, the HN front page looked roughly like this:

```
1. Story Title (github.com) 500 points by user 2 hours ago | 123 comments
2. Another Story (arxiv.org) 312 points by user 4 hours ago | 87 comments
```

The parser correctly spotted the domain names in parentheses and extracted them.
But then it constructed the URL as:

```python
url = f"https://{domain}" if domain else HN_FRONT_PAGE
```

So a story linking to `https://github.com/user/some-project/releases/v2.0` became
`https://github.com`. The skill was fetching and summarising the GitHub homepage —
and the homepage of every other domain — rather than the actual articles.

Every summary in the workspace was wrong.

### The fix

The HN Firebase API provides exactly what we need as structured JSON:

- `GET https://hacker-news.firebaseio.com/v0/topstories.json` returns an array of
  story IDs
- `GET https://hacker-news.firebaseio.com/v0/item/{id}.json` returns the item,
  including a `url` field with the real, full article URL

Switching to the API meant the URL problem vanished entirely. As a side effect, the
brittle regex parser for the front page was deleted — around 50 lines of fragile
code replaced by a straightforward JSON parse.

Stories without an external URL (Ask HN, Show HN posts) fall back to their HN
discussion page (`https://news.ycombinator.com/item?id={id}`) rather than the front
page, which is also an improvement.

`FetchService` also needed a one-line fix: it was rejecting `application/json`
responses (returning an error for any content type that wasn't `text/html` or
`text/plain`), so the API calls would have failed silently. Adding JSON to the
accepted content types, with the raw response returned unmodified (no HTML
cleaning needed for JSON), fixed that.

---

## Problem 2: The "Summaries" Were Useless Text Dumps

### What was happening

The `_summarise()` method attempted to produce a summary by:

1. Splitting the cleaned article text into lines
2. Keeping only lines longer than 60 characters (to filter out nav links)
3. Joining those lines and returning the first 1,500 characters

This is not a summary. It's a truncation heuristic, and a brittle one.

The 60-character line filter failed in both directions:

- **False positives (noise passes through):** Navigation text like
  `Home Missions Humans in Space Earth The Solar System The Universe…` gets
  concatenated into a single very long string after HTML tag stripping. It passes
  the 60-char filter and dominates the "summary". The NASA article in the
  workspace was almost entirely navigation links.

- **False negatives (content gets dropped):** The GLM-5.1 article returned
  `"No readable content extracted."` — its actual content lines happened to be
  shorter than 60 characters after stripping.

The workspace file `notes.md` was, at best, a dump of article boilerplate. At
worst, it contained nothing. The user couldn't get useful information from it.

### Why it was designed this way

The original design tried to make the skill self-contained: it gathers data, it
summarises, it saves, it returns a pre-formatted index. The agent (Claude) just
echoes the index to the user.

The fundamental mistake was delegating summarisation to a text-truncation function
rather than to the language model. The skill was short-circuiting the thing it was
embedded inside.

### The fix

The skill's role was redefined: **gather and deliver data; let Claude do the
reasoning.**

The new `run()` returns structured article data — title, URL, HN score, relevance
score, and the raw cleaned article text (up to 6,000 characters each) — as a list
of dicts in the tool result JSON:

```json
{
  "success": true,
  "date": "2026-04-09",
  "output_folder": "research/hn-2026-04-09",
  "articles": [
    {
      "title": "Git commands I run before reading any code",
      "url": "https://piechowski.io/post/git-commands-before-reading-code/",
      "score": 812,
      "relevance": 0.33,
      "content": "Five git commands that tell you where a codebase hurts…",
      "fetch_failed": false,
      "fetch_error": null
    },
    ...
  ]
}
```

When the agent (Claude) receives this tool result, it has the full article texts in
context. It writes real summaries from the content, identifies themes across
articles, draws out actionable insights, and saves structured notes to the workspace
using the `save_document` tool.

The tool description in `definitions.py` was updated to make this division of labour
explicit:

> *"After calling this tool, YOU must: (1) write a genuine summary of each article
> from its raw content, (2) identify themes, connections, and insights across all
> articles, and (3) save structured notes to the workspace."*

The `workspace_fn` dependency was also removed from the skill constructor — since
the skill no longer saves anything, it doesn't need access to the workspace.

---

## Problem 3: 529 Overload Errors Were Being Retried Naïvely

### What was happening

While debugging the digest skill, recurring `529 Overloaded` errors appeared in
the logs. The existing retry logic handled all non-429 errors with an exponential
backoff starting at 1 second:

```
retrying in 1.000 seconds (OverloadedError)
retrying in 2.000 seconds (OverloadedError)
retrying in 4.000 seconds (OverloadedError)
retrying in 8.000 seconds (OverloadedError)
retrying in 16.000 seconds (OverloadedError)
retrying in 32.000 seconds (OverloadedError)
retrying in 60.000 seconds (OverloadedError)
… (four more at 60 s)
ERROR: Claude API error: Error code: 529
```

The agent retried 11 times over about 6 minutes before giving up. On the surface,
that looks like patient handling — but the early retries were wasteful.

### 429 vs 529: two very different problems

These two error codes are often confused but have nothing in common:

| | 429 Rate Limited | 529 Overloaded |
|---|---|---|
| **Cause** | Client sent too many requests | Server is under too much load |
| **Recovery time** | Typically seconds (honour the `Retry-After` header) | Seconds to minutes |
| **Existing defence** | `ANTHROPIC_MIN_REQUEST_INTERVAL_SECONDS = 0.5` | Exponential backoff retry loop |

The 0.5-second burst control is the right defence for 429. It does nothing for 529
— those errors come from the server's load, not the client's request rate.

### Why starting at 1 second is wrong for 529

Server overload means the backend is saturated: it can't process any more work
right now. Retrying after 1 second almost never helps. Retrying after 2 seconds
is barely better. The first five retries (1 + 2 + 4 + 8 + 16 = 31 seconds of total
wait) have little realistic chance of succeeding. They burn through a large fraction
of the retry budget achieving nothing.

### The fix

When a 529 is detected on the very first retry attempt, the initial backoff is
bumped from 1 second to 5 seconds:

```python
# agent.py
status_code = getattr(getattr(e, "response", None), "status_code", None)
if status_code == 529 and backoff == ANTHROPIC_BACKOFF_INITIAL_SECONDS:
    backoff = ANTHROPIC_OVERLOAD_BACKOFF_INITIAL_SECONDS  # 5.0
```

The new retry sequence is `5 → 10 → 20 → 40 → 60 → 60 → …` rather than
`1 → 2 → 4 → 8 → 16 → 32 → 60 → …`. The total wait before giving up is similar
(~7 minutes vs ~5 minutes for 10 retries), but each wait is a realistic recovery
window rather than an optimistic guess.

A distinct log line was also added so 529 and other errors are easy to tell apart:

```
Anthropic API overloaded (529) — retrying in 5.000 seconds
```

vs

```
Anthropic request failed — retrying in 1.000 seconds (SomeOtherError)
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `services/fetch_service.py` | Accept `application/json` responses; skip HTML cleaning for JSON |
| `skills/hn_digest.py` | Replace front-page scraping + regex parser with HN Firebase API; return raw article content for Claude to synthesise instead of pre-formatted text; remove `workspace_fn` dependency |
| `tools/definitions.py` | Update tool description to instruct Claude on its obligations after calling the tool |
| `agent.py` | Detect 529 specifically; use 5 s initial backoff floor for overload errors; add distinct log line |

The net result: accurate article URLs, real AI-generated summaries and synthesis
rather than text truncation, and more efficient retry behaviour under API overload.
