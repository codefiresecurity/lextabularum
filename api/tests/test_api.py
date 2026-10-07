import asyncio

import httpx

from api.app.db import Base, SessionLocal, engine
from api.app.gitlab import GitLabClient
from api.app.main import app
from api.app.models import User
from api.app.security import hash_password


def test_health_endpoint():
    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    asyncio.run(request())


def test_authenticated_import_and_run_workflow(monkeypatch):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(User(username="admin", display_name="Administrator",
                    password_hash=hash_password("a-secure-test-password"), is_admin=True))
        db.commit()

    markdown = """# Plan
\n## Accounts
\n### AC-001 — Sign in (`P0`)
\n1. Open the sign-in page.
2. Enter valid credentials.
\nExpected: The dashboard opens.
""".encode()

    async def workflow():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post("/api/auth/login", json={
                "username": "admin", "password": "a-secure-test-password",
            })
            assert login.status_code == 200
            headers = {"X-CSRF-Token": login.json()["csrf_token"]}

            project = await client.post("/api/projects", headers=headers, json={
                "key": "SAMPLE", "name": "Sample project", "description": "",
                "gitlab_url": "https://gitlab.internal", "gitlab_project_id": "group/sample",
                "gitlab_token": "test-project-token",
            })
            assert project.status_code == 201
            project_id = project.json()["id"]

            imported = await client.post(
                f"/api/projects/{project_id}/imports",
                headers=headers,
                files={"file": ("plan.md", markdown, "text/markdown")},
            )
            assert imported.status_code == 201
            assert imported.json()["created"] == 1

            run = await client.post(f"/api/projects/{project_id}/runs", headers=headers, json={
                "name": "Release acceptance", "description": "", "case_ids": [],
            })
            assert run.status_code == 201
            detail = await client.get(f"/api/projects/{project_id}/runs/{run.json()['id']}")
            run_case = detail.json()["cases"][0]

            result = await client.patch(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/result",
                headers=headers,
                json={"state": "passed", "notes": "Observed expected dashboard."},
            )
            assert result.status_code == 200
            assert result.json()["state"] == "passed"

            evidence = await client.post(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/evidence",
                headers=headers,
                files={"file": ("failure.png", b"\x89PNG\r\n\x1a\nmock-image", "image/png")},
            )
            assert evidence.status_code == 201

            failed = await client.patch(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/result",
                headers=headers,
                json={"state": "failed", "notes": "The dashboard remained blank."},
            )
            assert failed.status_code == 200
            assert failed.json()["gitlab_issue_url"] == "https://gitlab.internal/group/sample/-/issues/17"

    monkeypatch.setattr(GitLabClient, "upload", lambda *args: {"markdown": "![failure](/uploads/failure.png)"})
    monkeypatch.setattr(GitLabClient, "create_issue", lambda *args: {
        "iid": 17, "web_url": "https://gitlab.internal/group/sample/-/issues/17",
    })
    asyncio.run(workflow())
