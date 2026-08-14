"""
init_db.py
----------
Creates the database schema for the Football Tournament website.

Production / Render:
    Set DATABASE_URL to your Supabase PostgreSQL connection string,
    then run:
        python init_db.py

Local development:
    If DATABASE_URL is not set, the original SQLite database.db is used.
"""

import os
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")


def create_postgres_connection():
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError(
            "psycopg2-binary is required. Add it to requirements.txt."
        ) from exc

    return psycopg2.connect(DATABASE_URL, sslmode="require")


def create_sqlite_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn, postgres=False):
    """Create all tables required by the application."""
    cur = conn.cursor()

    if postgres:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                short_name TEXT NOT NULL,
                city TEXT NOT NULL,
                initials TEXT NOT NULL,
                primary_color TEXT NOT NULL,
                secondary_color TEXT NOT NULL,
                avg_possession DOUBLE PRECISION DEFAULT 50.0,
                yellow_cards INTEGER DEFAULT 0,
                red_cards INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id BIGSERIAL PRIMARY KEY,
                home_team_id BIGINT NOT NULL,
                away_team_id BIGINT NOT NULL,
                match_datetime TEXT NOT NULL,
                stadium TEXT NOT NULL,
                matchweek INTEGER NOT NULL,
                stage TEXT NOT NULL DEFAULT 'league',
                status TEXT NOT NULL DEFAULT 'upcoming',
                home_score INTEGER,
                away_score INTEGER,
                minute INTEGER,
                match_duration INTEGER NOT NULL
                DEFAULT 90,
                extra_time INTEGER NOT NULL
                DEFAULT 0,
                FOREIGN KEY (home_team_id) REFERENCES teams (id),
                FOREIGN KEY (away_team_id) REFERENCES teams (id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                team_id BIGINT NOT NULL,
                position TEXT NOT NULL,
                goals INTEGER DEFAULT 0,
                assists INTEGER DEFAULT 0,
                clean_sheets INTEGER DEFAULT 0,
                yellow_cards INTEGER DEFAULT 0,
                red_cards INTEGER DEFAULT 0,
                FOREIGN KEY (team_id) REFERENCES teams (id)
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_matches_datetime
            ON matches (match_datetime)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_matches_status
            ON matches (status)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_matches_stage
            ON matches (stage)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_players_team
            ON players (team_id)
        """)

    else:
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_team_id INTEGER NOT NULL,
                away_team_id INTEGER NOT NULL,
                match_datetime TEXT NOT NULL,
                stadium TEXT NOT NULL,
                matchweek INTEGER NOT NULL,
                stage TEXT NOT NULL DEFAULT 'league',
                status TEXT NOT NULL DEFAULT 'upcoming',
                home_score INTEGER,
                away_score INTEGER,
                minute INTEGER,
                FOREIGN KEY (home_team_id) REFERENCES teams (id),
                FOREIGN KEY (away_team_id) REFERENCES teams (id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                team_id INTEGER NOT NULL,
                position TEXT NOT NULL,
                goals INTEGER DEFAULT 0,
                assists INTEGER DEFAULT 0,
                clean_sheets INTEGER DEFAULT 0,
                yellow_cards INTEGER DEFAULT 0,
                red_cards INTEGER DEFAULT 0,
                FOREIGN KEY (team_id) REFERENCES teams (id)
            )
        """)

    conn.commit()
    cur.close()


def main():
    if DATABASE_URL:
        print("Using Supabase PostgreSQL from DATABASE_URL")
        conn = create_postgres_connection()
        try:
            create_schema(conn, postgres=True)
        finally:
            conn.close()
        print("Supabase database schema is ready.")
    else:
        print(f"Using local SQLite database: {DB_PATH}")
        conn = create_sqlite_connection()
        try:
            create_schema(conn, postgres=False)
        finally:
            conn.close()
        print("Local SQLite database schema is ready.")

    print("No teams/matches/players are pre-loaded — add them from /admin.")


if __name__ == "__main__":
    main()
