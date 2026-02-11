import sqlite3
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

DB = "jobs.db"
SUBCHUNK_SIZE = 5_000_000_000  # 5B keys


def get_db():
    return sqlite3.connect(DB)


@app.route("/lease", methods=["POST"])
def lease():

    data = request.json
    worker = data.get("workerId", "unknown")

    db = get_db()
    db.row_factory = sqlite3.Row
    c = db.cursor()

    # Get next pending chunk
    c.execute("""
        SELECT id, start, end
        FROM chunks
        WHERE status = 'pending'
        ORDER BY id
        LIMIT 1
    """)

    row = c.fetchone()

    if not row:
        return jsonify([])

    chunk_id = row["id"]

    chunk_start = int(row["start"], 16)
    chunk_end   = int(row["end"], 16)

    # Clamp to first 5B subrange
    sub_end = min(chunk_start + SUBCHUNK_SIZE - 1, chunk_end)

    # Mark leased
    c.execute("""
        UPDATE chunks
        SET status='leased',
            worker=?,
            lease_time=?
        WHERE id=?
    """, (worker, int(time.time()), chunk_id))

    db.commit()
    db.close()

    return jsonify([{
        "chunkId": chunk_id,
        "start": hex(chunk_start),
        "end": hex(sub_end)
    }])
