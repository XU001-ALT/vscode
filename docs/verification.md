# Original SAF local deployment verification

Date: 2026-09-14. Local address: http://127.0.0.1:8502/ .

## Source and scope

Source: `z72882743-arch/saf-data-platform`, revision `43336612e47b499653bfa74bb2edc11dcdd9d432`. Application, requirements and support files are byte-identical to the previously verified upstream snapshot. The initial parquet database also matches its recorded SHA-256. No model files, prediction UI, credentials or user PDFs were copied.

The new project is independent of `D:/Codex/saf`: separate directory, Git repository, virtual environment, dataset and port. Added files provide launch/install commands, reproducible dependency versions, documentation and regression tests. Upstream application behavior was not edited.

## Checks

- `python -m pytest tests -q --tb=short`: 8 passed in 5.66 seconds. Covers five page loads, navigation/filtering/visualization, source hashes/no model module, and ingestion using temporary data.
- `python -m compileall -q` for all upstream Python modules: passed.
- `python -m pip check`: passed.
- Initial database SHA-256: passed; 4068 rows and 438 columns.
- HTTP `/_stcore/health`: 200, `ok`.
- Browser: five original navigation buttons, 4068-paper statistics, merged database filtering and charts displayed; no model navigation entry.
- Existing `D:/Codex/saf` Git status remains clean.
- Staged diff and credential-pattern check passed. Original prompt-file trailing blank lines are preserved with a path-specific Git whitespace exemption to retain upstream hashes.

The first filtering test selected the first available metal category, which had insufficient plotting records. The test fixture was corrected to the existing Co category; application code was not changed.

## Boundaries

External paper downloads, WebVPN login and paid LLM calls were not executed. Their original workflows and dependencies are retained, and require the user's network/account conditions. The public site could not be loaded directly and GitHub API was rate-limited, so the running cloud revision and pixel-level visual equality are not independently confirmed. Upstream navigation is retained as implemented, including its browser-dependent script styling.

Upstream deprecated `use_container_width` calls and empty-label warnings remain nonfatal. No project lint, formatting or type checker is configured. Runtime logs and datasets stay under ignored directories; they are not committed.
