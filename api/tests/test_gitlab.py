from api.app.gitlab import GitLabClient


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"iid": 1}


def test_gitlab_tls_verification_can_be_disabled(monkeypatch, tmp_path):
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr("api.app.gitlab.httpx.post", fake_post)
    screenshot = tmp_path / "failure.png"
    screenshot.write_bytes(b"image")
    client = GitLabClient("https://gitlab.internal", "group/project", "token", verify_ssl=False)

    client.upload(screenshot, "image/png")
    client.create_issue("Failure", "Details")

    assert len(calls) == 2
    assert all(call["verify"] is False for call in calls)
