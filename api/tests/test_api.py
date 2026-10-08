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
            admin_id = login.json()["user"]["id"]

            project = await client.post("/api/projects", headers=headers, json={
                "key": "SAMPLE", "name": "Sample project", "description": "",
                "gitlab_url": "https://gitlab.internal", "gitlab_project_id": "group/sample",
                "gitlab_token": "test-project-token",
            })
            assert project.status_code == 201
            project_id = project.json()["id"]

            outsider = await client.post("/api/users", headers=headers, json={
                "username": "outsider", "display_name": "Outside Tester",
                "password": "outside-test-password", "must_change_password": False,
            })
            assert outsider.status_code == 201
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as outsider_client:
                outsider_login = await outsider_client.post("/api/auth/login", json={
                    "username": "outsider", "password": "outside-test-password",
                })
                outsider_headers = {"X-CSRF-Token": outsider_login.json()["csrf_token"]}
                forbidden = await outsider_client.get(f"/api/projects/{project_id}/cases")
                assert forbidden.status_code == 403
                forbidden_delete = await outsider_client.delete(f"/api/projects/{project_id}", headers=outsider_headers)
                assert forbidden_delete.status_code == 403

            imported = await client.post(
                f"/api/projects/{project_id}/imports",
                headers=headers,
                files={"file": ("plan.md", markdown, "text/markdown")},
            )
            assert imported.status_code == 201
            assert imported.json()["created"] == 1
            preview = await client.post(
                f"/api/projects/{project_id}/imports/preview", headers=headers,
                files={"file": ("plan.md", markdown, "text/markdown")},
            )
            assert preview.status_code == 200
            assert preview.json()["unchanged"] == 1

            run = await client.post(f"/api/projects/{project_id}/runs", headers=headers, json={
                "name": "Release acceptance", "description": "", "case_ids": [], "assigned_to": admin_id,
            })
            assert run.status_code == 201
            detail = await client.get(f"/api/projects/{project_id}/runs/{run.json()['id']}")
            run_case = detail.json()["cases"][0]

            result = await client.patch(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/result",
                headers=headers,
                json={"state": "passed", "notes": "Observed expected dashboard.",
                      "lock_version": run_case["lock_version"]},
            )
            assert result.status_code == 200
            assert result.json()["state"] == "passed"

            stale = await client.patch(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/result",
                headers=headers,
                json={"state": "blocked", "notes": "stale", "lock_version": run_case["lock_version"]},
            )
            assert stale.status_code == 409

            retest = await client.post(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/retest",
                headers=headers, json={"lock_version": result.json()["lock_version"]},
            )
            assert retest.status_code == 200
            lock_version = retest.json()["lock_version"]

            evidence = await client.post(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/evidence",
                headers=headers,
                files={"file": ("failure.png", b"\x89PNG\r\n\x1a\nmock-image", "image/png")},
            )
            assert evidence.status_code == 201

            removed = await client.delete(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/evidence/{evidence.json()['id']}",
                headers=headers,
            )
            assert removed.status_code == 200
            assert removed.json()["file_deleted"] is True

            missing_evidence = await client.patch(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/result",
                headers=headers,
                json={"state": "failed", "notes": "The dashboard remained blank.",
                      "lock_version": lock_version},
            )
            assert missing_evidence.status_code == 422

            replacement = await client.post(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/evidence",
                headers=headers,
                files={"file": ("replacement.png", b"\x89PNG\r\n\x1a\nreplacement", "image/png")},
            )
            assert replacement.status_code == 201

            failed = await client.patch(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/result",
                headers=headers,
                json={"state": "failed", "notes": "The dashboard remained blank.",
                      "lock_version": lock_version},
            )
            assert failed.status_code == 200
            assert failed.json()["gitlab_issue_url"] == "https://gitlab.internal/group/sample/-/issues/17"
            history = await client.get(f"/api/projects/{project_id}/runs/{run.json()['id']}")
            assert len(history.json()["cases"][0]["attempts"]) == 2

            closed = await client.patch(f"/api/projects/{project_id}/runs/{run.json()['id']}/status",
                                        headers=headers, json={"status": "closed"})
            assert closed.status_code == 200
            closed_upload = await client.post(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/evidence", headers=headers,
                files={"file": ("late.png", b"\x89PNG\r\n\x1a\nlate", "image/png")},
            )
            assert closed_upload.status_code == 409

            attached = await client.delete(
                f"/api/projects/{project_id}/run-cases/{run_case['id']}/evidence/{replacement.json()['id']}",
                headers=headers,
            )
            assert attached.status_code == 409

            dashboard = await client.get(f"/api/projects/{project_id}/dashboard")
            assert dashboard.status_code == 200
            assert dashboard.json()["recent_runs"][0]["failed"] == 1
            assert dashboard.json()["workload"][0]["display_name"] == "Administrator"

            report = await client.get(f"/api/projects/{project_id}/reports/executions?state=failed")
            assert report.status_code == 200
            assert report.json()["total"] == 1
            assert report.json()["rows"][0]["case_id"] == "AC-001"

            deleted = await client.delete(f"/api/projects/{project_id}", headers=headers)
            assert deleted.status_code == 200
            assert deleted.json()["test_cases"] == 1
            assert deleted.json()["runs"] == 1
            assert deleted.json()["evidence"] == 1
            assert deleted.json()["evidence_file_errors"] == 0
            projects = await client.get("/api/projects")
            assert all(item["id"] != project_id for item in projects.json())

    monkeypatch.setattr(GitLabClient, "upload", lambda *args: {"markdown": "![failure](/uploads/failure.png)"})
    monkeypatch.setattr(GitLabClient, "find_issue", lambda *args: None)
    monkeypatch.setattr(GitLabClient, "create_issue", lambda *args: {
        "iid": 17, "web_url": "https://gitlab.internal/group/sample/-/issues/17",
    })
    asyncio.run(workflow())
