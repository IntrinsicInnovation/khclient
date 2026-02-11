import sqlite3

#START = int("700000000000000000", 16)
#END   = int("7fffffffffffffffff", 16)
START = int("dbdd1b55c9e880d5b66ea8b3e8bfe8ef03a41aa9326470b8661e140000000000", 16)
END   = int("dbdd1b55c9e880d5b66ea8b3e8bfe8ef03a41aa9326470b8661e14ffffffffff", 16)
CHUNK_SIZE = 0x1000000000  # ~4 billion per chunk, adjust for 1–6 hours runtime

db = sqlite3.connect("jobs.db")
c = db.cursor()

# clear old chunks
c.execute("DELETE FROM chunks")

i = 0
v = START
while v < END:
    c.execute("""
      INSERT INTO chunks VALUES (?, ?, ?, 'pending', NULL, NULL)
    """, (i, hex(v), hex(min(v + CHUNK_SIZE, END))))
    v += CHUNK_SIZE
    i += 1

db.commit()
print(f"Created {i} chunks")
