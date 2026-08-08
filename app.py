"""
app.py
------
Flask application for the Football Tournament website (ISL-inspired).

Routes:
    /            -> Overview page
    /matches     -> Matches page (upcoming / live / finished)
    /table       -> League table page
    /stats       -> Statistics page
    /api/countdown -> JSON endpoint used by the JS countdown timer

Data is read from database.db (SQLite) via helper functions below.
Run `python init_db.py` once before starting the server.
"""

import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, jsonify, g, request, redirect,
    url_for, session, flash,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)

# SECRET_KEY is needed for admin login sessions + flash messages.
# On real hosting, set this via an environment variable instead of the default.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Admin panel password — CHANGE THIS before deploying, ideally via env var.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


STAGES = ["league", "round_of_16", "quarterfinal", "semifinal", "final"]
STAGE_LABELS = {
    "league": "League Stage",
    "round_of_16": "Round of 16",
    "quarterfinal": "Quarterfinal",
    "semifinal": "Semifinal",
    "final": "Final",
}


def login_required(view):
    """Redirect to the admin login page if not logged in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# ----------------------------------------------------------------------
# Database helpers
# ----------------------------------------------------------------------
def get_db():
    """Open a new database connection if there isn't one for this request."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row  # allows dict-like access to rows
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Close the database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def query_one(sql, params=()):
    return get_db().execute(sql, params).fetchone()


# ----------------------------------------------------------------------
# Domain helper functions
# ----------------------------------------------------------------------
def get_all_teams():
    return {row["id"]: dict(row) for row in query_all("SELECT * FROM teams")}


def compute_standings():
    """
    Build the league table by iterating over all FINISHED matches and
    accumulating played/won/draw/lost/goals for each team.
    Sorted by: Points -> Goal Difference -> Goals Scored.
    """
    teams = get_all_teams()
    stats = {
        tid: {
            "id": tid,
            "name": t["name"],
            "short_name": t["short_name"],
            "initials": t["initials"],
            "primary_color": t["primary_color"],
            "played": 0, "won": 0, "draw": 0, "lost": 0,
            "gf": 0, "ga": 0,
        }
        for tid, t in teams.items()
    }

    # Only league-stage matches feed the table — knockout results (round of 16,
    # quarterfinal, semifinal, final) are shown separately on the bracket.
    finished = query_all(
        "SELECT * FROM matches WHERE status = 'finished' AND stage = 'league'"
    )

    for m in finished:
        h, a = m["home_team_id"], m["away_team_id"]
        hs, as_ = m["home_score"], m["away_score"]
        if hs is None or as_ is None:
            continue

        stats[h]["played"] += 1
        stats[a]["played"] += 1
        stats[h]["gf"] += hs
        stats[h]["ga"] += as_
        stats[a]["gf"] += as_
        stats[a]["ga"] += hs

        if hs > as_:
            stats[h]["won"] += 1
            stats[a]["lost"] += 1
        elif hs < as_:
            stats[a]["won"] += 1
            stats[h]["lost"] += 1
        else:
            stats[h]["draw"] += 1
            stats[a]["draw"] += 1

    table = []
    for s in stats.values():
        s["gd"] = s["gf"] - s["ga"]
        s["points"] = s["won"] * 3 + s["draw"]
        table.append(s)

    # Sort: points desc, GD desc, GF desc, name asc (tie-break for stability)
    table.sort(key=lambda x: (-x["points"], -x["gd"], -x["gf"], x["name"]))

    for i, row in enumerate(table, start=1):
        row["position"] = i

    return table


def format_match(m, teams):
    """Convert a sqlite3.Row match into a template-friendly dict."""
    home = teams[m["home_team_id"]]
    away = teams[m["away_team_id"]]
    dt = datetime.strptime(m["match_datetime"], "%Y-%m-%d %H:%M")
    return {
        "id": m["id"],
        "home": home,
        "away": away,
        "datetime": dt,
        "date_str": dt.strftime("%d %b %Y"),
        "time_str": dt.strftime("%I:%M %p"),
        "stadium": m["stadium"],
        "matchweek": m["matchweek"],
        "stage": m["stage"],
        "stage_label": STAGE_LABELS.get(m["stage"], m["stage"]),
        "status": m["status"],
        "home_score": m["home_score"],
        "away_score": m["away_score"],
        "minute": m["minute"],
    }


