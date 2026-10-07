# Markdown import format

The importer treats Markdown as input data. It recognizes second-level headings as module/section names and third-level headings as individual test cases.

```markdown
# Human test plan

## Authentication

### AU-001 — Valid login (`P0`)

1. Open the login page.
2. Enter valid credentials.
3. Submit the form.

Expected: The project dashboard opens.
```

Requirements:

- Every case ID must be unique within the file and match an identifier such as `AU-001`.
- The title separator may be an em dash, en dash, or hyphen.
- Priority is optional and appears in backticks inside parentheses.
- Additional text after the priority comma is stored as lifecycle metadata, for example `planned` or `implemented; live acceptance pending`.
- Each case needs at least one numbered step and a non-empty `Expected:` result.
- Files must be UTF-8 Markdown and at most 2 MB through the web importer.

Import matching is by `(project, case ID)`. New IDs are inserted. Changed cases receive a new immutable revision and update the library's current revision. Identical cases are reported as unchanged. Cases omitted from a later file are not deleted or deactivated.

Use the CLI to validate without changing data:

```bash
.venv/bin/python -m cli.import_tests path/to/plan.md --project PROJECTKEY --dry-run
```

