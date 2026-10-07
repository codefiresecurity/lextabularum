#!/usr/bin/env python3
"""
Import test cases into the TCM database.

Supports two formats:
  1. CSV  (see previous message)
  2. Markdown human test plan (the ResponderCare style you just shared)

Usage:
  python import_test_cases.py path/to/file.md
  python import_test_cases.py path/to/file.csv
"""

import csv
import re
import sys
from pathlib import Path
from typing import Optional

import mysql.connector
from mysql.connector import Error

# ---------- CONFIG ----------
DB_CONFIG = {
    "host": "localhost",
    "user": "lex_user",          # or whatever you prefer
    "password": "your_password",
    "database": "lex_tabularum",
}
DEFAULT_CREATED_BY = 3          # admin user id
# ----------------------------

PRIORITY_MAP = {
    "P0": "critical",
    "P1": "high",
    "P2": "medium",
    "P3": "low",
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}

# ----------------------------------------------------------------------
# Database helpers
# ----------------------------------------------------------------------
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def get_or_create_suite(cursor, suite_name: str) -> Optional[int]:
    if not suite_name or not suite_name.strip():
        return None
    name = suite_name.strip()
    cursor.execute("SELECT id FROM test_suites WHERE name = %s", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(
        "INSERT INTO test_suites (name, created_by) VALUES (%s, %s)",
        (name, DEFAULT_CREATED_BY),
    )
    return cursor.lastrowid

def upsert_test_case(cursor, data: dict):
    """data keys: external_id, title, description, preconditions, steps,
                  expected_result, priority, tags, suite_id
    """
    cursor.execute(
        "SELECT id FROM test_cases WHERE external_id = %s",
        (data["external_id"],),
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            """
            UPDATE test_cases SET
                suite_id        = %s,
                title           = %s,
                description     = %s,
                preconditions   = %s,
                steps           = %s,
                expected_result = %s,
                priority        = %s,
                tags            = %s,
                updated_at      = NOW()
            WHERE id = %s
            """,
            (
                data.get("suite_id"),
                data["title"],
                data.get("description"),
                data.get("preconditions"),
                data["steps"],
                data["expected_result"],
                data["priority"],
                data.get("tags"),
                existing[0],
            ),
        )
        return "updated"
    else:
        cursor.execute(
            """
            INSERT INTO test_cases
                (suite_id, external_id, title, description, preconditions,
                 steps, expected_result, priority, tags, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data.get("suite_id"),
                data["external_id"],
                data["title"],
                data.get("description"),
                data.get("preconditions"),
                data["steps"],
                data["expected_result"],
                data["priority"],
                data.get("tags"),
                DEFAULT_CREATED_BY,
            ),
        )
        return "inserted"

# ----------------------------------------------------------------------
# Markdown parser (ResponderCare style)
# ----------------------------------------------------------------------
def parse_markdown(filepath: str) -> list[dict]:
    """
    Parse a human test-plan markdown file and return a list of test-case dicts.
    """
    text = Path(filepath).read_text(encoding="utf-8")

    # Split into lines for easier processing
    lines = text.splitlines()

    cases = []
    current_suite = None
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].rstrip()

        # Suite heading: ## Something
        if line.startswith("## ") and not line.startswith("###"):
            current_suite = line[3:].strip()
            i += 1
            continue

        # Test case heading: ### RC-001 — Title (`P0`)
        m = re.match(
            r"^###\s+(RC-\d+)\s+[—–-]\s+(.+?)\s*(?:\(`([P0-3])`\))?\s*$",
            line,
        )
        if m:
            external_id = m.group(1)
            title = m.group(2).strip()
            raw_priority = m.group(3) or "P1"
            priority = PRIORITY_MAP.get(raw_priority, "high")

            # Collect the body until the next ### or ## heading
            body_lines = []
            i += 1
            while i < n and not re.match(r"^#{2,3}\s", lines[i]):
                body_lines.append(lines[i])
                i += 1

            body = "\n".join(body_lines).strip()

            # Extract steps (numbered list)
            steps_match = re.search(
                r"((?:^\d+\.\s+.+(?:\n|$))+)", body, re.MULTILINE
            )
            steps = steps_match.group(1).strip() if steps_match else ""

            # Extract Expected result
            expected_match = re.search(
                r"Expected:\s*(.+?)(?=\n\n|\n###|\n##|$)", body, re.DOTALL | re.IGNORECASE
            )
            expected = expected_match.group(1).strip() if expected_match else ""

            # Everything before the first numbered step is treated as description
            description = ""
            if steps_match:
                pre_steps = body[: steps_match.start()].strip()
                # Remove any leading blank lines / the title repetition
                description = pre_steps

            if not steps or not expected:
                print(f"Warning: {external_id} is missing steps or expected result – skipped")
                continue

            cases.append(
                {
                    "external_id": external_id,
                    "title": title,
                    "description": description or None,
                    "preconditions": None,          # not present in this format
                    "steps": steps,
                    "expected_result": expected,
                    "priority": priority,
                    "tags": None,
                    "suite_name": current_suite,
                }
            )
            continue

        i += 1

    return cases

# ----------------------------------------------------------------------
# CSV parser (kept for compatibility)
# ----------------------------------------------------------------------
def parse_csv(filepath: str) -> list[dict]:
    cases = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"external_id", "title", "steps", "expected_result"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = required - set(reader.fieldnames or [])
            raise ValueError(f"CSV missing required columns: {missing}")

        for row in reader:
            priority = (row.get("priority") or "medium").lower().strip()
            priority = PRIORITY_MAP.get(priority, "medium")
            cases.append(
                {
                    "external_id": row["external_id"].strip(),
                    "title": row["title"].strip(),
                    "description": row.get("description") or None,
                    "preconditions": row.get("preconditions") or None,
                    "steps": row["steps"].strip(),
                    "expected_result": row["expected_result"].strip(),
                    "priority": priority,
                    "tags": row.get("tags") or None,
                    "suite_name": row.get("suite_name") or None,
                }
            )
    return cases

# ----------------------------------------------------------------------
# Main import logic
# ----------------------------------------------------------------------
def import_file(filepath: str):
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)

    suffix = path.suffix.lower()
    if suffix == ".md":
        print(f"Parsing Markdown test plan: {path.name}")
        cases = parse_markdown(str(path))
    elif suffix == ".csv":
        print(f"Parsing CSV: {path.name}")
        cases = parse_csv(str(path))
    else:
        print("Unsupported file type. Use .md or .csv")
        sys.exit(1)

    if not cases:
        print("No test cases found.")
        sys.exit(0)

    print(f"Found {len(cases)} test cases. Importing…")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        inserted = updated = 0
        for case in cases:
            suite_id = get_or_create_suite(cursor, case.get("suite_name"))
            case["suite_id"] = suite_id
            result = upsert_test_case(cursor, case)
            if result == "inserted":
                inserted += 1
            else:
                updated += 1

        conn.commit()
        print(f"Done. Inserted: {inserted}, Updated: {updated}")

    except Error as e:
        print(f"Database error: {e}")
        sys.exit(1)
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python import_test_cases.py <file.md|file.csv>")
        sys.exit(1)
    import_file(sys.argv[1])
