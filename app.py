import os
import time

import psycopg
from flask import Flask, jsonify, request
from psycopg.rows import dict_row

app = Flask(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://visituser:visitpassword@localhost:5432/visitcounter",
)


def get_database_connection() -> psycopg.Connection:
    """
    Open a new connection to PostgreSQL.

    dict_row makes query results behave like dictionaries, allowing:
        result["total"]
    instead of:
        result[0]
    """
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    )


def wait_for_database(
    attempts: int = 10,
    delay_seconds: int = 2,
) -> None:
    """
    Wait for PostgreSQL to become available.

    The PostgreSQL container may need a few seconds to initialize.
    Flask should not immediately crash simply because the database is
    still starting.
    """
    for attempt in range(1, attempts + 1):
        try:
            with get_database_connection() as connection:
                connection.execute("SELECT 1")

            print("PostgreSQL is ready.")
            return

        except psycopg.OperationalError as error:
            print(
                f"Database connection attempt "
                f"{attempt}/{attempts} failed: {error}"
            )

            if attempt == attempts:
                raise

            time.sleep(delay_seconds)


def initialize_database() -> None:
    """
    Create the visits table if it does not already exist.
    """
    with get_database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS visits (
                id BIGSERIAL PRIMARY KEY,
                ip_address TEXT NOT NULL,
                visited_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


@app.route("/")
def home():
    return """
    <h1>Visit Counter</h1>
    <p>Visits are now stored in PostgreSQL.</p>
    <ul>
        <li><a href="/count">Record a visit</a></li>
        <li><a href="/health">Check server health</a></li>
    </ul>
    """


@app.route("/count")
def count():
    visitor_ip = request.remote_addr or "unknown"

    try:
        with get_database_connection() as connection:
            connection.execute(
                """
                INSERT INTO visits (ip_address)
                VALUES (%s)
                """,
                (visitor_ip,),
            )

            total_result = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM visits
                """
            ).fetchone()

            unique_result = connection.execute(
                """
                SELECT COUNT(DISTINCT ip_address) AS total
                FROM visits
                """
            ).fetchone()

        return jsonify(
            {
                "total_visits": total_result["total"],
                "unique_ip_count": unique_result["total"],
                "your_ip": visitor_ip,
            }
        )

    except psycopg.Error as error:
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


@app.route("/health")
def health():
    try:
        with get_database_connection() as connection:
            connection.execute("SELECT 1")

        return jsonify(
            {
                "status": "healthy",
                "database": "postgresql",
                "database_status": "connected",
            }
        )

    except psycopg.Error as error:
        print(f"Database health-check error: {error}")

        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "database": "postgresql",
                    "database_status": "unavailable",
                }
            ),
            500,
        )


if __name__ == "__main__":
    wait_for_database()
    initialize_database()

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=False,
    )