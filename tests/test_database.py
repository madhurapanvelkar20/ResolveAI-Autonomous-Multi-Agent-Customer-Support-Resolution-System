from resolveai import database


def test_init_db_creates_tables(tmp_path):
    path = tmp_path / "test.db"
    database.init_db(path)

    with database.connect_db(path) as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert {"customers", "tickets", "orders", "payments", "refunds"} <= tables


def test_seed_is_repeatable(tmp_path):
    path = tmp_path / "test.db"
    database.seed_demo_data(path)
    database.seed_demo_data(path)

    assert database.fetch_one(
        "customers", "customer_id", "cust-demo-001", path
    )["name"] == "Alex Morgan"

    assert len(database.list_tickets(db_path=path)) == 2


def test_unknown_record_returns_none(tmp_path):
    path = tmp_path / "test.db"
    database.init_db(path)

    assert database.fetch_one(
        "tickets", "ticket_id", "missing-ticket", path
    ) is None


def test_refund_cannot_exceed_payment_amount(tmp_path):
    path = tmp_path / "test.db"
    database.seed_demo_data(path)

    try:
        database.issue_refund(
            "pay-demo-001", 999.00, "Incorrect charge", db_path=path
        )
        assert False, "Expected excessive refund to be rejected"
    except ValueError as exc:
        assert "remaining paid amount" in str(exc)


def test_full_refund_updates_payment_status(tmp_path):
    path = tmp_path / "test.db"
    database.seed_demo_data(path)

    result = database.issue_refund(
        "pay-demo-001", 49.99, "Order issue", db_path=path
    )

    assert result["status"] == "approved"
    payment = database.fetch_one("payments", "payment_id", "pay-demo-001", path)
    assert payment["status"] == "refunded"


def test_escalation_updates_ticket(tmp_path):
    path = tmp_path / "test.db"
    database.seed_demo_data(path)

    database.escalate_ticket(
        "ticket-demo-001", "Needs specialist review", db_path=path
    )

    ticket = database.fetch_one(
        "tickets", "ticket_id", "ticket-demo-001", path
    )
    assert ticket["status"] == "escalated"