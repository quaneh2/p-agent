"""
VietnameseDashboardSkill — generates a static HTML Vietnamese vocab progress page
and pushes it to the existing GitHub Pages repo.

Page: https://stevens-j-54.github.io/vietnamese/
Updated after every save_vietnamese_session call and nightly by a scheduled task.
No Claude API calls — pure Python template engine.
"""

import html as html_lib
import json
import logging
from datetime import date, timedelta
from pathlib import Path

from config import AGENT_CORE_DIR, GITHUB_USERNAME

logger = logging.getLogger(__name__)

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# CSS defined as a plain string to avoid f-string brace-escaping in CSS rules.
_CSS = """
:root {
  --bg:       #F2E6C2;
  --paper:    #FDFAF0;
  --text:     #1A0A06;
  --muted:    #5C3D25;
  --red:      #CC1100;
  --red-dark: #7A0000;
  --gold:     #FFD700;
  --border:   #CC1100;
  --heat-0:   #E8D9B0;
  --heat-1:   #F4A07A;
  --heat-2:   #E86040;
  --heat-3:   #CC1100;
  --heat-4:   #7A0000;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Be Vietnam Pro', sans-serif;
  font-size: 15px;
  line-height: 1.6;
  min-height: 100vh;
}
a { color: var(--red); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Masthead ─────────────────────────────────────────────────── */
header {
  background: var(--red);
  text-align: center;
  padding: 1.8rem 1.5rem 1.6rem;
  border-bottom: 6px solid var(--red-dark);
  position: relative;
}
.mast-stars {
  font-size: 1rem;
  color: var(--gold);
  letter-spacing: 0.7em;
  margin-bottom: 0.6rem;
  display: block;
}
.mast-title {
  font-size: 2.8rem;
  font-weight: 900;
  color: var(--gold);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  line-height: 1;
  text-shadow: 2px 2px 0 rgba(0,0,0,0.3);
}
.mast-rule {
  width: 60%;
  height: 1px;
  background: rgba(255,215,0,0.4);
  margin: 0.7rem auto;
}
.mast-subtitle {
  font-size: 0.75rem;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
  text-transform: uppercase;
  letter-spacing: 0.22em;
}
.mast-date {
  font-size: 0.75rem;
  color: rgba(255,255,255,0.65);
  margin-top: 0.4rem;
  letter-spacing: 0.05em;
}

/* ── Layout ───────────────────────────────────────────────────── */
main { max-width: 840px; margin: 0 auto; padding: 2rem; }

/* ── Section divider ──────────────────────────────────────────── */
.divider {
  position: relative;
  height: 2px;
  background: var(--red);
  margin: 2rem 0;
}
.divider::after {
  content: '★';
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  background: var(--bg);
  color: var(--red);
  padding: 0 0.6rem;
  font-size: 0.8rem;
  line-height: 1;
}

/* ── Section titles ───────────────────────────────────────────── */
.section-title {
  display: inline-block;
  background: var(--red);
  color: var(--gold);
  padding: 0.25rem 1rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  margin-bottom: 1.1rem;
}
.section-title::before { content: '★  '; }
.section-title::after  { content: '  ★'; }

/* ── Stats strip ──────────────────────────────────────────────── */
.stats-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--border);
  border: 2px solid var(--border);
  margin-bottom: 0.5rem;
}
.stat-card {
  background: var(--paper);
  padding: 1rem 1.1rem;
  text-align: center;
}
.stat-value {
  font-size: 2rem;
  font-weight: 900;
  color: var(--red);
  line-height: 1;
}
.stat-label {
  font-size: 0.7rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-top: 0.35rem;
  padding-top: 0.35rem;
  border-top: 1px solid var(--border);
}

/* ── No practice ──────────────────────────────────────────────── */
.no-practice {
  color: var(--muted);
  font-style: italic;
  padding: 0.5rem 0;
  border-left: 3px solid var(--border);
  padding-left: 0.8rem;
}

/* ── Session cards ────────────────────────────────────────────── */
.session-card {
  background: var(--paper);
  border: 1px solid #C8B898;
  border-left: 5px solid var(--red);
  padding: 1rem 1.2rem;
  margin-bottom: 0.8rem;
}
.session-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}
.badge {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  border-radius: 0;
}
.badge-quiz         { background: var(--red);      color: var(--gold); }
.badge-exercise     { background: var(--red-dark); color: var(--gold); }
.badge-conversation { background: #5C3520;         color: #FFCC88; }
.badge-lookup       { background: #2A1A08;         color: #F5D890; }
.session-topic { color: var(--muted); font-size: 0.88rem; }
.score {
  margin-left: auto;
  font-size: 1rem;
  font-weight: 700;
  color: var(--red-dark);
  font-variant-numeric: tabular-nums;
}

/* ── Vocab section ────────────────────────────────────────────── */
.vocab-section { margin-top: 0.8rem; }
.vocab-item { margin-bottom: 0.9rem; padding-left: 0.2rem; }
.vocab-tag {
  display: inline-block;
  background: var(--red);
  color: var(--gold);
  padding: 0.15rem 0.55rem;
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 0.3rem;
}
.vocab-english { color: var(--muted); font-size: 0.8rem; }
.sample-vi {
  font-size: 0.88rem;
  color: var(--text);
  margin: 0.15rem 0 0 0.2rem;
  font-style: italic;
}
.sample-en {
  font-size: 0.78rem;
  color: var(--muted);
  margin: 0 0 0 0.2rem;
}

/* ── Heatmap ──────────────────────────────────────────────────── */
.heatmap-wrap { overflow-x: auto; padding-bottom: 0.5rem; }
.heatmap-months { display: flex; margin-bottom: 4px; padding-left: 1px; }
.hm-month { font-size: 0.7rem; color: var(--muted); width: 16px; text-align: left; flex-shrink: 0; }
.heatmap-grid {
  display: grid;
  grid-template-rows: repeat(7, 13px);
  grid-auto-flow: column;
  grid-auto-columns: 13px;
  gap: 3px;
}
.hm-cell { width: 13px; height: 13px; border-radius: 1px; background: var(--heat-0); }
.hm-cell.level-1 { background: var(--heat-1); }
.hm-cell.level-2 { background: var(--heat-2); }
.hm-cell.level-3 { background: var(--heat-3); }
.hm-cell.level-4 { background: var(--heat-4); }
.heatmap-legend {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 0.6rem;
  font-size: 0.72rem;
  color: var(--muted);
}
.legend-cell { width: 11px; height: 11px; border-radius: 1px; }

/* ── History ──────────────────────────────────────────────────── */
.day-details {
  border: 1px solid #C8B898;
  border-left: 4px solid var(--red);
  margin-bottom: 0.5rem;
  background: var(--paper);
}
.day-summary {
  cursor: pointer;
  padding: 0.7rem 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  list-style: none;
  user-select: none;
}
.day-summary::-webkit-details-marker { display: none; }
.day-summary::before {
  content: '▶';
  color: var(--red);
  font-size: 0.6rem;
  display: inline-block;
  width: 0.8rem;
  flex-shrink: 0;
}
details[open] .day-summary::before { content: '▼'; }
.day-date { font-weight: 600; font-size: 0.9rem; }
.day-meta { font-size: 0.8rem; color: var(--muted); margin-left: auto; }
.day-cards { padding: 0 0.8rem 0.8rem; }

/* ── Footer ───────────────────────────────────────────────────── */
footer {
  text-align: center;
  padding: 1.5rem 2rem;
  color: var(--muted);
  font-size: 0.78rem;
  background: var(--red);
  color: rgba(255,255,255,0.7);
  margin-top: 3rem;
  letter-spacing: 0.05em;
}
footer a { color: var(--gold); }

@media (max-width: 600px) {
  .stats-strip { grid-template-columns: repeat(2, 1fr); }
  main { padding: 1rem; }
  .mast-title { font-size: 2rem; }
}
"""


