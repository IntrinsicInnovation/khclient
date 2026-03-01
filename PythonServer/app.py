from flask import Flask, request, jsonify, render_template_string
import pymysql
import time
import os

app = Flask(__name__)

# -------------------------
# CONFIG FROM ENVIRONMENT
# -------------------------
DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")

LEASE_TIMEOUT = 3 * 60 * 60   # 3 hours
TEST_RANGE_SIZE = 1_000_000_500

# -------------------------
# DATABASE CONNECTION
# -------------------------
def db():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor
    )

# -------------------------
# HELPERS
# -------------------------
def reclaim_expired():
    now = int(time.time())
    conn = db()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE chunks
            SET status='pending', worker=NULL
            WHERE status='leased' AND heartbeat < %s
        """, (now - LEASE_TIMEOUT,))
    conn.commit()
    conn.close()

def reclaim_older_than(days):
    seconds = days * 24 * 60 * 60
    cutoff = int(time.time()) - seconds
    conn = db()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE chunks
            SET status='pending', worker=NULL
            WHERE status='leased' AND heartbeat < %s
        """, (cutoff,))
        affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected

# -------------------------
# ROUTES
# -------------------------
@app.route("/")
def home():
    return "KeyHunt server running (MySQL)"

@app.route("/admin/reset_leases", methods=["POST"])
def reset_leases():
    reclaimed = reclaim_older_than(3)
    return jsonify({"ok": True, "reclaimed": reclaimed})

@app.route("/lease", methods=["POST"])
def lease():
    data = request.get_json(force=True)
    worker = data.get("workerId")
    now = int(time.time())

    conn = db()
    with conn.cursor() as cursor:
        cursor.execute("START TRANSACTION")
        cursor.execute("""
            SELECT id, start, end
            FROM chunks
            WHERE status IS NULL OR status='pending'
            ORDER BY id
            LIMIT 1
            FOR UPDATE
        """)
        chunk = cursor.fetchone()
        if not chunk:
            conn.commit()
            conn.close()
            return jsonify([])

        chunk_start = int(chunk["start"], 16)
        chunk_end = int(chunk["end"], 16)
        lease_start = chunk_start
        lease_end = min(chunk_start + TEST_RANGE_SIZE - 1, chunk_end)

        cursor.execute("""
            UPDATE chunks
            SET status='leased', worker=%s, heartbeat=%s
            WHERE id=%s
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
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE chunks
            SET heartbeat=%s
            WHERE id=%s AND worker=%s
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
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE chunks
            SET status='complete'
            WHERE id=%s AND worker=%s
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
    conn = db()
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO found (datetime, workerid, privatekey)
            VALUES (%s, %s, %s)
        """, (
            int(time.time()),
            data.get("workerId"),
            data.get("privateKey")
        ))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/stats")
def stats_route():
    conn = db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM chunks")
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS completed FROM chunks WHERE status='complete'")
        completed = cursor.fetchone()["completed"]

        cursor.execute("SELECT COUNT(*) AS leased FROM chunks WHERE status='leased'")
        leased = cursor.fetchone()["leased"]

        cursor.execute("SELECT COUNT(*) AS pending FROM chunks WHERE status='pending'")
        pending = cursor.fetchone()["pending"]
    conn.close()

    progress = (completed / total * 100) if total else 0
    return jsonify({
        "total": total,
        "completed": completed,
        "leased": leased,
        "pending": pending,
        "progress": round(progress, 3)
    })

# -------------------------
# DASHBOARD (optional)
# -------------------------
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

        <button onclick="resetLeases()" 
                style="padding:10px 20px; font-size:16px; margin:15px;
                       background:#ff4444; color:white; border:none; border-radius:8px;">
            Reset Leases (3+ Days Old)
        </button>

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

        async function resetLeases() {
            if (!confirm("Reclaim leases older than 3 days?")) return;
            let r = await fetch('/admin/reset_leases', { method: 'POST' });
            let result = await r.json();
            alert("Reclaimed " + result.reclaimed + " leases.");
            loadStats();
        }

        loadStats();
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    app.run()