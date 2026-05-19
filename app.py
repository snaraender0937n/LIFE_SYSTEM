from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import datetime, timedelta
import sqlite3
import json
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

from database import init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123_lifesystem")
app.config["DATABASE"] = os.environ.get("DATABASE_PATH", "life.db")

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)

# ================= UTILITY FUNCTIONS =================

def get_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return generate_password_hash(password)

def verify_password(stored_hash, password):
    if stored_hash.startswith(("pbkdf2:", "scrypt:")):
        return check_password_hash(stored_hash, password)
    return stored_hash == password

def upgrade_password_if_plain(user_id, stored_hash, password):
    if not stored_hash.startswith(("pbkdf2:", "scrypt:")):
        conn = get_db()
        conn.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hash_password(password), user_id),
        )
        conn.commit()
        conn.close()

def log_activity(user_id, action, details=""):
    """Log user activities for audit trail"""
    conn = get_db()
    conn.execute(
        "INSERT INTO activity_logs (user_id, action, details) VALUES (?, ?, ?)",
        (user_id, action, details)
    )
    conn.commit()
    conn.close()

def update_streak(user_id):
    """Update user's consistency streak"""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Get or create streak record
    streak = conn.execute(
        "SELECT * FROM user_streaks WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    
    if not streak:
        conn.execute(
            "INSERT INTO user_streaks (user_id, last_activity_date) VALUES (?, ?)",
            (user_id, today)
        )
        conn.commit()
        conn.close()
        return
    
    last_date = streak['last_activity_date']
    
    if last_date == today:
        # Same day, no change
        conn.close()
        return
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    if last_date == yesterday:
        # Consecutive day, increment streak
        new_streak = streak['current_streak'] + 1
        longest = max(new_streak, streak['longest_streak'])
        
        conn.execute(
            """UPDATE user_streaks 
               SET current_streak = ?, longest_streak = ?, last_activity_date = ?, total_days_active = total_days_active + 1
               WHERE user_id = ?""",
            (new_streak, longest, today, user_id)
        )
    else:
        # Break in streak, reset
        conn.execute(
            """UPDATE user_streaks 
               SET current_streak = 1, last_activity_date = ?, total_days_active = total_days_active + 1
               WHERE user_id = ?""",
            (today, user_id)
        )
    
    conn.commit()
    conn.close()

def refresh_user_stats(user_id, date=None):
    """Recalculate and store daily statistics for a user."""
    conn = get_db()
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    plans = conn.execute(
        "SELECT COUNT(*) as count FROM plans WHERE user_id = ? AND date = ?",
        (user_id, date),
    ).fetchone()

    completed = conn.execute(
        """SELECT COUNT(*) as count FROM actual_logs
           WHERE user_id = ? AND date = ? AND status = 'completed'""",
        (user_id, date),
    ).fetchone()

    planned_count = plans["count"]
    completed_count = completed["count"]
    completion_rate = (
        (completed_count / planned_count * 100) if planned_count > 0 else 0
    )

    conn.execute(
        """INSERT INTO user_statistics
           (user_id, date, total_tasks_planned, total_tasks_completed,
            completion_rate, productivity_score)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id, date) DO UPDATE SET
             total_tasks_planned = excluded.total_tasks_planned,
             total_tasks_completed = excluded.total_tasks_completed,
             completion_rate = excluded.completion_rate,
             productivity_score = excluded.productivity_score""",
        (
            user_id,
            date,
            planned_count,
            completed_count,
            completion_rate,
            completion_rate,
        ),
    )
    conn.commit()

    stats = conn.execute(
        "SELECT * FROM user_statistics WHERE user_id = ? AND date = ?",
        (user_id, date),
    ).fetchone()
    conn.close()
    return stats

def get_user_stats(user_id):
    """Get today's statistics, refreshing values first."""
    return refresh_user_stats(user_id)

def require_login(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def time_to_minutes(time_str):
    hours, minutes = map(int, time_str.split(":"))
    return hours * 60 + minutes

def duration_minutes(start, end):
    return max(0, time_to_minutes(end) - time_to_minutes(start))

def calc_efficiency_score(status, actual_start, actual_end, plan=None):
    base_scores = {
        "completed": 100,
        "in_progress": 55,
        "postponed": 25,
        "cancelled": 0,
    }
    score = base_scores.get(status, 0)
    if plan and actual_start and actual_end:
        planned = duration_minutes(plan["planned_start"], plan["planned_end"])
        actual = duration_minutes(actual_start, actual_end)
        if planned > 0:
            ratio = actual / planned
            if 0.85 <= ratio <= 1.15:
                score = min(100, score + 15)
            elif ratio > 1.5:
                score = max(0, score - 10)
            else:
                score = min(100, score + 5)
    return score

def week_start_date(reference=None):
    ref = reference or datetime.now()
    monday = ref - timedelta(days=ref.weekday())
    return monday.strftime("%Y-%m-%d")

def attach_subtasks(conn, plans):
    enriched = []
    for plan in plans:
        plan_dict = dict(plan)
        plan_dict["subtasks"] = conn.execute(
            "SELECT * FROM subtasks WHERE plan_id = ? ORDER BY sort_order, id",
            (plan["id"],),
        ).fetchall()
        enriched.append(plan_dict)
    return enriched

def ensure_weekly_challenges(user_id):
    conn = get_db()
    ws = week_start_date()
    existing = conn.execute(
        "SELECT COUNT(*) as c FROM challenges WHERE user_id = ? AND week_start = ?",
        (user_id, ws),
    ).fetchone()["c"]
    if existing == 0:
        defaults = [
            (
                "Complete 5 tasks",
                "Finish five planned activities this week",
                "tasks",
                5,
                150,
                "medium",
            ),
            (
                "Habit hero",
                "Log 7 habit check-ins across the week",
                "habits",
                7,
                200,
                "hard",
            ),
            (
                "Deep focus",
                "Add 3 high-difficulty plans",
                "hard_plans",
                3,
                120,
                "easy",
            ),
        ]
        for title, desc, metric, target, xp, diff in defaults:
            conn.execute(
                """INSERT INTO challenges
                   (user_id, title, description, metric_type, target_value, xp_reward, difficulty, week_start)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, title, desc, metric, target, xp, diff, ws),
            )
        conn.commit()
    conn.close()

def sync_challenge_progress(user_id, date=None):
    conn = get_db()
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    ws = week_start_date(datetime.strptime(date, "%Y-%m-%d"))

    challenges = conn.execute(
        "SELECT * FROM challenges WHERE user_id = ? AND week_start = ? AND status = 'active'",
        (user_id, ws),
    ).fetchall()

    week_end = (datetime.strptime(ws, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")

    for ch in challenges:
        current = 0
        if ch["metric_type"] == "tasks":
            current = conn.execute(
                """SELECT COUNT(*) as c FROM actual_logs
                   WHERE user_id = ? AND date BETWEEN ? AND ? AND status = 'completed'""",
                (user_id, ws, week_end),
            ).fetchone()["c"]
        elif ch["metric_type"] == "habits":
            current = conn.execute(
                """SELECT COUNT(*) as c FROM habit_logs
                   WHERE user_id = ? AND date BETWEEN ? AND ?""",
                (user_id, ws, week_end),
            ).fetchone()["c"]
        elif ch["metric_type"] == "hard_plans":
            current = conn.execute(
                """SELECT COUNT(*) as c FROM plans
                   WHERE user_id = ? AND date BETWEEN ? AND ? AND difficulty >= 4""",
                (user_id, ws, week_end),
            ).fetchone()["c"]

        status = "completed" if current >= ch["target_value"] else "active"
        conn.execute(
            "UPDATE challenges SET current_value = ?, status = ? WHERE id = ?",
            (current, status, ch["id"]),
        )

    conn.commit()
    conn.close()

def save_subtasks(conn, plan_id, subtasks_raw):
    lines = [line.strip() for line in subtasks_raw.splitlines() if line.strip()]
    for index, title in enumerate(lines):
        conn.execute(
            "INSERT INTO subtasks (plan_id, title, sort_order) VALUES (?, ?, ?)",
            (plan_id, title, index),
        )

# ================= HOME =================

@app.route("/")
def home():
    session.clear()
    return redirect("/login")

# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        # Validation
        if not name or not email or not password:
            error = "All fields are required"
        elif len(password) < 6:
            error = "Password must be at least 6 characters"
        elif "@" not in email:
            error = "Invalid email format"
        else:
            conn = get_db()
            try:
                user_id = conn.execute(
                    "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                    (name, email, hash_password(password)),
                ).lastrowid
                
                # Create streak record
                conn.execute(
                    "INSERT INTO user_streaks (user_id) VALUES (?)",
                    (user_id,)
                )
                
                conn.commit()
                ensure_weekly_challenges(user_id)
                conn.close()
                
                return redirect("/login")
            except sqlite3.IntegrityError:
                conn.close()
                error = "Email already registered"

    return render_template("register.html", error=error)

# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            error = "Email and password required"
        else:
            conn = get_db()

            user = conn.execute(
                "SELECT * FROM users WHERE email=?",
                (email,),
            ).fetchone()

            if user and verify_password(user["password"], password):
                upgrade_password_if_plain(user["id"], user["password"], password)
                session.permanent = True
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                
                log_activity(user["id"], "LOGIN", "User logged in")
                update_streak(user["id"])
                
                conn.close()
                return redirect("/dashboard")
            else:
                error = "Invalid email or password"
                conn.close()

    return render_template("login.html", error=error)

# ================= DASHBOARD =================

@app.route("/dashboard")
@require_login
def dashboard():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()

    # Get plans and actuals
    plans = conn.execute(
        "SELECT * FROM plans WHERE user_id=? AND date=? ORDER BY planned_start",
        (session["user_id"], today)
    ).fetchall()

    actuals = conn.execute(
        "SELECT * FROM actual_logs WHERE user_id=? AND date=? ORDER BY actual_start DESC",
        (session["user_id"], today)
    ).fetchall()
    
    # Get streak
    streak = conn.execute(
        "SELECT * FROM user_streaks WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()
    
    # Get today's stats
    stats = get_user_stats(session["user_id"])
    
    # Get weekly stats
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    weekly_stats = conn.execute(
        """SELECT SUM(total_tasks_completed) as week_completed, 
                  SUM(total_tasks_planned) as week_planned,
                  AVG(completion_rate) as avg_completion
           FROM user_statistics 
           WHERE user_id=? AND date >= ?""",
        (session["user_id"], week_ago)
    ).fetchone()

    plans = attach_subtasks(conn, plans)
    ensure_weekly_challenges(session["user_id"])
    sync_challenge_progress(session["user_id"], today)

    active_goals = conn.execute(
        """SELECT * FROM goals WHERE user_id = ? AND status = 'active'
           ORDER BY target_date LIMIT 3""",
        (session["user_id"],),
    ).fetchall()

    habits = conn.execute(
        "SELECT * FROM habits WHERE user_id = ? ORDER BY name",
        (session["user_id"],),
    ).fetchall()
    habit_done_today = {
        row["habit_id"]
        for row in conn.execute(
            "SELECT habit_id FROM habit_logs WHERE user_id = ? AND date = ?",
            (session["user_id"], today),
        ).fetchall()
    }

    challenges = conn.execute(
        """SELECT * FROM challenges WHERE user_id = ? AND week_start = ?
           ORDER BY status, difficulty""",
        (session["user_id"], week_start_date()),
    ).fetchall()

    total_xp = sum(
        c["xp_reward"] for c in challenges if c["status"] == "completed"
    )

    conn.close()

    return render_template(
        "dashboard.html",
        plans=plans,
        actuals=actuals,
        today=today,
        streak=streak,
        stats=stats,
        weekly_stats=weekly_stats,
        active_goals=active_goals,
        habits=habits,
        habit_done_today=habit_done_today,
        challenges=challenges,
        total_xp=total_xp,
    )

# ================= ADD PLAN =================

@app.route("/add_plan", methods=["GET", "POST"])
@require_login
def add_plan():
    error = None

    if request.method == "POST":
        activity = request.form.get("activity", "").strip()
        planned_start = request.form.get("planned_start", "")
        planned_end = request.form.get("planned_end", "")
        priority = request.form.get("priority", "medium")
        category = request.form.get("category", "general")
        description = request.form.get("description", "").strip()
        difficulty = int(request.form.get("difficulty", 3) or 3)
        energy_level = request.form.get("energy_level", "medium")
        subtasks_raw = request.form.get("subtasks", "")
        is_recurring = 1 if request.form.get("is_recurring") else 0
        difficulty = max(1, min(5, difficulty))

        if not activity or not planned_start or not planned_end:
            error = "All fields required"
        elif planned_start >= planned_end:
            error = "End time must be after start time"
        else:
            today = datetime.now().strftime("%Y-%m-%d")
            conn = get_db()

            plan_id = conn.execute(
                """INSERT INTO plans
                   (user_id, date, activity, planned_start, planned_end, priority, category,
                    description, difficulty, energy_level, is_recurring)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session["user_id"],
                    today,
                    activity,
                    planned_start,
                    planned_end,
                    priority,
                    category,
                    description,
                    difficulty,
                    energy_level,
                    is_recurring,
                ),
            ).lastrowid

            save_subtasks(conn, plan_id, subtasks_raw)
            conn.commit()
            conn.close()

            log_activity(session["user_id"], "ADD_PLAN", f"Added plan: {activity}")
            update_streak(session["user_id"])
            refresh_user_stats(session["user_id"], today)
            sync_challenge_progress(session["user_id"], today)

            return redirect("/dashboard")

    return render_template("add_plan.html", error=error)

# ================= UPDATE ACTUAL =================

@app.route("/update_actual", methods=["GET", "POST"])
@require_login
def update_actual():
    error = None

    if request.method == "POST":
        activity = request.form.get("activity", "").strip()
        actual_start = request.form.get("actual_start", "")
        actual_end = request.form.get("actual_end", "")
        status = request.form.get("status", "")
        notes = request.form.get("notes", "").strip()
        category = request.form.get("category", "general")
        plan_id = request.form.get("plan_id") or None
        if plan_id:
            plan_id = int(plan_id)

        if not activity or not actual_start or not actual_end or not status:
            error = "All required fields must be filled"
        elif actual_start >= actual_end:
            error = "End time must be after start time"
        elif status not in ["completed", "in_progress", "postponed", "cancelled"]:
            error = "Invalid status"
        else:
            today = datetime.now().strftime("%Y-%m-%d")
            conn = get_db()

            linked_plan = None
            if plan_id:
                linked_plan = conn.execute(
                    "SELECT * FROM plans WHERE id = ? AND user_id = ?",
                    (plan_id, session["user_id"]),
                ).fetchone()

            mins = duration_minutes(actual_start, actual_end)
            efficiency_score = calc_efficiency_score(
                status, actual_start, actual_end, linked_plan
            )

            conn.execute(
                """INSERT INTO actual_logs
                   (user_id, date, activity, actual_start, actual_end, status, notes,
                    category, efficiency_score, plan_id, duration_minutes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session["user_id"],
                    today,
                    activity,
                    actual_start,
                    actual_end,
                    status,
                    notes,
                    category,
                    efficiency_score,
                    plan_id,
                    mins,
                ),
            )

            conn.commit()
            conn.close()

            log_activity(session["user_id"], "LOG_ACTIVITY", f"Logged: {activity} - {status}")
            update_streak(session["user_id"])
            refresh_user_stats(session["user_id"], today)
            sync_challenge_progress(session["user_id"], today)

            return redirect("/dashboard")

    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    todays_plans = conn.execute(
        "SELECT id, activity, planned_start, planned_end FROM plans WHERE user_id = ? AND date = ?",
        (session["user_id"], today),
    ).fetchall()
    conn.close()

    return render_template("update_actual.html", error=error, todays_plans=todays_plans)

# ================= DELETE PLAN / ACTUAL =================

@app.route("/delete_plan/<int:plan_id>", methods=["POST"])
@require_login
def delete_plan(plan_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    plan = conn.execute(
        "SELECT * FROM plans WHERE id = ? AND user_id = ?",
        (plan_id, session["user_id"]),
    ).fetchone()
    if plan:
        conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        conn.commit()
        log_activity(session["user_id"], "DELETE_PLAN", f"Deleted plan: {plan['activity']}")
        refresh_user_stats(session["user_id"], today)
    conn.close()
    return redirect("/dashboard")

@app.route("/delete_actual/<int:actual_id>", methods=["POST"])
@require_login
def delete_actual(actual_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    actual = conn.execute(
        "SELECT * FROM actual_logs WHERE id = ? AND user_id = ?",
        (actual_id, session["user_id"]),
    ).fetchone()
    if actual:
        conn.execute("DELETE FROM actual_logs WHERE id = ?", (actual_id,))
        conn.commit()
        log_activity(
            session["user_id"],
            "DELETE_ACTIVITY",
            f"Deleted activity: {actual['activity']}",
        )
        refresh_user_stats(session["user_id"], today)
    conn.close()
    return redirect("/dashboard")

@app.route("/toggle_subtask/<int:subtask_id>", methods=["POST"])
@require_login
def toggle_subtask(subtask_id):
    conn = get_db()
    sub = conn.execute(
        """SELECT s.* FROM subtasks s
           JOIN plans p ON p.id = s.plan_id
           WHERE s.id = ? AND p.user_id = ?""",
        (subtask_id, session["user_id"]),
    ).fetchone()
    if sub:
        new_val = 0 if sub["completed"] else 1
        conn.execute(
            "UPDATE subtasks SET completed = ? WHERE id = ?", (new_val, subtask_id)
        )
        conn.commit()
    conn.close()
    return redirect("/dashboard")

@app.route("/edit_plan/<int:plan_id>", methods=["GET", "POST"])
@require_login
def edit_plan(plan_id):
    conn = get_db()
    plan = conn.execute(
        "SELECT * FROM plans WHERE id = ? AND user_id = ?",
        (plan_id, session["user_id"]),
    ).fetchone()
    if not plan:
        conn.close()
        return redirect("/dashboard")

    error = None
    if request.method == "POST":
        activity = request.form.get("activity", "").strip()
        planned_start = request.form.get("planned_start", "")
        planned_end = request.form.get("planned_end", "")
        priority = request.form.get("priority", "medium")
        category = request.form.get("category", "general")
        description = request.form.get("description", "").strip()
        difficulty = max(1, min(5, int(request.form.get("difficulty", 3) or 3)))
        energy_level = request.form.get("energy_level", "medium")

        if not activity or not planned_start or not planned_end:
            error = "All fields required"
        elif planned_start >= planned_end:
            error = "End time must be after start time"
        else:
            conn.execute(
                """UPDATE plans SET activity=?, planned_start=?, planned_end=?,
                   priority=?, category=?, description=?, difficulty=?, energy_level=?
                   WHERE id=?""",
                (
                    activity,
                    planned_start,
                    planned_end,
                    priority,
                    category,
                    description,
                    difficulty,
                    energy_level,
                    plan_id,
                ),
            )
            conn.execute("DELETE FROM subtasks WHERE plan_id = ?", (plan_id,))
            save_subtasks(conn, plan_id, request.form.get("subtasks", ""))
            conn.commit()
            refresh_user_stats(session["user_id"], plan["date"])
            conn.close()
            return redirect("/dashboard")

    subtasks = conn.execute(
        "SELECT title FROM subtasks WHERE plan_id = ? ORDER BY sort_order, id",
        (plan_id,),
    ).fetchall()
    subtasks_text = "\n".join(s["title"] for s in subtasks)
    conn.close()
    return render_template(
        "edit_plan.html",
        plan=plan,
        subtasks_text=subtasks_text,
        error=error,
    )

# ================= GOALS =================

@app.route("/goals", methods=["GET", "POST"])
@require_login
def goals():
    error = None
    conn = get_db()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "personal")
        target_date = request.form.get("target_date", "")
        priority = request.form.get("priority", "medium")
        progress = float(request.form.get("progress", 0) or 0)
        progress = max(0, min(100, progress))

        if not title:
            error = "Goal title is required"
        else:
            status = "completed" if progress >= 100 else "active"
            conn.execute(
                """INSERT INTO goals
                   (user_id, title, description, category, target_date, progress, status, priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session["user_id"],
                    title,
                    description,
                    category,
                    target_date or None,
                    progress,
                    status,
                    priority,
                ),
            )
            conn.commit()

    goal_list = conn.execute(
        "SELECT * FROM goals WHERE user_id = ? ORDER BY status, target_date",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return render_template("goals.html", goals=goal_list, error=error)

@app.route("/goals/<int:goal_id>/progress", methods=["POST"])
@require_login
def update_goal_progress(goal_id):
    progress = float(request.form.get("progress", 0) or 0)
    progress = max(0, min(100, progress))
    status = "completed" if progress >= 100 else "active"
    conn = get_db()
    conn.execute(
        "UPDATE goals SET progress = ?, status = ? WHERE id = ? AND user_id = ?",
        (progress, status, goal_id, session["user_id"]),
    )
    conn.commit()
    conn.close()
    return redirect("/goals")

# ================= HABITS =================

@app.route("/habits", methods=["GET", "POST"])
@require_login
def habits():
    error = None
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()

    if request.method == "POST":
        action = request.form.get("action", "create")
        if action == "create":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            frequency = request.form.get("frequency", "daily")
            target = int(request.form.get("target_per_week", 7) or 7)
            if not name:
                error = "Habit name is required"
            else:
                conn.execute(
                    """INSERT INTO habits (user_id, name, description, frequency, target_per_week)
                       VALUES (?, ?, ?, ?, ?)""",
                    (session["user_id"], name, description, frequency, target),
                )
                conn.commit()

    habit_list = conn.execute(
        "SELECT * FROM habits WHERE user_id = ? ORDER BY name",
        (session["user_id"],),
    ).fetchall()
    done_today = {
        row["habit_id"]
        for row in conn.execute(
            "SELECT habit_id FROM habit_logs WHERE user_id = ? AND date = ?",
            (session["user_id"], today),
        ).fetchall()
    }
    conn.close()
    return render_template(
        "habits.html",
        habits=habit_list,
        done_today=done_today,
        today=today,
        error=error,
    )

@app.route("/habits/<int:habit_id>/checkin", methods=["POST"])
@require_login
def habit_checkin(habit_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    habit = conn.execute(
        "SELECT * FROM habits WHERE id = ? AND user_id = ?",
        (habit_id, session["user_id"]),
    ).fetchone()
    if habit:
        existing = conn.execute(
            "SELECT id FROM habit_logs WHERE habit_id = ? AND date = ?",
            (habit_id, today),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM habit_logs WHERE habit_id = ? AND date = ?",
                (habit_id, today),
            )
            new_streak = max(0, habit["current_streak"] - 1)
            conn.execute(
                "UPDATE habits SET current_streak = ? WHERE id = ?",
                (new_streak, habit_id),
            )
        else:
            conn.execute(
                "INSERT INTO habit_logs (habit_id, user_id, date) VALUES (?, ?, ?)",
                (habit_id, session["user_id"], today),
            )
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            if habit["last_completed_date"] == yesterday:
                new_streak = habit["current_streak"] + 1
            elif habit["last_completed_date"] == today:
                new_streak = habit["current_streak"]
            else:
                new_streak = 1
            longest = max(new_streak, habit["longest_streak"])
            conn.execute(
                """UPDATE habits SET current_streak = ?, longest_streak = ?,
                   last_completed_date = ? WHERE id = ?""",
                (new_streak, longest, today, habit_id),
            )
        conn.commit()
        sync_challenge_progress(session["user_id"], today)
    conn.close()
    return redirect(request.referrer or "/habits")

# ================= CHALLENGES =================

@app.route("/challenges")
@require_login
def challenges():
    ensure_weekly_challenges(session["user_id"])
    sync_challenge_progress(session["user_id"])
    conn = get_db()
    ws = week_start_date()
    challenge_list = conn.execute(
        "SELECT * FROM challenges WHERE user_id = ? AND week_start = ? ORDER BY difficulty",
        (session["user_id"], ws),
    ).fetchall()
    total_xp = sum(c["xp_reward"] for c in challenge_list if c["status"] == "completed")
    conn.close()
    return render_template(
        "challenges.html",
        challenges=challenge_list,
        week_start=ws,
        total_xp=total_xp,
    )

# ================= ANALYTICS DASHBOARD =================

@app.route("/analytics")
@require_login
def analytics():
    conn = get_db()
    
    # Weekly data
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    weekly_data = conn.execute(
        """SELECT date, total_tasks_completed, total_tasks_planned, completion_rate
           FROM user_statistics
           WHERE user_id = ? AND date >= ?
           ORDER BY date""",
        (session["user_id"], week_ago)
    ).fetchall()
    
    # Monthly data
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    monthly_data = conn.execute(
        """SELECT date, productivity_score, completion_rate
           FROM user_statistics
           WHERE user_id = ? AND date >= ?
           ORDER BY date""",
        (session["user_id"], month_ago)
    ).fetchall()
    
    # Category breakdown
    categories = conn.execute(
        """SELECT category, COUNT(*) as count, 
                  SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed
           FROM actual_logs
           WHERE user_id = ?
           GROUP BY category""",
        (session["user_id"],)
    ).fetchall()
    
    # Streak info
    streak = conn.execute(
        "SELECT * FROM user_streaks WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()
    
    conn.close()
    
    return render_template(
        "analytics.html",
        weekly_data=weekly_data,
        monthly_data=monthly_data,
        categories=categories,
        streak=streak
    )

# ================= USER PROFILE =================

@app.route("/profile", methods=["GET", "POST"])
@require_login
def profile():
    error = None
    success = None

    if request.method == "POST":
        action = request.form.get("action", "")
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (session["user_id"],),
        ).fetchone()

        if action == "change_password":
            current = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")

            if not verify_password(user["password"], current):
                error = "Current password is incorrect"
            elif len(new_password) < 6:
                error = "New password must be at least 6 characters"
            elif new_password != confirm:
                error = "New passwords do not match"
            else:
                conn.execute(
                    "UPDATE users SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (hash_password(new_password), session["user_id"]),
                )
                conn.commit()
                log_activity(session["user_id"], "CHANGE_PASSWORD", "Password updated")
                success = "Password updated successfully"

        elif action == "update_bio":
            bio = request.form.get("bio", "").strip()
            conn.execute(
                "UPDATE users SET bio = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (bio, session["user_id"]),
            )
            conn.commit()
            success = "Bio updated"

        elif action == "delete_account":
            confirm = request.form.get("confirm_delete", "")
            if confirm != "DELETE":
                error = 'Type DELETE to confirm account removal'
            else:
                conn.execute("DELETE FROM users WHERE id = ?", (session["user_id"],))
                conn.commit()
                conn.close()
                session.clear()
                return redirect("/login")

        conn.close()

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()

    streak = conn.execute(
        "SELECT * FROM user_streaks WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        streak=streak,
        error=error,
        success=success,
    )

@app.route("/export_data")
@require_login
def export_data():
    conn = get_db()
    user_id = session["user_id"]

    user_row = conn.execute(
        "SELECT id, name, email, bio, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    streak_row = conn.execute(
        "SELECT * FROM user_streaks WHERE user_id = ?", (user_id,)
    ).fetchone()

    data = {
        "user": dict(user_row) if user_row else {},
        "plans": [
            dict(row)
            for row in conn.execute("SELECT * FROM plans WHERE user_id = ? ORDER BY date DESC", (user_id,)).fetchall()
        ],
        "actual_logs": [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM actual_logs WHERE user_id = ? ORDER BY date DESC", (user_id,)
            ).fetchall()
        ],
        "statistics": [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM user_statistics WHERE user_id = ? ORDER BY date DESC", (user_id,)
            ).fetchall()
        ],
        "streaks": dict(streak_row) if streak_row else {},
    }
    conn.close()

    log_activity(user_id, "EXPORT_DATA", "User exported account data")
    filename = f"life_system_export_{datetime.now().strftime('%Y%m%d')}.json"
    response = jsonify(data)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

# ================= LOGOUT =================

@app.route("/logout")
def logout():
    if "user_id" in session:
        log_activity(session["user_id"], "LOGOUT", "User logged out")
    session.clear()
    return redirect("/login")

# ================= API ENDPOINTS =================

@app.route("/api/stats")
@require_login
def api_stats():
    """JSON API for statistics"""
    conn = get_db()
    
    stats = get_user_stats(session["user_id"])
    streak = conn.execute(
        "SELECT * FROM user_streaks WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()
    
    conn.close()
    
    return jsonify({
        "stats": dict(stats) if stats else {},
        "streak": dict(streak) if streak else {}
    })

# ================= ERROR HANDLING =================

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500

# ================= RUN =================

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
