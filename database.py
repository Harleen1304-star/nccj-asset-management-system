import sqlite3


DATABASE = "assetsystem.db"


def get_db():

    db = sqlite3.connect(
        DATABASE
    )

    db.row_factory = sqlite3.Row

    asset_columns = {
        row[1]
        for row in db.execute("PRAGMA table_info(assets)").fetchall()
    }

    if asset_columns and "audit_recertified_date" not in asset_columns:
        db.execute(
            "ALTER TABLE assets ADD COLUMN audit_recertified_date DATE"
        )

    if asset_columns and "audit_recertified_by" not in asset_columns:
        db.execute(
            "ALTER TABLE assets ADD COLUMN audit_recertified_by INTEGER"
        )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            request_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(request_id) REFERENCES asset_requests(request_id)
        )
        """
    )

    db.commit()

    return db