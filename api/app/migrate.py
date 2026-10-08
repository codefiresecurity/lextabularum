from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .db import engine


def upgrade_database():
    config = Config("alembic.ini")
    tables = set(inspect(engine).get_table_names())
    if tables and "alembic_version" not in tables:
        required = {"users", "projects", "test_cases", "test_runs", "run_cases", "evidence"}
        if not required.issubset(tables):
            missing = ", ".join(sorted(required - tables))
            raise RuntimeError(f"Database is not empty and does not match the baseline schema; missing: {missing}")
        command.stamp(config, "0001")
    command.upgrade(config, "head")


def main():
    upgrade_database()
    print("Database is at the latest migration")


if __name__ == "__main__":
    main()
