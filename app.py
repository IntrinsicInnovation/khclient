from flask import Flask, request, jsonify, render_template_string
import sqlite3
import time
import random
import os

app = Flask(__name__)

DB = os.path.join(os.path.dirname(__file__), "jobs.db")
LEASE_TIMEOUT = 3 * 60 * 60   # 3 hours
BUCKETS = 8                  # partition count



TEST_RANGE_SIZE = 1_000_000_500  # 200M keys




stats = {
    "found": False,
    "found_by": None,
    "timestamp": None,
    "total_reports": 0
}




# -------------------------
# Database helpers
# -------------------------

def db():
    conn = sqlite3.connect(
        DB,
        timeout=30,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()

    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            start TEXT,
            end TEXT,
            status TEXT,
            worker TEXT,
            heartbeat INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS found (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime INTEGER,
            workerid TEXT,
            privatekey TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()

# -------------------------
# HELPERS
# -------------------------

def reclaim_expired():
    now = int(time.time())
    conn = db()

    conn.execute("""
        UPDATE chunks
        SET status='pending', worker=NULL
        WHERE status='leased' AND heartbeat < ?
    """, (now - LEASE_TIMEOUT,))

    conn.commit()
    conn.close()


# -------------------------
# Routes
# -------------------------

@app.route("/")
def home():
    return "KeyHunt server running"



@app.route("/lease", methods=["POST"])
def lease():

  
    data = request.get_json(force=True)
    worker = data.get("workerId")
    count = int(data.get("count", 1))
    now = int(time.time())
    reclaim_expired()

    conn = db()
    c = conn.cursor()


    # get first non-completed chunk
    c.execute("""
        SELECT *
        FROM chunks
        WHERE status IS NULL
           OR status='pending'
        ORDER BY id
        LIMIT 1
    """)

    chunk = c.fetchone()

    if not chunk:
        conn.close()
        return jsonify([])

    chunk_start = int(chunk["start"],16)
    chunk_end   = int(chunk["end"],16)

    # give only first 200M slice
    lease_start = chunk_start
    lease_end   = min(chunk_start + TEST_RANGE_SIZE - 1,
                      chunk_end)

    c.execute("""
        UPDATE chunks
        SET status='leased', worker=?, heartbeat=?
        WHERE id=? AND (status IS NULL OR status='pending')
    """, (worker, now, chunk["id"]))

    conn.commit()
    conn.close()

    return jsonify([{
        "chunkId": chunk["id"],
        "start": hex(lease_start),
        "end": hex(lease_end)
    }])




@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json(force=True)

    conn = db()
    conn.execute("""
        UPDATE chunks
        SET heartbeat=?
        WHERE id=? AND worker=?
    """, (
        int(time.time()),
        data["chunkId"],
        data["workerId"]
    ))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@app.route("/complete", methods=["POST"])
def complete():
    data = request.get_json(force=True)

    conn = db()
    conn.execute("""
        UPDATE chunks
        SET status='complete'
        WHERE id=? AND worker=?
    """, (
        data["chunkId"],
        data["workerId"]
    ))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})



@app.route("/report_found", methods=["POST"])
def report_found():

    data = request.get_json(force=True)

    worker_id = data.get("workerId", "unknown")
    key = data.get("privateKey", "unknown")

    conn = db()

    conn.execute("""
        INSERT INTO found (datetime, workerid, privatekey)
        VALUES (?, ?, ?)
    """, (
        int(time.time()),
        worker_id,
        key
    ))

    conn.commit()
    conn.close()

    stats["found"] = True
    stats["found_by"] = worker_id
    stats["timestamp"] = time.time()
    stats["total_reports"] += 1

    print(f"\nKEY FOUND by {worker_id}")
    print(f"Key: {key}\n")

    return jsonify({"ok": True})



@app.route("/chunkstats")
def chunkstats():
    conn = db()
    rows = conn.execute("""
        SELECT id, start, end, status, worker, heartbeat
        FROM chunks
        ORDER BY id
    """).fetchall()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "start": r["start"],
            "end": r["end"],
            "status": r["status"],
            "worker": r["worker"],
            "heartbeat": r["heartbeat"]
        })

    return jsonify(result)
    
@app.route("/debug/db")
def debug_db():
    conn = db()
    cur = conn.execute("SELECT COUNT(*) FROM chunks")
    total = cur.fetchone()[0]

    cur = conn.execute("SELECT status, COUNT(*) FROM chunks GROUP BY status")
    counts = {row["status"]: row[1] for row in cur.fetchall()}

    return jsonify({
        "total_chunks": total,
        "by_status": counts
    })



def get_stats():
    conn = db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM chunks")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM chunks WHERE status='complete'")
    completed = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM chunks WHERE status='leased'")
    leased = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM chunks WHERE status='pending'")
    pending = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM found")
    found_count = c.fetchone()[0]

    conn.close()
    
    progress = (completed / total * 100) if total else 0

    return {
        "total": total,
        "completed": completed,
        "leased": leased,
        "pending": pending,
        "progress": round(progress, 3),
        "FOUND count": found_count,
        "Found by": stats["found_by"],
        "timestamp": stats["timestamp"]
    }


@app.route("/stats")
def stats_route():
    return jsonify(get_stats())


# ------------------------
# DASHBOARD PAGE
# ------------------------
@app.route("/dashboard")
def dashboard():

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Keyhunt Dashboard</title>
        <meta http-equiv="refresh" content="10">
        <style>
            body { font-family: Arial; background:#111; color:#eee; text-align:center; }
            .box { padding:20px; margin:20px auto; width:300px; background:#222; border-radius:10px;}
            h1 { color:#00ffa6; }
            .big { font-size:28px; }
        </style>
    </head>
    <body>
        <h1>Keyhunt Progress Dashboard</h1>
        <div id="stats">Loading...</div>

        <script>
        async function loadStats() {
            let r = await fetch('/stats');
            let s = await r.json();

            document.getElementById("stats").innerHTML = `
                <div class='box'>
                    <div>Total Chunks: <span class='big'>${s.total}</span></div>
                    <div>Completed: <span class='big'>${s.completed}</span></div>
                    <div>Leased: <span class='big'>${s.leased}</span></div>
                    <div>Pending: <span class='big'>${s.pending}</span></div>
                    <hr>
                    <div>Progress:</div>
                    <div class='big'>${s.progress}%</div>
                </div>
            `;
        }

        loadStats();
        setInterval(loadStats, 5000);
        </script>
    </body>
    </html>
    """

    return render_template_string(html)

# ------------------------
# RUN
# ------------------------
if __name__ == "__main__":
    app.run()
