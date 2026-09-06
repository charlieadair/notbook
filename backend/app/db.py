from collections.abc import Generator
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite:///{db_path.resolve()}"


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        _sqlite_url(db_path),
        connect_args={"check_same_thread": False},
        future=True,
    )
    return engine


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts "
                "USING fts5(text, chunk_id UNINDEXED)"
            )
        )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db(request: Request) -> Generator[Session, None, None]:
    SessionLocal: sessionmaker[Session] = request.app.state.SessionLocal
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fts_index_chunk(db: Session, chunk_id: str, text_value: str) -> None:
    db.execute(
        text("INSERT INTO chunks_fts (chunk_id, text) VALUES (:chunk_id, :text)"),
        {"chunk_id": chunk_id, "text": text_value},
    )
