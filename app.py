import sqlite3
import os
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_PATH = Path(
    os.environ.get(
        "DATABASE_PATH",
        str(Path(__file__).parent / "visits.db"),
    )
)


def get_database_connection() -> sqlite3.Connection:
    """
    Open a new connection to the SQLite database.

    timeout=10 means SQLite will wait up to 10 seconds if another
    connection temporarily has the database locked.
    """
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)

    # Ask SQLite to wait up to 10 seconds when encountering a lock.
    connection.execute("PRAGMA busy_timeout = 10000")

    return connection


def initialize_database() -> None:
    """
    Create the visits table if it does not already exist.
    """

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = get_database_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                visited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.commit()
    finally:
        connection.close()


@app.route("/")
def home():
    return """
    <h1>Visit Counter</h1>
    <p>Visits are stored in an SQLite database.</p>
    <ul>
        <li><a href="/count">Record a visit</a></li>
        <li><a href="/health">Check server health</a></li>
    </ul>
    """


@app.route("/count")
def count():
    visitor_ip = request.remote_addr or "unknown"

    connection = get_database_connection()

    try:
        # Record this visit.
        connection.execute(
            """
            INSERT INTO visits (ip_address)
            VALUES (?)
            """,
            (visitor_ip,),
        )

        # Save the inserted row permanently.
        connection.commit()

        # COUNT always returns one row containing one number.
        total_result = connection.execute(
            """
            SELECT COUNT(*)
            FROM visits
            """
        ).fetchone()

        unique_result = connection.execute(
            """
            SELECT COUNT(DISTINCT ip_address)
            FROM visits
            """
        ).fetchone()

        # fetchone() returns a tuple such as (7,).
        total_visits = total_result[0]
        unique_ip_count = unique_result[0]

        return jsonify(
            {
                "total_visits": total_visits,
                "unique_ip_count": unique_ip_count,
                "your_ip": visitor_ip,
            }
        )

    except sqlite3.Error as error:
        connection.rollback()

        print(f"Database error in /count: {error}")

        return (
            jsonify(
                {
                    "error": "A database error occurred.",
                    "details": str(error),
                }
            ),
            500,
        )

    finally:
        # This runs whether the request succeeds or fails.
        connection.close()


@app.route("/health")
def health():
    connection = None

    try:
        connection = get_database_connection()
        connection.execute("SELECT 1").fetchone()

        return jsonify(
            {
                "status": "healthy",
                "database": "connected",
            }
        )

    except sqlite3.Error as error:
        print(f"Database error in /health: {error}")

        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "database": "unavailable",
                    "details": str(error),
                }
            ),
            500,
        )

    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    initialize_database()

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True,
    )