class VietnameseDashboardSkill:
    """
    Generates a Vietnamese vocab progress page and publishes it to GitHub Pages.
    Reads data directly from the local agent-core filesystem clone.
    Shares the DashboardSkill's GitRepo instance to avoid maintaining a second clone.
    """

    def __init__(self, dashboard_skill):
        # dashboard_skill: DashboardSkill — borrowed for its GitRepo instance only
        self._dashboard_skill = dashboard_skill
        self._vocab_path = Path(AGENT_CORE_DIR) / "vietnamese_vocab.json"
        self._exercises_dir = Path(AGENT_CORE_DIR) / "exercises"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Called by the scheduler (instruction_type='skill')."""
        return self.update()

    def update(self) -> dict:
        """Regenerate and push vietnamese/index.html to GitHub Pages."""
        try:
            vocab_data = self._load_vocab()
            sessions = self._load_sessions()
            page_html = self.generate_html(vocab_data, sessions)
            repo = self._dashboard_skill._get_repo()
            repo.write_file("vietnamese/index.html", page_html)
            result = repo.commit_and_push("Update Vietnamese vocab dashboard")
            if result.get("success"):
                url = f"https://{GITHUB_USERNAME}.github.io/vietnamese/"
                logger.info("Vietnamese dashboard updated: %s", url)
                return {"success": True, "url": url, "action": result.get("action")}
            return result
        except Exception as e:
            logger.error("Vietnamese dashboard update failed: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_vocab(self) -> dict:
        try:
            if self._vocab_path.exists():
                with open(self._vocab_path, encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return {"version": 2, "entries": []}

    def _load_sessions(self) -> list:
        sessions = []
        if not self._exercises_dir.exists():
            return sessions
        for path in sorted(self._exercises_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    sessions.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
        return sessions

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _sessions_by_date(self, sessions: list) -> dict:
        by_date: dict = {}
        for s in sessions:
            raw = s.get("date", "")
            if not raw:
                continue
            try:
                day = str(raw)[:10]
                date.fromisoformat(day)
                by_date.setdefault(day, []).append(s)
            except ValueError:
                pass
        return by_date

    def _compute_streak(self, sessions_by_date: dict) -> int:
        today = date.today()
        check = today if today.isoformat() in sessions_by_date else today - timedelta(days=1)
        streak = 0
        while check.isoformat() in sessions_by_date:
            streak += 1
            check -= timedelta(days=1)
        return streak

    def _heatmap_data(self, sessions_by_date: dict) -> list:
        today = date.today()
        result = []
        for i in range(111, -1, -1):
            d = today - timedelta(days=i)
            key = d.isoformat()
            day_sessions = sessions_by_date.get(key, [])
            word_count = sum(len(s.get("vocab_reviewed", [])) for s in day_sessions)
            if word_count == 0:
                level = 0
            elif word_count < 5:
                level = 1
            elif word_count < 10:
                level = 2
            elif word_count < 20:
                level = 3
            else:
                level = 4
            result.append({"date": key, "count": word_count, "level": level})
        return result

    def _compute_stats(self, vocab_data: dict, sessions: list, sessions_by_date: dict) -> dict:
        today = date.today()
        week_ago = (today - timedelta(days=7)).isoformat()
        sessions_this_week = sum(1 for s in sessions if str(s.get("date", ""))[:10] >= week_ago)
        return {
            "total_words": len(vocab_data.get("entries", [])),
            "sessions_this_week": sessions_this_week,
            "streak": self._compute_streak(sessions_by_date),
            "total_sessions": len(sessions),
        }

    # ------------------------------------------------------------------
    # HTML generation
    # ------------------------------------------------------------------

    def generate_html(self, vocab_data: dict, sessions: list) -> str:
        sessions_by_date = self._sessions_by_date(sessions)
        stats = self._compute_stats(vocab_data, sessions, sessions_by_date)
        heatmap = self._heatmap_data(sessions_by_date)

        vocab_map: dict = {}
        for entry in vocab_data.get("entries", []):
            w = entry.get("vietnamese", "")
            if w and w not in vocab_map:
                vocab_map[w] = entry

        today_str = date.today().isoformat()
        today_sessions = sessions_by_date.get(today_str, [])

        if today_sessions:
            today_body = "\n".join(
                self._render_session_card(s, vocab_map) for s in today_sessions
            )
        else:
            today_body = '<p class="no-practice">Không luyện tập hôm nay.</p>'

        history_days = sorted(
            [d for d in sessions_by_date if d != today_str],
            reverse=True,
        )[:30]

        history_body = ""
        for day in history_days:
            day_sessions = sessions_by_date[day]
            sc = len(day_sessions)
            wc = sum(len(s.get("vocab_reviewed", [])) for s in day_sessions)
            cards = "\n".join(self._render_session_card(s, vocab_map) for s in day_sessions)
            s_label = "sessions" if sc != 1 else "session"
            history_body += (
                f'<details class="day-details">'
                f'<summary class="day-summary">'
                f'<span class="day-date">{html_lib.escape(day)}</span>'
                f'<span class="day-meta">{sc} {s_label} · {wc} words</span>'
                f'</summary>'
                f'<div class="day-cards">{cards}</div>'
                f'</details>\n'
            )

        if not history_body:
            history_body = '<p class="no-practice">Chưa có lịch sử luyện tập.</p>'

        heatmap_cells = "".join(
            f'<div class="hm-cell level-{c["level"]}" title="{html_lib.escape(self._cell_tip(c))}"></div>\n'
            for c in heatmap
        )

        month_row = self._month_labels(heatmap)

        streak = stats["streak"]
        streak_label = f"{streak} ngày" if streak != 1 else "1 ngày"

        today_display = date.today().strftime("%d %B %Y")

        return (
            "<!DOCTYPE html>\n"
            '<html lang="vi">\n'
            "<head>\n"
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            "<title>Học Tiếng Việt</title>\n"
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:ital,wght@0,400;0,500;0,600;0,700;0,900;1,400;1,500&display=swap" rel="stylesheet">\n'
            f"<style>{_CSS}</style>\n"
            "</head>\n"
            "<body>\n"
            "<header>\n"
            '<span class="mast-stars">★ ★ ★ ★ ★</span>\n'
            '<div class="mast-title">Học Tiếng Việt</div>\n'
            '<div class="mast-rule"></div>\n'
            '<div class="mast-subtitle">Nhật Ký Học Tập Từ Vựng</div>\n'
            f'<div class="mast-date">★ {html_lib.escape(today_display)} ★</div>\n'
            "</header>\n"
            "<main>\n"
            # Stats strip
            '<div class="stats-strip">\n'
            f'  <div class="stat-card"><div class="stat-value">{stats["total_words"]}</div><div class="stat-label">Tổng từ vựng</div></div>\n'
            f'  <div class="stat-card"><div class="stat-value">{stats["sessions_this_week"]}</div><div class="stat-label">Buổi học tuần này</div></div>\n'
            f'  <div class="stat-card"><div class="stat-value">{html_lib.escape(streak_label)}</div><div class="stat-label">Chuỗi liên tiếp</div></div>\n'
            f'  <div class="stat-card"><div class="stat-value">{stats["total_sessions"]}</div><div class="stat-label">Tổng buổi học</div></div>\n'
            "</div>\n"
            + _DIVIDER
            # Today
            + '<section>\n<p class="section-title">Hôm nay</p>\n'
            + today_body + "\n</section>\n"
            + _DIVIDER
            # Heatmap
            + '<section>\n<p class="section-title">16 tuần gần đây</p>\n'
            '<div class="heatmap-wrap">\n'
            f'<div class="heatmap-months">{month_row}</div>\n'
            f'<div class="heatmap-grid">\n{heatmap_cells}</div>\n'
            "</div>\n"
            '<div class="heatmap-legend">'
            '<span>Ít hơn</span>'
            '<div class="legend-cell" style="background:var(--heat-0)"></div>'
            '<div class="legend-cell" style="background:var(--heat-1)"></div>'
            '<div class="legend-cell" style="background:var(--heat-2)"></div>'
            '<div class="legend-cell" style="background:var(--heat-3)"></div>'
            '<div class="legend-cell" style="background:var(--heat-4)"></div>'
            '<span>Nhiều hơn</span>'
            "</div>\n"
            "</section>\n"
            + _DIVIDER
            # History
            + '<section>\n<p class="section-title">Lịch sử luyện tập</p>\n'
            + history_body
            + "</section>\n"
            "</main>\n"
            "<footer>\n"
            f'Cập nhật lần cuối: {html_lib.escape(today_str)} · '
            f'<a href="https://{GITHUB_USERNAME}.github.io">← Trang chủ</a>\n'
            "</footer>\n"
            "</body>\n</html>"
        )

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _render_session_card(self, session: dict, vocab_map: dict) -> str:
        mode = session.get("mode", "")
        topic = html_lib.escape(session.get("topic", ""))

        badge_classes = {
            "quiz": "badge-quiz",
            "exercise": "badge-exercise",
            "conversation": "badge-conversation",
            "lookup": "badge-lookup",
        }
        badge_class = badge_classes.get(mode, "badge-exercise")
        badge_label = mode.capitalize() if mode else "Session"

        score_html = ""
        if mode == "quiz":
            correct = session.get("correct_count", 0)
            total = session.get("cards_presented", 0)
            if total:
                score_html = f'<span class="score">{correct}/{total}</span>'

        vocab_reviewed = session.get("vocab_reviewed", [])
        vocab_html = ""
        for word in vocab_reviewed:
            entry = vocab_map.get(word)
            tag = html_lib.escape(word)
            english_text = html_lib.escape(entry.get("english", "")) if entry else ""
            english_span = (
                f' <span class="vocab-english">— {english_text}</span>' if english_text else ""
            )

            sentence_html = ""
            if entry:
                sents = entry.get("sample_sentences", [])
                if sents:
                    vi = html_lib.escape(sents[0].get("vi", ""))
                    en = html_lib.escape(sents[0].get("en", ""))
                    if vi:
                        sentence_html = f'<p class="sample-vi">{vi}</p>'
                        if en:
                            sentence_html += f'<p class="sample-en">{en}</p>'

            vocab_html += (
                f'<div class="vocab-item">'
                f'<span class="vocab-tag">{tag}</span>{english_span}'
                f'{sentence_html}'
                f'</div>\n'
            )

        vocab_section = f'<div class="vocab-section">{vocab_html}</div>' if vocab_html else ""

        return (
            f'<div class="session-card">'
            f'<div class="session-header">'
            f'<span class="badge {badge_class}">{html_lib.escape(badge_label)}</span>'
            f'<span class="session-topic">{topic}</span>'
            f'{score_html}'
            f'</div>'
            f'{vocab_section}'
            f'</div>\n'
        )

    def _month_labels(self, heatmap: list) -> str:
        parts = []
        seen: set = set()
        for col in range(16):
            idx = col * 7
            label = ""
            if idx < len(heatmap):
                try:
                    d = date.fromisoformat(heatmap[idx]["date"])
                    key = (d.year, d.month)
                    if key not in seen:
                        seen.add(key)
                        label = _MONTHS[d.month - 1]
                except ValueError:
                    pass
            parts.append(f'<span class="hm-month">{html_lib.escape(label)}</span>')
        return "".join(parts)

    @staticmethod
    def _cell_tip(cell: dict) -> str:
        n = cell["count"]
        if n == 0:
            return f"{cell['date']}: no practice"
        return f"{cell['date']}: {n} word{'s' if n != 1 else ''}"


# ------------------------------------------------------------------
# Module-level HTML fragments
# ------------------------------------------------------------------

_DIVIDER = '<div class="divider"></div>\n'
