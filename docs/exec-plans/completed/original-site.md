# Restore the original SAF website as an independent local project

## Objective
Create D:/Codex/10-projects/SAF from the source of the user-specified Streamlit website, without the additional FTS prediction subsystem.

## Scope and acceptance
- Original five pages, including merged overview/database, unchanged functional source.
- Independent local dataset, Python environment and launcher using port 8502.
- Existing D:/Codex/saf project and its data remain unchanged.
- Confirm source provenance, page tests and HTTP health; document unverified external services.

## Steps
1. Verify the upstream revision and file inventory.
2. Copy verified original files and initial website data into the new project.
3. Create standalone installation/run helpers and maintenance documentation.
4. Run offline page/ingestion checks and inspect the local browser.

## Decisions
- Windows paths are case-insensitive, so SAF cannot coexist with saf in D:/Codex; use the workspace's active-project directory.
- Preserve raw upstream application code unless a demonstrated runtime issue requires a minimal adaptation.
- Do not copy FTS models, credentials or user PDFs.

## Verification
- Copied 18 SHA-256 verified original source/data files with no application edits.
- Installed independent Python 3.12 environment and recorded dependency constraints.
- Five-page, navigation/filtering, source parity and temporary-ingestion tests implemented and checked.
- Compilation and dependency checks passed; HTTP health returns ok on port 8502.
- Browser confirms original five-entry navigation and merged overview/database.
- Existing model-enabled site remains unchanged. External cloud comparison and account-dependent operations remain unverified as documented in docs/verification.md.
