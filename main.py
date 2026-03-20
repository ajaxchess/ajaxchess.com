import os
import re
import json as _json
import threading
import uuid
from datetime import date, datetime, timezone
from typing import Optional

import psutil
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import asyncio
import markdown as md_lib
from auth import clear_session, get_current_user, oauth, set_session_user, SECRET_KEY
from fics import FICSSession
from database import BlogComment, ServerStats, UserProfile, get_db, init_db, SessionLocal
import settings as site_settings

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="AjaxChess.com")

# ── Request counter ───────────────────────────────────────────────────────────
_req_lock  = threading.Lock()
_req_count = 0

@app.middleware("http")
async def count_requests(request: Request, call_next):
    global _req_count
    with _req_lock:
        _req_count += 1
    return await call_next(request)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="127.0.0.1")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, https_only=False)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
templates.env.globals["ga_tag"]              = Config(".env")("GA_TAG", default="")
templates.env.globals["DEFAULT_SKIN"]        = site_settings.DEFAULT_SKIN
templates.env.globals["active_skin"]         = site_settings.active_skin
templates.env.globals["solstice_banner"]     = site_settings.solstice_banner
templates.env.globals["equinox_banner"]      = site_settings.equinox_banner
templates.env.globals["chess_day_banner"]    = site_settings.chess_day_banner

# ── Admin emails ──────────────────────────────────────────────────────────────
ADMIN_EMAILS = {"ajaxchess@gmail.com", "ecgero@gmail.com", "gwarpp@gmail.com"}

# ── Error handlers ────────────────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(
        "404.html",
        {"request": request, "mode": "404", "user": get_current_user(request)},
        status_code=404,
    )

@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return templates.TemplateResponse(
        "403.html",
        {"request": request, "mode": "403", "user": get_current_user(request)},
        status_code=403,
    )

# ── SEO ───────────────────────────────────────────────────────────────────────
@app.get("/robots.txt", include_in_schema=False)
async def robots():
    content = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "Disallow: /api/\n"
        "Disallow: /admin/\n\n"
        "Sitemap: https://ajaxchess.com/sitemap.xml\n"
    )
    return PlainTextResponse(content)

@app.get("/ads.txt", include_in_schema=False)
async def ads_txt():
    if os.path.exists("ads.txt"):
        return FileResponse("ads.txt", media_type="text/plain")
    return PlainTextResponse("google.com, pub-8102958922361899, DIRECT, f08c47fec0942fa0")

# ── Main pages ────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "mode": "home",
        "user": get_current_user(request),
    })

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse("privacy.html", {
        "request": request,
        "mode": "privacy",
        "user": get_current_user(request),
    })

@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse("terms.html", {
        "request": request,
        "mode": "terms",
        "user": get_current_user(request),
    })

# ── FICS page ─────────────────────────────────────────────────────────────────
@app.get("/fics", response_class=HTMLResponse)
async def fics_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login?next=/fics", status_code=302)
    return templates.TemplateResponse("fics.html", {
        "request": request,
        "mode":    "fics",
        "user":    user,
    })


@app.websocket("/ws/fics")
async def fics_websocket(websocket: WebSocket):
    await websocket.accept()

    user = websocket.session.get("user")
    if not user:
        await websocket.send_json({"type": "error", "msg": "Authentication required — please sign in."})
        await websocket.close(code=1008)
        return

    session = FICSSession()

    # ── Wait for the browser's connect message ────────────────────────────
    try:
        msg = await asyncio.wait_for(websocket.receive_json(), timeout=30)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        await websocket.close()
        return

    if msg.get("type") != "connect":
        await websocket.close()
        return

    fics_user = (msg.get("fics_user") or "").strip() or "guest"
    fics_pass = msg.get("fics_pass") or ""

    # ── Open TCP connection to FICS and log in ────────────────────────────
    await websocket.send_json({"type": "status", "state": "connecting",
                               "msg": f"Connecting to FICS as {fics_user}…"})
    try:
        transcript = await session.connect(fics_user, fics_pass)
        await websocket.send_json({"type": "data", "text": transcript})
        await websocket.send_json({"type": "status", "state": "connected",
                                   "msg": f"Connected as {fics_user}"})
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "msg": "Connection to FICS timed out."})
        await websocket.close()
        return
    except Exception as e:
        await websocket.send_json({"type": "error", "msg": f"FICS connection failed: {e}"})
        await websocket.close()
        return

    # ── Bidirectional relay ───────────────────────────────────────────────
    async def fics_to_ws():
        """Read from FICS, forward to browser."""
        while True:
            text = await session.read()
            if text is None:
                await websocket.send_json({"type": "status", "state": "disconnected",
                                           "msg": "FICS closed the connection."})
                break
            await websocket.send_json({"type": "data", "text": text})

    async def ws_to_fics():
        """Read from browser, forward to FICS."""
        while True:
            try:
                msg = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            if msg.get("type") == "command":
                await session.send(msg.get("text", ""))
            elif msg.get("type") == "disconnect":
                break

    try:
        await asyncio.gather(fics_to_ws(), ws_to_fics())
    except Exception:
        pass
    finally:
        session.close()
        try:
            await websocket.close()
        except Exception:
            pass


