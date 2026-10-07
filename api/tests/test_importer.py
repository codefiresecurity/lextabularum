from api.app.importer import parse_markdown


SAMPLE = """# Product plan

## Authentication

### AU-001 — Valid login (`P0`)

1. Open the login screen.
2. Submit valid credentials.

Expected: The dashboard opens.

### AU-002 — Locked account (`P1`, planned)

1. Submit credentials for a locked account.

Expected: Access is denied without revealing account details.
"""


def test_parse_markdown_cases():
    cases = parse_markdown(SAMPLE)
    assert len(cases) == 2
    assert cases[0].external_id == "AU-001"
    assert cases[0].section == "Authentication"
    assert cases[0].priority == "P0"
    assert cases[0].steps == ["Open the login screen.", "Submit valid credentials."]
    assert cases[1].lifecycle == "planned"


def test_hash_changes_with_expected_result():
    before = parse_markdown(SAMPLE)[0].content_hash
    after = parse_markdown(SAMPLE.replace("The dashboard opens.", "A dashboard opens."))[0].content_hash
    assert before != after


def test_requires_expected_result():
    invalid = "### AU-001 — Valid login (`P0`)\n\n1. Try it."
    try:
        parse_markdown(invalid)
    except ValueError as exc:
        assert "Expected" in str(exc)
    else:
        raise AssertionError("invalid case was accepted")