def get_matches_by_status(status=None, stage="league"):
    """Fetch matches, optionally filtered by status and/or stage.
    Pass stage=None to include every stage (league + knockout)."""
    teams = get_all_teams()
    sql = "SELECT * FROM matches WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if stage:
        sql += " AND stage = ?"
        params.append(stage)
    sql += " ORDER BY match_datetime ASC"
    rows = query_all(sql, tuple(params))
    return [format_match(m, teams) for m in rows]


def get_knockout_bracket():
    """Group knockout-stage matches by round for the bracket view."""
    teams = get_all_teams()
    bracket = {}
    for stage in ("round_of_16", "quarterfinal", "semifinal", "final"):
        rows = query_all(
            "SELECT * FROM matches WHERE stage = ? ORDER BY match_datetime ASC",
            (stage,),
        )
        bracket[stage] = [format_match(m, teams) for m in rows]
    return bracket


def get_next_match():
    """Return the soonest upcoming (or currently live) match."""
    teams = get_all_teams()
    row = query_one(
        """SELECT * FROM matches
           WHERE status = 'live'
           ORDER BY match_datetime ASC LIMIT 1"""
    )
    if row is None:
        row = query_one(
            """SELECT * FROM matches
               WHERE status = 'upcoming'
               ORDER BY match_datetime ASC LIMIT 1"""
        )
    return format_match(row, teams) if row else None


def get_latest_results(limit=4):
    teams = get_all_teams()
    rows = query_all(
        """SELECT * FROM matches
           WHERE status = 'finished'
           ORDER BY match_datetime DESC LIMIT ?""",
        (limit,),
    )
    return [format_match(m, teams) for m in rows]


def get_top_scorers(limit=8):
    return query_all(
        """SELECT p.name, p.goals, p.assists, t.short_name, t.initials,
                  t.primary_color
           FROM players p JOIN teams t ON p.team_id = t.id
           WHERE p.goals > 0
           ORDER BY p.goals DESC, p.assists DESC LIMIT ?""",
        (limit,),
    )


def get_top_assists(limit=8):
    return query_all(
        """SELECT p.name, p.assists, p.goals, t.short_name, t.initials,
                  t.primary_color
           FROM players p JOIN teams t ON p.team_id = t.id
           WHERE p.assists > 0
           ORDER BY p.assists DESC, p.goals DESC LIMIT ?""",
        (limit,),
    )


def get_top_clean_sheets(limit=8):
    return query_all(
        """SELECT p.name, p.clean_sheets, t.short_name, t.initials,
                  t.primary_color
           FROM players p JOIN teams t ON p.team_id = t.id
           WHERE p.position = 'Goalkeeper' AND p.clean_sheets > 0
           ORDER BY p.clean_sheets DESC LIMIT ?""",
        (limit,),
    )


def get_discipline():
    """Yellow/red cards per team (players + team-level totals combined)."""
    rows = query_all(
        """SELECT t.short_name, t.initials, t.primary_color,
                  t.yellow_cards AS team_yellow, t.red_cards AS team_red
           FROM teams t ORDER BY t.yellow_cards DESC"""
    )
    return rows


def get_team_goal_totals():
    """Total goals scored by each team across finished matches, for charts."""
    table = compute_standings()
    ranked = sorted(table, key=lambda x: -x["gf"])
    return ranked


def get_team_win_totals():
    table = compute_standings()
    ranked = sorted(table, key=lambda x: -x["won"])
    return ranked


def get_team_possession():
    rows = query_all(
        "SELECT short_name, initials, primary_color, avg_possession FROM teams "
        "ORDER BY avg_possession DESC"
    )
    return rows


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------
@app.route("/")
def overview():
    next_match = get_next_match()
    latest_results = get_latest_results(limit=4)
    standings = compute_standings()[:5]  # mini table preview
    return render_template(
        "overview.html",
        active_page="overview",
        next_match=next_match,
        latest_results=latest_results,
        standings=standings,
        now=datetime.now(),
    )


