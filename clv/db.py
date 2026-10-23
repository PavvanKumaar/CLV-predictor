import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session


def engine(url=None):
    load_dotenv()
    url = url or os.getenv("DATABASE_URL", "sqlite:///data/clv.db")
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    result = create_engine(url)
    if result.dialect.name == "sqlite":
        @event.listens_for(result, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return result


def session(url=None):
    return Session(engine(url))
