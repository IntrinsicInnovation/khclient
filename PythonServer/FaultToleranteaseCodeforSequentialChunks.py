SUBCHUNK_SIZE = 5_000_000_000
STALE_TIME = 3600  # 1 hour timeout
#should be like 2 weeks or something, NOT 1 hour

@app.route("/lease", methods=["POST"])
def lease():

    data = request.json
    worker = data["workerId"]
    now = int(time.time())

    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    # 1) Reassign stale
    c.execute("""
        SELECT * FROM subchunks
        WHERE status='assigned'
        AND assigned_at < ?
        LIMIT 1
    """, (now - STALE_TIME,))

    row = c.fetchone()

    if row:
        c.execute("""
            UPDATE subchunks
            SET assigned_to=?, assigned_at=?
            WHERE id=?
        """, (worker, now, row["id"]))

        db.commit()
        return jsonify([dict(row)])

    # 2) Generate new range
    c.execute("SELECT value FROM meta WHERE key='next_key'")
    next_key = int(c.fetchone()["value"], 16)

    start = next_key
    end   = start + SUBCHUNK_SIZE - 1

    # update pointer
    c.execute("""
        UPDATE meta
        SET value=?
        WHERE key='next_key'
    """, (hex(end + 1),))

    # insert subchunk
    c.execute("""
        INSERT INTO subchunks
        (start,end,status,assigned_to,assigned_at)
        VALUES (?,?,?,?,?)
    """, (
        hex(start),
        hex(end),
        'assigned',
        worker,
        now
    ))

    sid = c.lastrowid

    db.commit()
    db.close()

    return jsonify([{
        "subchunkId": sid,
        "start": hex(start),
        "end": hex(end)
    }])
