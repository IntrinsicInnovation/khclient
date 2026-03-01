import sqlite3
import pymysql
import os

# -------------------------
# SQLITE DATABASE
# -------------------------
sqlite_path = "db.sqlite"
sqlite_conn = sqlite3.connect(sqlite_path)
sqlite_conn.row_factory = sqlite3.Row
sqlite_cur = sqlite_conn.cursor()

# -------------------------
# MYSQL CONNECTION (Azure)
# -------------------------
mysql_conn = pymysql.connect(
    host=os.environ.get("DB_HOST"),
    user=os.environ.get("DB_USER"),
    password=os.environ.get("DB_PASS"),
    database=os.environ.get("DB_NAME"),
    ssl={'ssl': {}},  # <-- this enables SSL
    autocommit=True,
    cursorclass=pymysql.cursors.DictCursor
)
mysql_cur = mysql_conn.cursor()




# -------------------------
# UTILITY FUNCTION
# -------------------------
def migrate_table(table_name, columns):
    print(f"Migrating table {table_name}...")
    
    # Create table in MySQL if it doesn't exist
    col_defs = []
    for col, col_type in columns.items():
        if col_type.upper() in ["INTEGER", "INT"]:
            if col.lower() == "id":
                col_defs.append(f"{col} INT AUTO_INCREMENT PRIMARY KEY")
            else:
                col_defs.append(f"{col} INT")
        elif col_type.upper() in ["TEXT"]:
            col_defs.append(f"{col} TEXT")
        else:
            col_defs.append(f"{col} {col_type}")
    create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(col_defs)});"
    mysql_cur.execute(create_sql)
    
    # Read all rows from SQLite
    sqlite_cur.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cur.fetchall()
    
    if not rows:
        print(f"No rows found for {table_name}, skipping insert.")
        return
    
    # Insert into MySQL
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO {table_name} ({', '.join(columns.keys())}) VALUES ({placeholders})"
    
    for row in rows:
        values = [row[col] for col in columns.keys()]
        mysql_cur.execute(insert_sql, values)
    
    print(f"{len(rows)} rows migrated for {table_name}.")

# -------------------------
# MIGRATE TABLES
# -------------------------
# Adjust types as per your SQLite schema
migrate_table("chunks", {
    "id": "INT",
    "start": "TEXT",
    "end": "TEXT",
    "status": "TEXT",
    "worker": "TEXT",
    "heartbeat": "BIGINT"
})

migrate_table("found", {
    "id": "INT",
    "datetime": "BIGINT",
    "workerid": "TEXT",
    "privatekey": "TEXT"
})

# -------------------------
# CLOSE CONNECTIONS
# -------------------------
sqlite_conn.close()
mysql_conn.close()

print("Migration complete!")