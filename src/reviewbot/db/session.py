"""Database engine and session management."""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from reviewbot.config import get_settings
from reviewbot.db.models import Base

logger = logging.getLogger("reviewbot.db.session")

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None
_tables_initialized: bool = False


def ensure_tables_created(engine: Engine | None = None) -> None:
    """Ensure database schema and all tables exist in target database."""
    global _tables_initialized
    if not _tables_initialized:
        try:
            target_engine = engine or get_engine()
            Base.metadata.create_all(bind=target_engine)
            _tables_initialized = True
            logger.info("Database tables verified and initialized successfully.")
        except Exception as exc:
            logger.warning("Could not auto-create tables: %s", exc)


def get_engine(database_url: str | None = None) -> Engine:
    """Return singleton SQLAlchemy engine or create one with provided URL."""
    global _engine
    if _engine is None or database_url is not None:
        import os

        url = database_url or os.environ.get("DATABASE_URL") or get_settings().DATABASE_URL
        # SQLite needs specific connect_args for multithreading
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        engine = create_engine(
            url,
            echo=False,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        if database_url is None:
            _engine = engine
        return engine
    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Return singleton sessionmaker."""
    global _SessionFactory
    if _SessionFactory is None or engine is not None:
        target_engine = engine or get_engine()
        ensure_tables_created(target_engine)
        factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=target_engine,
        )
        if engine is None:
            _SessionFactory = factory
        return factory
    return _SessionFactory


@contextmanager
def get_db_session(
    session_factory: sessionmaker[Session] | None = None,
) -> Generator[Session, None, None]:
    """Context manager yielding a transactional database session."""
    factory = session_factory or get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Reset cached engine and session factory."""
    global _engine, _SessionFactory, _tables_initialized
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
        _engine = None
    _SessionFactory = None
    _tables_initialized = False


def ensure_database_exists(database_url: str | None = None) -> None:
    """Ensure target PostgreSQL or MySQL database exists before creating tables."""
    import os

    url_str = database_url or os.environ.get("DATABASE_URL") or get_settings().DATABASE_URL
    if not url_str or url_str.startswith("sqlite") or ":memory:" in url_str:
        return
    if url_str.startswith("mysql"):
        try:
            from sqlalchemy import make_url

            url = make_url(url_str)
            db_name = url.database
            if not db_name:
                return

            import pymysql

            conn = pymysql.connect(
                host=url.host or "127.0.0.1",
                port=url.port or 3306,
                user=url.username or "root",
                password=url.password or "",
                connect_timeout=3,
            )
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
            conn.commit()
            conn.close()
            logger.info("Ensured MySQL database '%s' exists.", db_name)
        except Exception as exc:
            logger.warning("Could not auto-create MySQL database: %s", exc)
        return

    if not url_str.startswith("postgresql"):
        return

    from sqlalchemy import make_url, text

    url = make_url(url_str)
    db_name = url.database
    if not db_name or db_name == "postgres":
        return

    # 1. Quick check if target db is reachable directly
    try:
        test_engine = create_engine(url_str, pool_pre_ping=True)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()
        return
    except Exception as exc:
        logger.info(
            "Direct connection to '%s' failed (%s), attempting creation via maintenance db...",
            db_name,
            exc,
        )

    # 2. Connect to maintenance db 'postgres' with autocommit to create database
    try:
        maintenance_url = url.set(database="postgres")
        m_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
        with m_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :d"),
                {"d": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info("Created PostgreSQL database '%s' successfully.", db_name)
        m_engine.dispose()
    except Exception as exc:
        logger.warning("Could not auto-create database '%s': %s", db_name, exc)


def create_all_tables(engine: Engine | None = None) -> None:
    """Create all tables in the database (useful for testing and initial bootstrap)."""
    target_engine = engine or get_engine()
    ensure_database_exists(str(target_engine.url))
    Base.metadata.create_all(bind=target_engine)
    logger.info("Database schema created successfully.")