@app.route("/matches")
def matches():
    upcoming = get_matches_by_status("upcoming")
    live = get_matches_by_status("live")
    finished = get_matches_by_status("finished")
    finished.sort(key=lambda m: m["datetime"], reverse=True)
    bracket = get_knockout_bracket()
    return render_template(
        "matches.html",
        active_page="matches",
        upcoming=upcoming,
        live=live,
        finished=finished,
        bracket=bracket,
        stage_labels=STAGE_LABELS,
    )


@app.route("/table")
def table():
    standings = compute_standings()
    return render_template(
        "table.html",
        active_page="table",
        standings=standings,
    )


@app.route("/stats")
def stats():
    return render_template(
        "stats.html",
        active_page="stats",
        top_scorers=get_top_scorers(),
        top_assists=get_top_assists(),
        top_clean_sheets=get_top_clean_sheets(),
        team_goals=get_team_goal_totals(),
        team_wins=get_team_win_totals(),
        team_possession=get_team_possession(),
        discipline=get_discipline(),
    )


@app.route("/api/countdown")
def api_countdown():
    """Returns ISO datetime of the next match, for the JS countdown widget."""
    next_match = get_next_match()
    if not next_match:
        return jsonify({"has_match": False})
    return jsonify({
        "has_match": True,
        "datetime": next_match["datetime"].isoformat(),
        "status": next_match["status"],
        "home": next_match["home"]["short_name"],
        "away": next_match["away"]["short_name"],
    })


# ----------------------------------------------------------------------
# Admin panel
# ----------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            next_url = request.args.get("next") or url_for("admin_dashboard")
            return redirect(next_url)
        error = "Incorrect password."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    teams = get_all_teams()
    all_matches = get_matches_by_status(stage=None)  # every stage, sorted by date asc
    all_matches.sort(key=lambda m: m["datetime"], reverse=True)
    return render_template("admin_dashboard.html", teams=teams, matches=all_matches)


def _match_form_to_db(form):
    """Extract + validate match fields from a submitted form."""
    home_id = form.get("home_team_id")
    away_id = form.get("away_team_id")
    match_date = form.get("match_date")
    match_time = form.get("match_time")
    stadium = form.get("stadium", "").strip()
    stage = form.get("stage", "league")
    status = form.get("status", "upcoming")
    home_score = form.get("home_score") or None
    away_score = form.get("away_score") or None
    minute = form.get("minute") or None

    errors = []
    if not home_id or not away_id:
        errors.append("Please select both teams.")
    elif home_id == away_id:
        errors.append("Home and away teams must be different.")
    if not match_date or not match_time:
        errors.append("Date and time are required.")
    if not stadium:
        errors.append("Stadium is required.")
    if stage not in STAGES:
        errors.append("Invalid stage selected.")

    # Tournament matches are only played on weekends.
    if match_date:
        try:
            parsed_date = datetime.strptime(match_date, "%Y-%m-%d")
            if parsed_date.weekday() not in (5, 6):  # 5=Saturday, 6=Sunday
                errors.append("Matches can only be scheduled on a Saturday or Sunday.")
        except ValueError:
            errors.append("Invalid date format.")

    try:
        matchweek = int(form.get("matchweek") or 1)
    except ValueError:
        matchweek = 1
        errors.append("Matchweek must be a number.")

    if errors:
        return None, errors

    dt_str = f"{match_date} {match_time}"
    return {
        "home_team_id": home_id,
        "away_team_id": away_id,
        "match_datetime": dt_str,
        "stadium": stadium,
        "matchweek": matchweek,
        "stage": stage,
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
        "minute": minute,
    }, None


