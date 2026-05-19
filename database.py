import sqlite3


def _table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _add_column_if_missing(cursor, table_name, column_name, column_def):
    if column_name not in _table_columns(cursor, table_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


def migrate_db(conn=None):
    """Upgrade an existing SQLite database to the current schema."""
    close_conn = False
    if conn is None:
        conn = sqlite3.connect("life.db")
        close_conn = True

    cursor = conn.cursor()
    tables = {row[0] for row in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    if "users" in tables:
        for col, definition in [
            ("avatar", "TEXT DEFAULT 'default.png'"),
            ("bio", "TEXT"),
            ("created_at", "TEXT"),
            ("updated_at", "TEXT"),
        ]:
            _add_column_if_missing(cursor, "users", col, definition)

    if "plans" in tables:
        for col, definition in [
            ("priority", "TEXT DEFAULT 'medium'"),
            ("category", "TEXT DEFAULT 'general'"),
            ("created_at", "TEXT"),
            ("description", "TEXT"),
            ("difficulty", "INTEGER DEFAULT 3"),
            ("energy_level", "TEXT DEFAULT 'medium'"),
            ("is_recurring", "INTEGER DEFAULT 0"),
        ]:
            _add_column_if_missing(cursor, "plans", col, definition)

    if "actual_logs" in tables:
        for col, definition in [
            ("category", "TEXT DEFAULT 'general'"),
            ("efficiency_score", "INTEGER DEFAULT 0"),
            ("created_at", "TEXT"),
            ("updated_at", "TEXT"),
            ("plan_id", "INTEGER"),
            ("duration_minutes", "INTEGER DEFAULT 0"),
        ]:
            _add_column_if_missing(cursor, "actual_logs", col, definition)

    conn.commit()
    if close_conn:
        conn.close()


def init_db():

    conn = sqlite3.connect("life.db")

    cursor = conn.cursor()

    # ================= USERS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        name TEXT NOT NULL,

        email TEXT UNIQUE NOT NULL,

        password TEXT NOT NULL,
        
        avatar TEXT DEFAULT 'default.png',
        
        bio TEXT,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    # ================= USER STREAKS (Consistency) =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_streaks (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_id INTEGER NOT NULL,

        current_streak INTEGER DEFAULT 0,

        longest_streak INTEGER DEFAULT 0,

        last_activity_date TEXT,

        total_days_active INTEGER DEFAULT 0,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

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

        planned_end TEXT,
        
        priority TEXT DEFAULT 'medium',
        
        category TEXT DEFAULT 'general',
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

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

        notes TEXT,
        
        category TEXT DEFAULT 'general',
        
        efficiency_score INTEGER DEFAULT 0,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

    )
    """)

    # ================= USER STATISTICS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_statistics (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_id INTEGER NOT NULL,

        date TEXT,

        total_tasks_planned INTEGER DEFAULT 0,

        total_tasks_completed INTEGER DEFAULT 0,

        total_time_spent INTEGER DEFAULT 0,

        productivity_score FLOAT DEFAULT 0,

        completion_rate FLOAT DEFAULT 0,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        
        UNIQUE(user_id, date)

    )
    """)

    # ================= SUBTASKS (break complex plans into steps) =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subtasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        completed INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
    )
    """)

    # ================= LONG-TERM GOALS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT DEFAULT 'personal',
        target_date TEXT,
        progress REAL DEFAULT 0,
        status TEXT DEFAULT 'active',
        priority TEXT DEFAULT 'medium',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ================= HABITS (recurring complex routines) =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        frequency TEXT DEFAULT 'daily',
        target_per_week INTEGER DEFAULT 7,
        current_streak INTEGER DEFAULT 0,
        longest_streak INTEGER DEFAULT 0,
        last_completed_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS habit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(habit_id, date)
    )
    """)

    # ================= WEEKLY CHALLENGES (gamified complex tasks) =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS challenges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        metric_type TEXT DEFAULT 'tasks',
        target_value INTEGER DEFAULT 5,
        current_value INTEGER DEFAULT 0,
        xp_reward INTEGER DEFAULT 100,
        difficulty TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'active',
        week_start TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ================= ACTIVITY LOGS (for audit trail) =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_id INTEGER NOT NULL,

        action TEXT NOT NULL,

        details TEXT,

        ip_address TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

    )
    """)

    migrate_db(conn)

    conn.commit()
    conn.close()

    print("Database ready.")