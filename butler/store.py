"""The graveyard: one SQLite row per meal the Taster has eaten."""
import json
import sqlite3
import time
import uuid

from . import config

_SCHEMA = """create table if not exists deaths(
    id text primary key, ts real, meal text, source text, verdict text, cause text,
    last_words text, findings text, vitals text, evidence text, revive_s real, deja_vu text)"""


def _connect():
    connection = sqlite3.connect(config.DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(_SCHEMA)
    return connection


def _to_dict(row, full):
    death = {key: row[key] for key in ("id", "ts", "source", "verdict", "cause", "last_words", "revive_s")}
    death["meal"] = row["meal"] if full else row["meal"][:300]
    death["findings"] = json.loads(row["findings"])
    death["vitals"] = json.loads(row["vitals"])
    if full:
        death["evidence"] = row["evidence"]
        death["deja_vu"] = json.loads(row["deja_vu"])
    return death


def add(meal, source, autopsy, vitals, evidence, revive_seconds, past_lives):
    death_id = uuid.uuid4().hex[:10]
    with _connect() as connection:
        connection.execute("insert into deaths values(?,?,?,?,?,?,?,?,?,?,?,?)", (
            death_id, time.time(), meal, source, autopsy["verdict"], autopsy["cause"],
            autopsy["last_words"], json.dumps(autopsy["findings"]), json.dumps(vitals),
            evidence, revive_seconds, json.dumps(past_lives)))
    return death_id


def recent(limit=200):
    with _connect() as connection:
        rows = connection.execute("select * from deaths order by ts desc limit ?", (limit,)).fetchall()
    return [_to_dict(row, full=False) for row in rows]


def get(death_id):
    with _connect() as connection:
        row = connection.execute("select * from deaths where id=?", (death_id,)).fetchone()
    return _to_dict(row, full=True) if row else None
