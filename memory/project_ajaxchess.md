---
name: ajaxchess_project_overview
description: AjaxChess.com project structure, stack, and key decisions
type: project
---

AjaxChess.com is a chess platform site built with FastAPI + SQLite, modeled on minesweeper.org.

**Why:** Building a chess platform as a separate product from the minesweeper.org project. Same owner (Richard Cross / ajaxchess@gmail.com).

**Stack:**
- Python FastAPI with Jinja2 templates
- SQLite (chess.db) via SQLAlchemy ORM
- Google OAuth via Authlib (same pattern as minesweeper.org)
- uvicorn on port 8001
- Virtual environment at ./venv

**Key files:**
- main.py — FastAPI app (routes, admin, blog, auth)
- auth.py — Google OAuth helpers
- settings.py — astronomical event banners (solstice/equinox/World Chess Day July 20)
- database.py — SQLite models: UserProfile, BlogComment, ServerStats
- KANBAN.md — parsed by /admin/kanban route
- Features.md — feature backlog
- Bugs.md — bug tracking

**Admin emails:** ajaxchess@gmail.com, ecgero@gmail.com, gwarpp@gmail.com
**Run:** venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload

**How to apply:** When working on ajaxchess.com, use this stack and follow the same patterns as minesweeper.org.
