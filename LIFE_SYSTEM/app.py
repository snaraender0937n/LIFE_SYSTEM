from flask import Flask, render_template, request, redirect, session
from datetime import datetime
import sqlite3

from database import init_db

app = Flask(__name__)
app.secret_key = "secret123"

app.config["PERMANENT_SESSION_LIFETIME"] = 0


# ================= DATABASE =================

def get_db():

    conn = sqlite3.connect("life.db")
    conn.row_factory = sqlite3.Row

    return conn


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

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        try:

            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, password)
            )

            conn.commit()
            conn.close()

            return redirect("/login")

        except:

            conn.close()
            error = "Email already exists"

    return render_template("register.html", error=error)


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    error = None

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()

        conn.close()

        if user:

            session.permanent = False

            session["user_id"] = user["id"]

            return redirect("/dashboard")

        else:

            error = "Invalid email or password"

    return render_template("login.html", error=error)


# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    today = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()

    plans = conn.execute(
        "SELECT * FROM plans WHERE user_id=? AND date=?",
        (session["user_id"], today)
    ).fetchall()

    actuals = conn.execute(
        "SELECT * FROM actual_logs WHERE user_id=? AND date=?",
        (session["user_id"], today)
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        plans=plans,
        actuals=actuals,
        today=today
    )


# ================= ADD PLAN =================

@app.route("/add_plan", methods=["GET", "POST"])
def add_plan():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        activity = request.form["activity"]
        planned_start = request.form["planned_start"]
        planned_end = request.form["planned_end"]

        today = datetime.now().strftime("%Y-%m-%d")

        conn = get_db()

        conn.execute(
            """
            INSERT INTO plans
            (user_id, date, activity, planned_start, planned_end)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                today,
                activity,
                planned_start,
                planned_end
            )
        )

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_plan.html")


# ================= UPDATE ACTUAL =================

@app.route("/update_actual", methods=["GET", "POST"])
def update_actual():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        activity = request.form["activity"]
        actual_start = request.form["actual_start"]
        actual_end = request.form["actual_end"]
        status = request.form["status"]
        notes = request.form["notes"]

        today = datetime.now().strftime("%Y-%m-%d")

        conn = get_db()

        conn.execute(
            """
            INSERT INTO actual_logs
            (
                user_id,
                date,
                activity,
                actual_start,
                actual_end,
                status,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                today,
                activity,
                actual_start,
                actual_end,
                status,
                notes
            )
        )

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("update_actual.html")


# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ================= RUN =================

if __name__ == "__main__":

    init_db()

    app.run(debug=True)