# ── Auth routes ───────────────────────────────────────────────────────────────
@app.get("/auth/login")
async def login(request: Request):
    next_url = request.query_params.get("next", "/")
    request.session["next"] = next_url
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user  = token.get("userinfo")
    if user:
        email = user.get("email", "")
        profile = db.query(UserProfile).filter(UserProfile.email == email).first()
        if not profile:
            profile = UserProfile(
                email=email,
                display_name=user.get("name", "")[:64],
                public_id=str(uuid.uuid4()),
            )
            db.add(profile)
            db.commit()
        elif not profile.public_id:
            profile.public_id = str(uuid.uuid4())
            db.commit()
        set_session_user(request, user, display_name=profile.display_name)

    next_url = request.session.pop("next", "/")
    return RedirectResponse(url=next_url)

@app.get("/auth/logout")
async def logout(request: Request):
    clear_session(request)
    return RedirectResponse(url="/")

# ── Blog ──────────────────────────────────────────────────────────────────────
BLOG_POSTS = [
    {
        "slug":          "welcome-to-ajaxchess",
        "file":          "blog/welcome.md",
        "title":         "Welcome to AjaxChess.com",
        "date":          "2026-03-20",
        "datePublished": "2026-03-20T00:00:00Z",
        "excerpt":       "We're building a world-class online chess platform. Here's what we have planned.",
        "date_display":  "March 20, 2026",
    },
]

_BLOG_INDEX   = BLOG_POSTS
_BLOG_BY_SLUG = {p["slug"]: p for p in _BLOG_INDEX}


