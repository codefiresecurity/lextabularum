import argparse
from pathlib import Path

from sqlalchemy import select

from api.app.db import SessionLocal
from api.app.importer import import_cases, parse_markdown
from api.app.models import Project


def main():
    parser = argparse.ArgumentParser(description="Import a Markdown test plan into Lex Tabularum")
    parser.add_argument("file", type=Path)
    parser.add_argument("--project", required=True, help="Project key, for example DUTYARC")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without changing the database")
    args = parser.parse_args()

    try:
        parsed = parse_markdown(args.file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(f"Valid: {len(parsed)} cases")
        for item in parsed:
            print(f"  {item.external_id}: {item.title} [{item.priority or 'unprioritized'}]")
        return

    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.key == args.project.upper()))
        if not project:
            parser.error(f"project {args.project!r} does not exist")
        result = import_cases(db, project.id, parsed, args.file.name)
        db.commit()
    print(f"Imported {result['total']} cases: {result['created']} created, "
          f"{result['updated']} updated, {result['unchanged']} unchanged")


if __name__ == "__main__":
    main()

