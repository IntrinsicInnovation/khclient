OLD Lease  for random chunks



@app.route("/lease", methods=["POST"])
def lease():
    reclaim_expired()

    data = request.get_json(force=True)
    worker = data.get("workerId")
    count = int(data.get("count", 1))
    now = int(time.time())

    conn = db()
    c = conn.cursor()

    c.execute("SELECT MAX(id) FROM chunks")
    max_id = c.fetchone()[0]

    if max_id is None:
        return jsonify([])

    leased = []

    for _ in range(count):
        bucket = random.randint(0, BUCKETS - 1)

        bucket_size = max_id // BUCKETS
        bucket_start = bucket * bucket_size
        bucket_end = (bucket + 1) * bucket_size

        c.execute("""
            SELECT id, start, end FROM chunks
            WHERE status='pending'
              AND id BETWEEN ? AND ?
            ORDER BY RANDOM()
            LIMIT 1
        """, (bucket_start, bucket_end))

        row = c.fetchone()
        if not row:
		    c.execute("""
                SELECT id, start, end FROM chunks
                WHERE status='pending'
                ORDER BY RANDOM()
                LIMIT 1
            """)
            row = c.fetchone()
        if not row:
            continue

        c.execute("""
            UPDATE chunks
            SET status='leased', worker=?, heartbeat=?
            WHERE id=?
        """, (worker, now, row["id"]))

        leased.append({
            "chunkId": row["id"],
            "start": row["start"],
            "end": row["end"]
        })

    conn.commit()
    return jsonify(leased)

