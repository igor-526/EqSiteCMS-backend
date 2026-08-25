from pathlib import Path


def test_callback_migration_has_required_schema_and_downgrade() -> None:
    text = (
        Path(__file__).parents[3]
        / "src/migration/versions/c055bacc0001_add_callback_requests.py"
    ).read_text()
    for token in (
        "callback_request_statuses",
        "callback_requests",
        "equestrian_id",
        "notifications_delivered",
        "ix_callback_requests_tenant_status_created",
        "def downgrade",
    ):
        assert token in text
