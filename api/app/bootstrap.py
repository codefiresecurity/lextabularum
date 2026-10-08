import argparse

from sqlalchemy import select

from .db import SessionLocal
from .migrate import upgrade_database
from .models import User
from .security import hash_password


def main():
    parser = argparse.ArgumentParser(description="Initialize Lex Tabularum and create the first administrator")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    if len(args.password) < 10:
        parser.error("password must contain at least 10 characters")
    upgrade_database()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == args.username.lower())):
            parser.error("user already exists")
        db.add(User(username=args.username.lower(), display_name=args.display_name,
                    password_hash=hash_password(args.password), is_admin=True))
        db.commit()
    print(f"Created administrator {args.username.lower()}")


if __name__ == "__main__":
    main()
