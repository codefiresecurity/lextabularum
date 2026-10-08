# Database migrations

The current production-shaped schema is revision `0001`. Existing installations created with the bootstrap command must be stamped once before applying later migrations:

```bash
.venv/bin/alembic stamp 0001
.venv/bin/alembic upgrade head
```

Fresh installations only run `alembic upgrade head` before creating the first administrator.
