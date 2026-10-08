import argparse
import time
from datetime import timedelta

from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import Evidence, utcnow
from .outbox import process_pending


def purge_expired_evidence(db):
    if settings.evidence_retention_days <= 0:
        return 0
    cutoff = utcnow() - timedelta(days=settings.evidence_retention_days)
    items = db.scalars(select(Evidence).where(Evidence.attempt_id.is_not(None), Evidence.purged_at.is_(None),
                                                Evidence.created_at < cutoff).limit(200)).all()
    purged = 0
    for item in items:
        try:
            (settings.evidence_dir / item.stored_name).unlink(missing_ok=True)
            item.purged_at = utcnow()
            purged += 1
        except OSError:
            continue
    db.commit()
    return purged


def main():
    parser = argparse.ArgumentParser(description="Process durable Lex Tabularum integration jobs")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()
    while True:
        with SessionLocal() as db:
            succeeded, failed = process_pending(db)
            purged = purge_expired_evidence(db)
        if succeeded or failed or purged:
            print(f"GitLab outbox: {succeeded} completed, {failed} pending; evidence purged: {purged}")
        if args.once:
            break
        time.sleep(max(2, args.interval))


if __name__ == "__main__":
    main()
