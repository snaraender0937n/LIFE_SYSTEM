import sqlite3


def init_db():

    conn = sqlite3.connect("life.db")

    cursor = conn.cursor()

    # ================= USERS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        name TEXT NOT NULL,

        email TEXT UNIQUE NOT NULL,

        password TEXT NOT NULL
    )
    """)

    # ================= PLANS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plans (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_id INTEGER,

        date TEXT,

        activity TEXT,

        planned_start TEXT,

        planned_end TEXT
    )
    """)

    # ================= ACTUAL LOGS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS actual_logs (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_id INTEGER,

        date TEXT,

        activity TEXT,

        actual_start TEXT,

        actual_end TEXT,

        status TEXT,

        notes TEXT
    )
    """)

    conn.commit()

    conn.close()

    print("Database Ready")