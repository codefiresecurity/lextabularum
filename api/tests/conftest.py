import atexit
import os
import shutil
import tempfile
from pathlib import Path


database_path = Path(tempfile.gettempdir()) / f"lextabularum-tests-{os.getpid()}.db"
evidence_path = Path(tempfile.gettempdir()) / f"lextabularum-evidence-{os.getpid()}"
evidence_path.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{database_path}"
os.environ["APP_SECRET"] = "automated-test-secret-that-is-long-enough"
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ["EVIDENCE_DIR"] = str(evidence_path)
atexit.register(lambda: database_path.unlink(missing_ok=True))
atexit.register(lambda: shutil.rmtree(evidence_path, ignore_errors=True))
