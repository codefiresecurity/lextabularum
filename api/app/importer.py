import hashlib
import json
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import TestCase, TestCaseVersion


CASE_HEADING = re.compile(r"^###\s+([A-Za-z][A-Za-z0-9_-]*-\d+)\s+[—–-]\s+(.+?)(?:\s+\(`([^`]+)`(?:,\s*([^)]*))?\))?\s*$")
SECTION_HEADING = re.compile(r"^##\s+(.+?)\s*$")
STEP = re.compile(r"^\s*\d+[.)]\s+(.+?)\s*$")
EXPECTED = re.compile(r"^\s*Expected:\s*(.*)$", re.IGNORECASE)


@dataclass
class ParsedCase:
    external_id: str
    title: str
    section: str
    priority: str | None
    lifecycle: str | None
    steps: list[str]
    expected: str

    @property
    def content_hash(self) -> str:
        canonical = json.dumps(
            {"title": self.title, "section": self.section, "priority": self.priority,
             "lifecycle": self.lifecycle, "steps": self.steps, "expected": self.expected},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


def parse_markdown(text: str) -> list[ParsedCase]:
    cases: list[ParsedCase] = []
    section = "General"
    current: ParsedCase | None = None
    expected_lines: list[str] = []
    reading_expected = False

    def finish():
        nonlocal current, expected_lines
        if current:
            current.expected = "\n".join(expected_lines).strip()
            if not current.steps or not current.expected:
                raise ValueError(f"{current.external_id} must contain numbered steps and an Expected: result")
            cases.append(current)
        current = None
        expected_lines = []

    for raw in text.splitlines():
        line = raw.rstrip()
        case_match = CASE_HEADING.match(line)
        if case_match:
            finish()
            metadata = (case_match.group(4) or "").strip() or None
            current = ParsedCase(case_match.group(1), case_match.group(2).strip(), section,
                                 case_match.group(3), metadata, [], "")
            reading_expected = False
            continue
        section_match = SECTION_HEADING.match(line)
        if section_match:
            finish()
            section = section_match.group(1).strip()
            reading_expected = False
            continue
        if not current:
            continue
        expected_match = EXPECTED.match(line)
        if expected_match:
            reading_expected = True
            expected_lines.append(expected_match.group(1))
            continue
        if reading_expected:
            if line.strip():
                expected_lines.append(line.strip())
            continue
        step_match = STEP.match(line)
        if step_match:
            current.steps.append(step_match.group(1).strip())
    finish()
    if not cases:
        raise ValueError("No test cases found; expected headings like '### DF-001 — Title (`P0`)'")
    ids = [case.external_id for case in cases]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise ValueError("Duplicate case IDs: " + ", ".join(duplicates))
    return cases


def import_cases(db: Session, project_id: int, parsed: list[ParsedCase], source_file: str) -> dict:
    created = updated = unchanged = 0
    for item in parsed:
        case = db.scalar(select(TestCase).where(TestCase.project_id == project_id, TestCase.external_id == item.external_id))
        if not case:
            case = TestCase(project_id=project_id, external_id=item.external_id, title=item.title,
                            section=item.section, priority=item.priority, lifecycle=item.lifecycle, current_version=1)
            db.add(case)
            db.flush()
            db.add(TestCaseVersion(test_case_id=case.id, version=1, title=item.title, section=item.section,
                                   priority=item.priority, lifecycle=item.lifecycle, steps_json=json.dumps(item.steps),
                                   expected=item.expected, content_hash=item.content_hash, source_file=source_file))
            created += 1
            continue
        latest = db.scalar(select(TestCaseVersion).where(TestCaseVersion.test_case_id == case.id,
                                                         TestCaseVersion.version == case.current_version))
        if latest and latest.content_hash == item.content_hash:
            unchanged += 1
            continue
        case.title, case.section, case.priority, case.lifecycle = item.title, item.section, item.priority, item.lifecycle
        case.current_version += 1
        db.add(TestCaseVersion(test_case_id=case.id, version=case.current_version,
                               title=item.title, section=item.section, priority=item.priority, lifecycle=item.lifecycle,
                               steps_json=json.dumps(item.steps), expected=item.expected,
                               content_hash=item.content_hash, source_file=source_file))
        updated += 1
    return {"created": created, "updated": updated, "unchanged": unchanged, "total": len(parsed)}
