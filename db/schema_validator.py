"""Database schema migrations wrapper.

This file is kept for backwards compatibility with earlier code that imports
db.schema_validator.validate_and_migrate(). The authoritative migration logic
lives in core.migrations.
"""

from core.migrations import migrate_database

def validate_and_migrate(db_path: str):
    """Backwards-compatible entry point."""
    migrate_database(db_path)
    return True
