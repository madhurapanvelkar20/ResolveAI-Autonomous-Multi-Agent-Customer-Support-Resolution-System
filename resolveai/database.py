"""SQLite persistence and deterministic demo data for ResolveAI."""

import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("data/resolveai.db")


def connect_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection and return rows as dictionaries."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create the support tables if they do not already exist."""
    with connect_db(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'in_progress', 'resolved', 'escalated')),
                channel TEXT NOT NULL DEFAULT 'web'
                    CHECK (channel IN ('web', 'email', 'chat')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'processing'
                    CHECK (status IN ('processing', 'shipped', 'delivered', 'cancelled')),
                total REAL NOT NULL CHECK (total >= 0),
                currency TEXT NOT NULL DEFAULT 'USD',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount >= 0),
                currency TEXT NOT NULL DEFAULT 'USD',
                status TEXT NOT NULL DEFAULT 'paid'
                    CHECK (status IN ('pending', 'paid', 'refunded', 'failed')),
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            );

            CREATE TABLE IF NOT EXISTS ticket_notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
            );

            CREATE TABLE IF NOT EXISTS refunds (
                refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'approved'
                    CHECK (status IN ('approved', 'rejected')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (payment_id) REFERENCES payments(payment_id)
            );

            CREATE TABLE IF NOT EXISTS escalations (
                escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
            );
            """
        )


def seed_demo_data(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Insert predictable synthetic records without overwriting existing data."""
    init_db(db_path)

    with connect_db(db_path) as connection:
        connection.executemany(
            """
            INSERT OR IGNORE INTO customers (customer_id, name, email)
            VALUES (?, ?, ?)
            """,
            [
                ("cust-demo-001", "Alex Morgan", "alex.demo@example.test"),
                ("cust-demo-002", "Jordan Lee", "jordan.demo@example.test"),
            ],
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO tickets
                (ticket_id, customer_id, subject, message, status, channel)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "ticket-demo-001",
                    "cust-demo-001",
                    "Payment taken, order missing",
                    "My payment was deducted but no order was created.",
                    "open",
                    "web",
                ),
                (
                    "ticket-demo-002",
                    "cust-demo-002",
                    "Delivery status",
                    "Please provide an update on my delivery.",
                    "in_progress",
                    "email",
                ),
            ],
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO orders
                (order_id, customer_id, status, total, currency)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("order-demo-001", "cust-demo-001", "processing", 49.99, "USD"),
                ("order-demo-002", "cust-demo-002", "shipped", 25.00, "USD"),
            ],
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO payments
                (payment_id, order_id, amount, currency, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("pay-demo-001", "order-demo-001", 49.99, "USD", "paid"),
                ("pay-demo-002", "order-demo-002", 25.00, "USD", "paid"),
            ],
        )


def fetch_one(
    table: str,
    key_column: str,
    key_value: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    """Fetch one row from an allowlisted table using a parameterized query."""
    allowed = {
        ("customers", "customer_id"),
        ("tickets", "ticket_id"),
        ("orders", "order_id"),
        ("payments", "payment_id"),
    }
    if (table, key_column) not in allowed:
        raise ValueError("Unsupported table or key")

    with connect_db(db_path) as connection:
        row = connection.execute(
            f"SELECT * FROM {table} WHERE {key_column} = ?",
            (key_value,),
        ).fetchone()
        return dict(row) if row else None


def list_tickets(
    customer_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    """List tickets with optional filters and a bounded result count."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    query = "SELECT * FROM tickets WHERE 1 = 1"
    parameters: list[Any] = []

    if customer_id is not None:
        query += " AND customer_id = ?"
        parameters.append(customer_id)
    if status is not None:
        query += " AND status = ?"
        parameters.append(status)

    query += " ORDER BY created_at DESC, ticket_id LIMIT ?"
    parameters.append(limit)

    with connect_db(db_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]


def add_ticket_note(
    ticket_id: str,
    note: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Add an internal note to an existing ticket."""
    with connect_db(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO ticket_notes (ticket_id, note) VALUES (?, ?)",
            (ticket_id, note),
        )
        return int(cursor.lastrowid)


def update_ticket_status(
    ticket_id: str,
    status: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    """Update a ticket status; return False if the ticket does not exist."""
    allowed_statuses = {"open", "in_progress", "resolved", "escalated"}
    if status not in allowed_statuses:
        raise ValueError("Unsupported ticket status")

    with connect_db(db_path) as connection:
        cursor = connection.execute(
            "UPDATE tickets SET status = ? WHERE ticket_id = ?",
            (status, ticket_id),
        )
        return cursor.rowcount == 1


def issue_refund(
    payment_id: str,
    amount: float,
    reason: str,
    max_refund_amount: float = 1000.0,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Record a refund only when the payment and amount pass basic checks."""
    if amount <= 0:
        raise ValueError("Refund amount must be greater than zero")
    if amount > max_refund_amount:
        raise ValueError("Refund amount exceeds the configured limit")
    if not reason.strip():
        raise ValueError("Refund reason cannot be blank")

    with connect_db(db_path) as connection:
        payment = connection.execute(
            "SELECT * FROM payments WHERE payment_id = ?",
            (payment_id,),
        ).fetchone()

        if payment is None:
            raise ValueError("Payment not found")
        if payment["status"] != "paid":
            raise ValueError("Only paid payments can be refunded")

        already_refunded = connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM refunds
            WHERE payment_id = ? AND status = 'approved'
            """,
            (payment_id,),
        ).fetchone()["total"]

        remaining = round(float(payment["amount"]) - float(already_refunded), 2)
        if amount > remaining:
            raise ValueError("Refund amount exceeds the remaining paid amount")

        cursor = connection.execute(
            """
            INSERT INTO refunds (payment_id, amount, reason, status)
            VALUES (?, ?, ?, 'approved')
            """,
            (payment_id, round(amount, 2), reason.strip()),
        )
        refund_id = int(cursor.lastrowid)

        if round(float(already_refunded) + amount, 2) >= float(payment["amount"]):
            connection.execute(
                "UPDATE payments SET status = 'refunded' WHERE payment_id = ?",
                (payment_id,),
            )

        return {
            "refund_id": refund_id,
            "payment_id": payment_id,
            "amount": round(amount, 2),
            "currency": payment["currency"],
            "status": "approved",
        }


def escalate_ticket(
    ticket_id: str,
    reason: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Record a human escalation and mark the ticket escalated."""
    if not reason.strip():
        raise ValueError("Escalation reason cannot be blank")

    with connect_db(db_path) as connection:
        ticket = connection.execute(
            "SELECT ticket_id FROM tickets WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
        if ticket is None:
            raise ValueError("Ticket not found")

        cursor = connection.execute(
            "INSERT INTO escalations (ticket_id, reason) VALUES (?, ?)",
            (ticket_id, reason.strip()),
        )
        connection.execute(
            "UPDATE tickets SET status = 'escalated' WHERE ticket_id = ?",
            (ticket_id,),
        )
        return int(cursor.lastrowid)