"""
database.py — SQLAlchemy models + MySQL setup for ajaxchess.com.
"""
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from starlette.config import Config

_config = Config(".env")
DB_USER = _config("DB_USER", default="")
DB_PASS = _config("DB_PASS", default="")
DB_HOST = _config("DB_HOST", default="localhost")
DB_NAME = _config("DB_NAME", default="ajaxchess")

if DB_USER:
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # Local development fallback — SQLite
    DATABASE_URL = "sqlite:///./chess.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


# ── Models ────────────────────────────────────────────────────────────────────

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id           = Column(Integer, primary_key=True, index=True)
    email        = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(64), nullable=False, default="")
    public_id    = Column(String(64), unique=True, nullable=True)
    created_at   = Column(DateTime(timezone=True), default=utcnow)


class BlogComment(Base):
    __tablename__ = "blog_comments"

    id           = Column(Integer, primary_key=True, index=True)
    post_slug    = Column(String(128), nullable=False, index=True)
    user_email   = Column(String(255), nullable=False)
    display_name = Column(String(64), nullable=False, default="")
    body         = Column(Text, nullable=False)
    approved     = Column(Boolean, default=False, nullable=False)
    created_at   = Column(DateTime(timezone=True), default=utcnow)


class ServerStats(Base):
    __tablename__ = "server_stats"

    id              = Column(Integer, primary_key=True, index=True)
    recorded_at     = Column(DateTime(timezone=True), default=utcnow)
    cpu_percent     = Column(Float, default=0.0)
    mem_percent     = Column(Float, default=0.0)
    disk_percent    = Column(Float, default=0.0)
    db_size_mb      = Column(Float, default=0.0)
    net_delta_sent  = Column(Integer, default=0)
    net_delta_recv  = Column(Integer, default=0)
    http_requests   = Column(Integer, default=0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
