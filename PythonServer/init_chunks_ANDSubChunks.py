import sqlite3

# Puzzle range
START = int("700009000000000002", 16)
END   = int("7fffffffffffffffff", 16)

CHUNK_SIZE    = 0xAAAAAAAAAAAB      # your chunk size
SUBCHUNK_SIZE = 5_000_000_000       # 5 billion keys

db = sqlite3.connect("jobs.db")
c = db.cursor()

# -------- PERFORMANCE PRAGMAs --------
c.execute("PRAGMA journal_mode = WAL;")
c.execute("PRAGMA synchronous = NORMAL;")
c.execute("PRAGMA temp_store = MEMORY;")
c.execute("PRAGMA cache_size = 100000;")  # extra speed boost

# Clear old data
c.execute("DELETE FROM chunks")

chunk_id = 0
v = START

COMMIT_EVERY = 1000

while v <= END:

    chunk_start = v
    chunk_end   = min(v + CHUNK_SIZE - 1, END)

    # --- Subchunks ---
    sub_id = 0
    sv = chunk_start

    while sv <= chunk_end:
        sub_start = sv
        sub_end   = min(sv + SUBCHUNK_SIZE - 1, chunk_end)

        c.execute("""
            INSERT INTO chunks
            VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, NULL)
        """, (
            chunk_id,
            hex(chunk_start),
            hex(chunk_end),
            sub_id,
            hex(sub_start),
            hex(sub_end)
        ))

        sv = sub_end + 1
        sub_id += 1

    chunk_id += 1
    v = chunk_end + 1

    if chunk_id % COMMIT_EVERY == 0:
        db.commit()
        print(f"Committed {chunk_id} chunks...")

db.commit()
db.close()

print(f"\nDone. Created {chunk_id} chunks.")
