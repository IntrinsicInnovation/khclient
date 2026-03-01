import sqlite3
#this is the puzzle range. not the test range.

START = int("700008555555555556", 16)
END   = int("7fffffffffffffffff", 16)
#CHUNK_SIZE = 0x1000000000  # ~4 billion per chunk
CHUNK_SIZE = 0xAAAAAAAAAAAB
             
#			 0x80000000000  - a better size of chunk, suitable for a gtx 5090 or better. should take 5 hours or so to run through.
  #             AAAAAAAAAAAB -- this should work for 10 hours for gtx 4090 or 5090


db = sqlite3.connect("jobs.db")
c = db.cursor()

# clear old chunks
c.execute("DELETE FROM chunks")

i = 0
v = START

COMMIT_EVERY = 1000  # safety + speed

while v < END:
    start_hex = hex(v)
    end_hex   = hex(min(v + CHUNK_SIZE, END))

    c.execute("""
      INSERT INTO chunks VALUES (?, ?, ?, 'pending', NULL, NULL)
    """, (i, start_hex, end_hex))

    #print(f"Created chunk {i}: {start_hex} -> {end_hex}")

    v += CHUNK_SIZE
    i += 1

    if i % COMMIT_EVERY == 0:
        db.commit()
        print(f"Committed {i} chunks so far...")

db.commit()
print(f"\nDone. Created {i} chunks total.")
