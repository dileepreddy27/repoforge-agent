"""Identical event storage API for SQLite demo and PostgreSQL deployments."""
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
)


class EventStore:
    def __init__(self, url: str):
        self.engine = create_engine(url)
        metadata = MetaData()
        self.events = Table(
            "run_events", metadata,
            Column("id", Integer, primary_key=True),
            Column("run_id", String(40), nullable=False, index=True),
            Column("stage", String(40), nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("payload", JSON, nullable=False),
        )
        metadata.create_all(self.engine)

    def record(self, run_id: str, stage: str, payload: dict):
        with self.engine.begin() as connection:
            connection.execute(insert(self.events).values(
                run_id=run_id, stage=stage, created_at=datetime.now(UTC), payload=payload
            ))

    def read(self, run_id: str) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(self.events).where(
                self.events.c.run_id == run_id
            ).order_by(self.events.c.id)).mappings()
            return [{"stage": r["stage"], "payload": r["payload"]} for r in rows]
