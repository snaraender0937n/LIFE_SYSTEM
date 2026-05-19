# LIFE SYSTEM

An anime-themed personal productivity web application built using Flask, SQLite, HTML, CSS, and JavaScript.

LIFE SYSTEM helps users:
- plan their day,
- log actual activities,
- track habits and streaks,
- manage goals,
- complete weekly challenges,
- and analyze consistency/productivity over time.

---

# Features

## Authentication
- User registration and login
- Hashed password security
- Session-based authentication
- Logout protection

---

## Anime-Themed UI
- Anime backgrounds on every page
- Glassmorphism dashboard design
- Responsive modern UI
- Dynamic dashboard cards

---

## Daily Planning
- Add complex daily plans
- Set:
  - priority
  - category
  - difficulty
  - energy level
- Add subtasks
- Edit/delete plans

---

## Activity Logging
- Log actual completed activities
- Compare planned vs actual work
- Smart efficiency scoring
- Daily productivity tracking

---

## Habit Tracking
- Create habits
- Daily check-ins
- Automatic streak calculation
- Habit consistency monitoring

---

## Goals System
- Long-term goal tracking
- Progress sliders
- Goal completion percentage

---

## Weekly Challenges
- Auto-generated weekly challenges
- XP rewards
- Progress tracking

---

## Dashboard & Analytics
- Completion rate tracking
- Weekly summaries
- XP and streak system
- Productivity analytics
- Quick dashboard insights

---

## Profile Features
- User profile and bio
- Change password
- Export data
- Delete account

---

# Tech Stack

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript

---

# Requirements

- Python 3.10+
- Flask
- Werkzeug

Install dependencies using:

```bash
pip install -r requirements.txt
```

---

# Setup Instructions

## Clone Repository

```bash
git clone YOUR_GITHUB_REPO_LINK
```

---

## Open Project

```bash
cd LIFE_SYSTEM
```

---

## Create Virtual Environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Run Application

```bash
python app.py
```

---

# Open Website

Open browser:

```text
http://127.0.0.1:5000
```

---

# Environment Variables (Optional)

| Variable | Default | Description |
|----------|----------|-------------|
| SECRET_KEY | dev default | Flask session key |
| DATABASE_PATH | life.db | SQLite database file |

---

# Project Structure

```text
LIFE_SYSTEM/
│
├── app.py
├── database.py
├── life.db
├── requirements.txt
├── README.md
│
├── static/
│   ├── style.css
│   ├── bg-login.png
│   ├── bg-register.png
│   ├── bg-dashboard.png
│   ├── screenshots/
│   └── ...
│
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── add_plan.html
│   ├── analytics.html
│   └── ...
│
└── .gitignore
```

---

# Anime Background Themes

| Page | Theme |
|------|-------|
| Login | Monster |
| Register | One Piece |
| Dashboard | Attack on Titan |
| Add Plan | Hogwarts |
| Activity Log | Red Dead Redemption 2 |

---

# Default Workflow

1. Register account
2. Login
3. Add complex daily plan
4. Add habits and goals
5. Log actual activities
6. Complete weekly challenges
7. Review analytics and streaks

---

# Screenshots

## Login Page

Add screenshot here:

```text
static/screenshots/login.png
```

---

## Dashboard

Add screenshot here:

```text
static/screenshots/dashboard.png
```

---

# Future Improvements

- AI productivity suggestions
- Notification/reminder system
- Calendar integration
- Mobile app version
- Dark/light themes
- Cloud database deployment
- Achievement system
- Social productivity sharing

---

# License

This project is developed for educational and learning purposes.

---

# Author

Developed by Naraender 🚀