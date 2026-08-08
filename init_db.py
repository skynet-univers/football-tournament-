"""
init_db.py
-----------
Creates the SQLite database (database.db) for the Football Tournament
website. Does NOT seed any fixed teams, matches, or players — everything
is added live through the admin panel (/admin) so any number of teams
can register and the schedule is built as the season goes.

Run this once to (re)build the database:
    python init_db.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")


def create_connection():
    """Create and return a SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn):
    """Create all tables required by the application."""
    cur = conn.cursor()

    # Teams table: core identity + season-long extras (possession, cards).
    # No fixed count — add as many teams as register, via /admin/teams.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            short_name TEXT NOT NULL,
            city TEXT NOT NULL,
            initials TEXT NOT NULL,
            primary_color TEXT NOT NULL,
            secondary_color TEXT NOT NULL,
            avg_possession REAL DEFAULT 50.0,
            yellow_cards INTEGER DEFAULT 0,
            red_cards INTEGER DEFAULT 0
        )
    """)

    # Matches table: fixtures & results.
    # stage: 'league' (weekend group-stage matches that feed the table),
    #        'round_of_16', 'quarterfinal', 'semifinal', 'final' (knockout).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            match_datetime TEXT NOT NULL,
            stadium TEXT NOT NULL,
            matchweek INTEGER NOT NULL,
            stage TEXT NOT NULL DEFAULT 'league',
            status TEXT NOT NULL DEFAULT 'upcoming',  -- upcoming | live | finished
            home_score INTEGER,
            away_score INTEGER,
            minute INTEGER,                            -- current minute if live
            FOREIGN KEY (home_team_id) REFERENCES teams (id),
            FOREIGN KEY (away_team_id) REFERENCES teams (id)
        )
    """)

    # Players table: for the stats page. Added per-team via /admin/players.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            team_id INTEGER NOT NULL,
            position TEXT NOT NULL,     -- Forward | Midfielder | Defender | Goalkeeper
            goals INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            clean_sheets INTEGER DEFAULT 0,
            yellow_cards INTEGER DEFAULT 0,
            red_cards INTEGER DEFAULT 0,
            FOREIGN KEY (team_id) REFERENCES teams (id)
        )
    """)

    conn.commit()


def main():
    if os.path.exists(DB_PATH):
        print(f"Using existing database file at {DB_PATH}")
    conn = create_connection()
    create_schema(conn)
    conn.close()
    print("Database ready:", DB_PATH)
    print("No teams/matches/players are pre-loaded — add them from /admin once the site is running.")


if __name__ == "__main__":
    main()