@app.route("/admin/matches/add", methods=["GET", "POST"])
@login_required
def admin_add_match():
    teams = get_all_teams()
    if request.method == "POST":
        data, errors = _match_form_to_db(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db = get_db()
            db.execute(
                """INSERT INTO matches (home_team_id, away_team_id, match_datetime,
                       stadium, matchweek, stage, status, home_score, away_score, minute)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["home_team_id"], data["away_team_id"], data["match_datetime"],
                 data["stadium"], data["matchweek"], data["stage"], data["status"],
                 data["home_score"], data["away_score"], data["minute"]),
            )
            db.commit()
            flash("Match added successfully.", "success")
            return redirect(url_for("admin_dashboard"))

    return render_template("admin_match_form.html", teams=teams, match=None, action="Add")


@app.route("/admin/matches/<int:match_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_match(match_id):
    teams = get_all_teams()
    row = query_one("SELECT * FROM matches WHERE id = ?", (match_id,))
    if row is None:
        flash("Match not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        data, errors = _match_form_to_db(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db = get_db()
            db.execute(
                """UPDATE matches SET home_team_id=?, away_team_id=?, match_datetime=?,
                       stadium=?, matchweek=?, stage=?, status=?, home_score=?, away_score=?, minute=?
                   WHERE id=?""",
                (data["home_team_id"], data["away_team_id"], data["match_datetime"],
                 data["stadium"], data["matchweek"], data["stage"], data["status"],
                 data["home_score"], data["away_score"], data["minute"], match_id),
            )
            db.commit()
            flash("Match updated successfully.", "success")
            return redirect(url_for("admin_dashboard"))

    dt = datetime.strptime(row["match_datetime"], "%Y-%m-%d %H:%M")
    match = dict(row)
    match["date_part"] = dt.strftime("%Y-%m-%d")
    match["time_part"] = dt.strftime("%H:%M")
    return render_template("admin_match_form.html", teams=teams, match=match, action="Edit")


@app.route("/admin/matches/<int:match_id>/delete", methods=["POST"])
@login_required
def admin_delete_match(match_id):
    db = get_db()
    db.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    db.commit()
    flash("Match deleted.", "success")
    return redirect(url_for("admin_dashboard"))


# ---- Teams: any number of teams can register, no fixed count ----------
def _team_form_to_db(form):
    name = form.get("name", "").strip()
    short_name = form.get("short_name", "").strip()
    city = form.get("city", "").strip()
    initials = form.get("initials", "").strip().upper()
    primary_color = form.get("primary_color", "#1fae5f")
    secondary_color = form.get("secondary_color", "#0a0e0c")

    errors = []
    if not name:
        errors.append("Team name is required.")
    if not short_name:
        errors.append("Short name is required.")
    if not city:
        errors.append("City is required.")
    if not initials or len(initials) > 4:
        errors.append("Initials are required (max 4 characters).")

    if errors:
        return None, errors

    return {
        "name": name, "short_name": short_name, "city": city,
        "initials": initials, "primary_color": primary_color,
        "secondary_color": secondary_color,
    }, None


@app.route("/admin/teams")
@login_required
def admin_teams():
    teams = get_all_teams()
    return render_template("admin_teams.html", teams=teams)


@app.route("/admin/teams/add", methods=["GET", "POST"])
@login_required
def admin_add_team():
    if request.method == "POST":
        data, errors = _team_form_to_db(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db = get_db()
            db.execute(
                """INSERT INTO teams (name, short_name, city, initials,
                       primary_color, secondary_color)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (data["name"], data["short_name"], data["city"], data["initials"],
                 data["primary_color"], data["secondary_color"]),
            )
            db.commit()
            flash(f"{data['name']} added to the tournament.", "success")
            return redirect(url_for("admin_teams"))
    return render_template("admin_team_form.html", team=None, action="Add")


@app.route("/admin/teams/<int:team_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_team(team_id):
    row = query_one("SELECT * FROM teams WHERE id = ?", (team_id,))
    if row is None:
        flash("Team not found.", "error")
        return redirect(url_for("admin_teams"))

    if request.method == "POST":
        data, errors = _team_form_to_db(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db = get_db()
            db.execute(
                """UPDATE teams SET name=?, short_name=?, city=?, initials=?,
                       primary_color=?, secondary_color=? WHERE id=?""",
                (data["name"], data["short_name"], data["city"], data["initials"],
                 data["primary_color"], data["secondary_color"], team_id),
            )
            db.commit()
            flash("Team updated.", "success")
            return redirect(url_for("admin_teams"))

    return render_template("admin_team_form.html", team=dict(row), action="Edit")


@app.route("/admin/teams/<int:team_id>/delete", methods=["POST"])
@login_required
def admin_delete_team(team_id):
    db = get_db()
    in_use = query_one(
        "SELECT COUNT(*) AS c FROM matches WHERE home_team_id=? OR away_team_id=?",
        (team_id, team_id),
    )
    if in_use["c"] > 0:
        flash("Can't delete a team that already has matches scheduled — remove those matches first.", "error")
        return redirect(url_for("admin_teams"))
    db.execute("DELETE FROM players WHERE team_id = ?", (team_id,))
    db.execute("DELETE FROM teams WHERE id = ?", (team_id,))
    db.commit()
    flash("Team removed.", "success")
    return redirect(url_for("admin_teams"))


# ---- Players ------------------------------------------------------------
POSITIONS = ["Forward", "Midfielder", "Defender", "Goalkeeper"]


def get_all_players():
    return query_all(
        """SELECT p.*, t.name AS team_name, t.short_name AS team_short_name
           FROM players p JOIN teams t ON p.team_id = t.id
           ORDER BY t.name, p.name"""
    )


def _player_form_to_db(form):
    name = form.get("name", "").strip()
    team_id = form.get("team_id")
    position = form.get("position", "Forward")

    def _int(field):
        try:
            return int(form.get(field) or 0)
        except ValueError:
            return 0

    errors = []
    if not name:
        errors.append("Player name is required.")
    if not team_id:
        errors.append("Please select a team.")
    if position not in POSITIONS:
        errors.append("Invalid position.")

    if errors:
        return None, errors

    return {
        "name": name, "team_id": team_id, "position": position,
        "goals": _int("goals"), "assists": _int("assists"),
        "clean_sheets": _int("clean_sheets"),
        "yellow_cards": _int("yellow_cards"), "red_cards": _int("red_cards"),
    }, None


@app.route("/admin/players")
@login_required
def admin_players():
    players = get_all_players()
    teams = get_all_teams()
    return render_template("admin_players.html", players=players, teams=teams)


@app.route("/admin/players/add", methods=["GET", "POST"])
@login_required
def admin_add_player():
    teams = get_all_teams()
    if request.method == "POST":
        data, errors = _player_form_to_db(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db = get_db()
            db.execute(
                """INSERT INTO players (name, team_id, position, goals, assists,
                       clean_sheets, yellow_cards, red_cards)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["name"], data["team_id"], data["position"], data["goals"],
                 data["assists"], data["clean_sheets"], data["yellow_cards"],
                 data["red_cards"]),
            )
            db.commit()
            flash(f"{data['name']} added.", "success")
            return redirect(url_for("admin_players"))
    return render_template("admin_player_form.html", teams=teams, player=None, action="Add")


@app.route("/admin/players/<int:player_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_player(player_id):
    teams = get_all_teams()
    row = query_one("SELECT * FROM players WHERE id = ?", (player_id,))
    if row is None:
        flash("Player not found.", "error")
        return redirect(url_for("admin_players"))

    if request.method == "POST":
        data, errors = _player_form_to_db(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db = get_db()
            db.execute(
                """UPDATE players SET name=?, team_id=?, position=?, goals=?,
                       assists=?, clean_sheets=?, yellow_cards=?, red_cards=? WHERE id=?""",
                (data["name"], data["team_id"], data["position"], data["goals"],
                 data["assists"], data["clean_sheets"], data["yellow_cards"],
                 data["red_cards"], player_id),
            )
            db.commit()
            flash("Player updated.", "success")
            return redirect(url_for("admin_players"))

    return render_template("admin_player_form.html", teams=teams, player=dict(row), action="Edit")


@app.route("/admin/players/<int:player_id>/delete", methods=["POST"])
@login_required
def admin_delete_player(player_id):
    db = get_db()
    db.execute("DELETE FROM players WHERE id = ?", (player_id,))
    db.commit()
    flash("Player removed.", "success")
    return redirect(url_for("admin_players"))


# ----------------------------------------------------------------------
# Error handlers
# ----------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("No database.db found — please run `python init_db.py` first.")
    app.run(debug=True, host="0.0.0.0", port=5000)