def _parse_front_matter(raw: str) -> tuple[dict, str]:
    meta = {}
    raw = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    m = re.match(r"^---\n(.*?\n)---\n", raw, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                meta[key.strip()] = val.strip().strip('"').strip("'")
        raw = raw[m.end():].lstrip("\n")
    return meta, raw


@app.get("/blog", response_class=HTMLResponse)
async def blog_index(request: Request):
    return templates.TemplateResponse("blog_index.html", {
        "request": request,
        "mode": "blog",
        "user": get_current_user(request),
        "posts": _BLOG_INDEX,
    })


@app.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_post(request: Request, slug: str, db: Session = Depends(get_db)):
    post = _BLOG_BY_SLUG.get(slug)
    if not post:
        raise HTTPException(status_code=404)
    raw = open(post["file"], encoding="utf-8").read()
    front_matter, body = _parse_front_matter(raw)
    lines = body.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    html_content = md_lib.markdown("\n".join(lines), extensions=["extra", "sane_lists"])
    date_published = (
        front_matter.get("datePublished")
        or post.get("datePublished")
        or post["date"]
    )
    comments = (
        db.query(BlogComment)
        .filter_by(post_slug=slug, approved=True)
        .order_by(BlogComment.created_at)
        .all()
    )
    return templates.TemplateResponse("blog_post.html", {
        "request":        request,
        "mode":           "blog",
        "user":           get_current_user(request),
        "post":           post,
        "content":        html_content,
        "author":         front_matter.get("author", ""),
        "authorurl":      front_matter.get("authorurl", ""),
        "publisher":      front_matter.get("publisher", ""),
        "og_image":       front_matter.get("image", ""),
        "date_published": date_published,
        "comments":       comments,
    })


@app.post("/api/blog/{slug}/comments")
async def submit_blog_comment(slug: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    if slug not in _BLOG_BY_SLUG:
        raise HTTPException(status_code=404, detail="Post not found")
    data = await request.json()
    body = (data.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Comment body required")
    if len(body) > 2000:
        raise HTTPException(status_code=400, detail="Comment too long (max 2000 chars)")
    comment = BlogComment(
        post_slug=slug,
        user_email=user["email"],
        display_name=user.get("display_name") or user.get("name") or user["email"],
        body=body,
        approved=False,
    )
    db.add(comment)
    db.commit()
    return {"ok": True, "message": "Your comment has been submitted and is awaiting review."}


# ── Admin ─────────────────────────────────────────────────────────────────────
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user or user.get("email") not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Forbidden")

    today = date.today()

    total_users = db.query(func.count()).select_from(UserProfile).scalar() or 0
    new_users_today = (
        db.query(func.count()).select_from(UserProfile)
        .filter(func.date(UserProfile.created_at) == today)
        .scalar() or 0
    )
    pending_comments = db.query(func.count()).select_from(BlogComment).filter_by(approved=False).scalar() or 0
    total_comments   = db.query(func.count()).select_from(BlogComment).scalar() or 0

    return templates.TemplateResponse("admin.html", {
        "request":          request,
        "mode":             "admin",
        "user":             user,
        "today":            today.isoformat(),
        "total_users":      total_users,
        "new_users_today":  new_users_today,
        "pending_comments": pending_comments,
        "total_comments":   total_comments,
    })


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user or user.get("email") not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Forbidden")

    users = db.query(UserProfile).order_by(UserProfile.created_at.desc()).all()
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "mode":    "admin",
        "user":    user,
        "users":   users,
    })


@app.get("/admin/kanban", response_class=HTMLResponse)
def admin_kanban(request: Request):
    user = get_current_user(request)
    if not user or user.get("email") not in ADMIN_EMAILS:
        return RedirectResponse("/", status_code=302)

    kanban_path = os.path.join(os.path.dirname(__file__), "KANBAN.md")
    try:
        text = open(kanban_path).read()
    except FileNotFoundError:
        text = ""

    columns = []
    for block in re.split(r'^## ', text, flags=re.MULTILINE):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        col_name = lines[0].strip()
        cards = []
        for line in lines[1:]:
            line = line.strip()
            if not line.startswith('- '):
                continue
            line = line[2:].strip()
            assignee_match = re.search(r'@(\S+)$', line)
            assignee = assignee_match.group(1) if assignee_match else None
            if assignee:
                line = line[:assignee_match.start()].strip()
            id_match = re.match(r'^([FBD]\d+)\s+', line)
            card_id = id_match.group(1) if id_match else None
            description = line[id_match.end():].strip() if id_match else line
            cards.append({"id": card_id, "description": description, "assignee": assignee})
        columns.append({"name": col_name, "cards": cards})

    return templates.TemplateResponse("admin_kanban.html", {
        "request": request,
        "mode":    "admin",
        "user":    user,
        "columns": columns,
    })


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


@app.get("/admin/operations", response_class=HTMLResponse)
def admin_operations(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user or user.get("email") not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Forbidden")

    disk        = psutil.disk_usage("/")
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem         = psutil.virtual_memory()

    # Database size (MySQL information_schema)
    from sqlalchemy import text as _text
    db_size_bytes = db.execute(
        _text("SELECT SUM(data_length + index_length) "
              "FROM information_schema.tables WHERE table_schema = DATABASE()")
    ).scalar() or 0

    table_counts = {
        "UserProfile":  db.query(func.count()).select_from(UserProfile).scalar() or 0,
        "BlogComment":  db.query(func.count()).select_from(BlogComment).scalar() or 0,
        "ServerStats":  db.query(func.count()).select_from(ServerStats).scalar() or 0,
    }
    total_records = sum(table_counts.values())

    net = psutil.net_io_counters()
    try:
        conns = psutil.net_connections(kind="tcp")
        active_connections = sum(1 for c in conns if c.status == "ESTABLISHED")
    except (psutil.AccessDenied, PermissionError):
        active_connections = None

    # Historical charts (last 48 hourly snapshots)
    history = (
        db.query(ServerStats)
        .order_by(ServerStats.recorded_at.desc())
        .limit(48)
        .all()
    )
    history = list(reversed(history))

    chart_labels   = [r.recorded_at.strftime("%-m/%-d %-I%p") for r in history]
    chart_cpu      = [round(r.cpu_percent, 1)  for r in history]
    chart_mem      = [round(r.mem_percent, 1)  for r in history]
    chart_disk     = [round(r.disk_percent, 1) for r in history]
    chart_db_mb    = [round(r.db_size_mb, 2)   for r in history]
    chart_net_sent = [round((r.net_delta_sent or 0) / (1024 ** 2), 2) for r in history]
    chart_net_recv = [round((r.net_delta_recv or 0) / (1024 ** 2), 2) for r in history]
    chart_requests = [r.http_requests for r in history]

    return templates.TemplateResponse("admin_operations.html", {
        "request":            request,
        "mode":               "admin",
        "user":               user,
        "disk_total":         _fmt_bytes(disk.total),
        "disk_used":          _fmt_bytes(disk.used),
        "disk_free":          _fmt_bytes(disk.free),
        "disk_percent":       disk.percent,
        "cpu_percent":        cpu_percent,
        "mem_total":          _fmt_bytes(mem.total),
        "mem_used":           _fmt_bytes(mem.used),
        "mem_free":           _fmt_bytes(mem.available),
        "mem_percent":        mem.percent,
        "table_counts":       table_counts,
        "total_records":      total_records,
        "db_size":            _fmt_bytes(db_size_bytes),
        "net_bytes_sent":     _fmt_bytes(net.bytes_sent),
        "net_bytes_recv":     _fmt_bytes(net.bytes_recv),
        "net_packets_sent":   f"{net.packets_sent:,}",
        "net_packets_recv":   f"{net.packets_recv:,}",
        "active_connections": active_connections,
        "chart_labels":       _json.dumps(chart_labels),
        "chart_cpu":          _json.dumps(chart_cpu),
        "chart_mem":          _json.dumps(chart_mem),
        "chart_disk":         _json.dumps(chart_disk),
        "chart_db_mb":        _json.dumps(chart_db_mb),
        "chart_net_sent":     _json.dumps(chart_net_sent),
        "chart_net_recv":     _json.dumps(chart_net_recv),
        "chart_requests":     _json.dumps(chart_requests),
    })


@app.get("/admin/blog", response_class=HTMLResponse)
def admin_blog(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user or user.get("email") not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Forbidden")

    pending  = db.query(BlogComment).filter_by(approved=False).order_by(BlogComment.created_at).all()
    approved = db.query(BlogComment).filter_by(approved=True).order_by(BlogComment.created_at.desc()).limit(50).all()
    return templates.TemplateResponse("admin_blog.html", {
        "request":  request,
        "mode":     "admin",
        "user":     user,
        "pending":  pending,
        "approved": approved,
    })


@app.post("/admin/blog/comments/{comment_id}/approve")
def admin_approve_comment(comment_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user or user.get("email") not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Forbidden")
    comment = db.query(BlogComment).filter_by(id=comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Not found")
    comment.approved = True
    db.commit()
    return RedirectResponse("/admin/blog", status_code=303)


@app.post("/admin/blog/comments/{comment_id}/delete")
def admin_delete_comment(comment_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user or user.get("email") not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Forbidden")
    comment = db.query(BlogComment).filter_by(id=comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(comment)
    db.commit()
    return RedirectResponse("/admin/blog", status_code=303)


# ── Background scheduler: hourly server stats ─────────────────────────────────
_prev_net = psutil.net_io_counters()

def collect_server_stats():
    global _req_count, _prev_net
    db = SessionLocal()
    try:
        disk        = psutil.disk_usage("/")
        cpu_percent = psutil.cpu_percent(interval=1)
        mem         = psutil.virtual_memory()
        net         = psutil.net_io_counters()
        from sqlalchemy import text as _text
        _db2 = SessionLocal()
        try:
            db_size_bytes = _db2.execute(
                _text("SELECT SUM(data_length + index_length) "
                      "FROM information_schema.tables WHERE table_schema = DATABASE()")
            ).scalar() or 0
        finally:
            _db2.close()

        with _req_lock:
            reqs = _req_count
            _req_count = 0

        delta_sent = max(0, net.bytes_sent - _prev_net.bytes_sent)
        delta_recv = max(0, net.bytes_recv - _prev_net.bytes_recv)
        _prev_net  = net

        stat = ServerStats(
            cpu_percent   = cpu_percent,
            mem_percent   = mem.percent,
            disk_percent  = disk.percent,
            db_size_mb    = db_size_bytes / (1024 * 1024),
            net_delta_sent= delta_sent,
            net_delta_recv= delta_recv,
            http_requests = reqs,
        )
        db.add(stat)
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()


scheduler = BackgroundScheduler()
scheduler.add_job(collect_server_stats, CronTrigger(minute=0))
scheduler.start()

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
