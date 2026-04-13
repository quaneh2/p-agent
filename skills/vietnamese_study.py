"""
Vietnamese Study Skill

Fetches recent article listings from Vietnamese news sites (VNExpress, Tuổi Trẻ,
Thanh Niên) filtered by topic, and returns the raw page text so Claude can
identify suitable articles and select a B1→B2 paragraph for a translation exercise.

This skill deliberately does NOT pre-select articles or judge language complexity.
That work belongs to the language model, not to a keyword heuristic.

Typical flow:
  1. Claude calls fetch_vietnamese_articles (optionally with a topic)
  2. Skill fetches 1–3 section pages and returns their text
  3. Claude reads the text, picks a suitable article headline
  4. Claude calls fetch_url on the article URL to get the full text
  5. Claude selects a paragraph and presents it to the user for translation
"""

import logging

logger = logging.getLogger(__name__)

# Section pages per topic.  We fetch these listing pages (not individual articles)
# and return their text content for Claude to browse.
SOURCES: dict[str, list[tuple[str, str]]] = {
    "current_affairs": [
        ("VNExpress", "https://vnexpress.net/the-gioi"),
        ("Tuổi Trẻ", "https://tuoitre.vn/tin-tuc.htm"),
        ("Thanh Niên", "https://thanhnien.vn/thoi-su.htm"),
    ],
    "nature": [
        ("VNExpress", "https://vnexpress.net/khoa-hoc"),
        ("Tuổi Trẻ", "https://tuoitre.vn/khoa-hoc.htm"),
    ],
    "food": [
        ("VNExpress", "https://vnexpress.net/am-thuc"),
        ("Tuổi Trẻ", "https://tuoitre.vn/am-thuc.htm"),
    ],
    "travel": [
        ("VNExpress", "https://vnexpress.net/du-lich"),
        ("Tuổi Trẻ", "https://tuoitre.vn/du-lich.htm"),
        ("Thanh Niên", "https://thanhnien.vn/du-lich.htm"),
    ],
}

ALL_SOURCES: list[tuple[str, str]] = [
    ("VNExpress", "https://vnexpress.net/"),
    ("Tuổi Trẻ", "https://tuoitre.vn/"),
    ("Thanh Niên", "https://thanhnien.vn/"),
]

# Max characters of section-page text to return per source.
# Enough to surface 10–20 article titles without flooding context.
SECTION_MAX_CHARS = 6_000

# Max number of section pages to fetch in one call.
MAX_PAGES = 3


class VietnameseStudySkill:
    """
    Fetches Vietnamese news section pages and returns their text content
    for Claude to browse and select a suitable article.

    Depends on:
      - fetch_service: FetchService — for HTTP fetching
    """

    def __init__(self, fetch_service):
        self.fetch = fetch_service

    def run(self, topic: str = None) -> dict:
        """
        Fetch section page(s) from Vietnamese news sites.

        Parameters
        ----------
        topic : str, optional
            One of "current_affairs", "nature", "food", "travel".
            If None or unrecognised, fetches from all homepages.

        Returns
        -------
        dict with:
          - success: bool
          - topic: str
          - pages: list[dict]  — each has source_site, section_url, content
          - error: str  (only on failure)

        Each page dict:
          - source_site: str  (e.g. "VNExpress")
          - section_url: str
          - content: str  (plain text of the section page, up to SECTION_MAX_CHARS)
          - fetch_failed: bool
          - fetch_error: str | None
        """
        try:
            sources = SOURCES.get(topic) if topic else None
            if not sources:
                sources = ALL_SOURCES

            pages = []
            for site_name, url in sources[:MAX_PAGES]:
                page = self._fetch_page(site_name, url)
                pages.append(page)

            return {
                "success": True,
                "topic": topic or "all",
                "pages": pages,
            }

        except Exception as e:
            logger.error("VietnameseStudySkill failed: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}

    def _fetch_page(self, site_name: str, url: str) -> dict:
        """Fetch a single section page and return its text content."""
        logger.info("Vietnamese study: fetching %s (%s)", site_name, url)

        base = {
            "source_site": site_name,
            "section_url": url,
        }

        result = self.fetch.fetch_url(url=url, max_length=SECTION_MAX_CHARS)
        if not result.get("success"):
            return {
                **base,
                "content": None,
                "fetch_failed": True,
                "fetch_error": result.get("error", "unknown error"),
            }

        return {
            **base,
            "content": result.get("content", ""),
            "fetch_failed": False,
            "fetch_error": None,
        }
