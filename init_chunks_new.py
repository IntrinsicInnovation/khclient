import sqlite3
import time

START = int("dbdd1b55c9e880d5b66ea8b3e8bfe8ef03a41aa9326470b8661e140000000000", 16)
END   = int("dbdd1b55c9e880d5b66ea8b3e8bfe8ef03a41aa9326470b8661e14ffffffffff", 16)

# ~6-hour chunk for very fast GPUs (adjust if needed)
CHUNK_SIZE = 0x25000000000000   # ~6e14 keys

LOGFILE = "chunk_log.txt"

db = sqlite3.connect("jobs.db")
c = db.cursor()

# clear old chunks
c.execute("DELETE FROM chunks")

def log(msg):
    with open(LOGFILE, "a") as f:
        f.write(f"{time.ctime()} | {msg}\n")

log("---- Chunk generation started ----")

i = 0
v = START

while v < END:
    chunk_end = min(v + CHUNK_SIZE, END)

    c.execute("""
        INSERT INTO chunks VALUES (?, ?, ?, 'pending', NULL, NULL)
    """, (i, hex(v), hex(chunk_end)))

    if i % 10 == 0:
        log(f"{i} chunks created. Current range: {hex(v)} -> {hex(chunk_end)}")

    v = chunk_end + 1
    i += 1

db.commit()
db.close()

log(f"Finished. Total chunks: {i}")
print(f"Created {i} chunks")
