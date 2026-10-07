from pathlib import Path
from urllib.parse import quote

import httpx


class GitLabClient:
    def __init__(self, base_url: str, project_id: str, token: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.project_id = quote(project_id, safe="")
        self.headers = {"PRIVATE-TOKEN": token}
        self.verify_ssl = verify_ssl

    def upload(self, path: Path, mime_type: str) -> dict:
        with path.open("rb") as handle:
            response = httpx.post(
                f"{self.base_url}/api/v4/projects/{self.project_id}/uploads",
                headers=self.headers,
                files={"file": (path.name, handle, mime_type)},
                verify=self.verify_ssl,
                timeout=30,
            )
        response.raise_for_status()
        return response.json()

    def create_issue(self, title: str, description: str) -> dict:
        response = httpx.post(
            f"{self.base_url}/api/v4/projects/{self.project_id}/issues",
            headers=self.headers,
            data={"title": title, "description": description, "labels": "test-failure"},
            verify=self.verify_ssl,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
