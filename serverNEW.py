from fastapi import FastAPI
import sqlite3
import time
import random
from typing import List

DB = "jobs.db"
LEASE_TIMEOUT = 3 * 60 * 60  # 3 hours
BUCKETS = 8                 # random distribution buckets

app = FastAPI()


# ------------------------
# Database helpers
# ------------------------

def get_db():
    return sqlite3.connect(DB, check_same_thread=False)


@app.on_event("startup")
def startup():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            start TEXT NOT NULL,
            end TEXT NOT NULL,
            status TEXT NOT NULL,
            worker TEXT,
            heartbeat INTEGER
        )
    """)
    conn.commit()
    conn.close()


def reclaim_expired():
    now = int(time.time())
    conn = get_db()
    conn.execute("""
        UPDATE chunks
        SET status='pending', worker=NULL
        WHERE status='leased' AND heartbeat < ?
    """, (now - LEASE_TIMEOUT,))
    conn.commit()
    conn.close()


# ------------------------
# API endpoints
# ------------------------

@app.post("/lease")
def lease(req: dict):
    reclaim_expired()

    worker = req.get("workerId")
    count = int(req.get("count", 1))
    now = int(time.time())

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT MAX(id) FROM chunks")
    max_id = c.fetchone()[0]
    if max_id is None:
        return []

    leased = []

    for _ in range(count):
        bucket = random.randint(0, BUCKETS - 1)
        bucket_start = (max_id // BUCKETS) * bucket
        bucket_end = (max_id // BUCKETS) * (bucket + 1)

        c.execute("""
            SELECT id, start, end
            FROM chunks
            WHERE status='pending'
              AND id BETWEEN ? AND ?
            ORDER BY RANDOM()
            LIMIT 1
        """, (bucket_start, bucket_end))

        row = c.fetchone()
        if not row:
            continue

        c.execute("""
            UPDATE chunks
            SET status='leased', worker=?, heartbeat=?
            WHERE id=?
        """, (worker, now, row[0]))

        leased.append({
            "chunkId": row[0],
            "start": row[1],
            "end": row[2]
        })

    conn.commit()
    conn.close()
    return leased


@app.post("/heartbeat")
def heartbeat(req: dict):
    conn = get_db()
    conn.execute("""
        UPDATE chunks
        SET heartbeat=?
        WHERE id=? AND worker=?
    """, (int(time.time()), req["chunkId"], req["workerId"]))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/complete")
def complete(req: dict):
    conn = get_db()
    conn.execute("""
        UPDATE chunks
        SET status='complete'
        WHERE id=? AND worker=?
    """, (req["chunkId"], req["workerId"]))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/stats")
def stats():
    conn = get_db()
    c = conn.cursor()
    out = {}
    for s in ("pending", "leased", "complete"):
        c.execute("SELECT COUNT(*) FROM chunks WHERE status=?", (s,))
        out[s] = c.fetchone()[0]
    conn.close()
    return out


@app.get("/chunkstats")
def chunkstats():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, start, end, status, worker, heartbeat
        FROM chunks
        ORDER BY id
    """)
    rows = c.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "start": r[1],
            "end": r[2],
            "status": r[3],
            "worker": r[4],
            "heartbeat": r[5],
        }
        for r in rows
    ]


@app.get("/")
def root():
    return {"status": "keyhunt server running"}
