# Repository Guidelines

## Project Structure & Module Organization
- `src/veotools/` holds the public SDK, CLI entry points, and storage utilities; keep runtime assets (plans, clips) in `output/` only.
- Tests live in `tests/` and mirror the package layout; add new suites under `tests/<area>/test_<feature>.py`.
- Reference flows in `examples/`, automation in `scripts/`, and long-form docs under `docs/` (served via MkDocs).

## Build, Test, and Development Commands
- `pip install -e ".[dev,mcp]"` prepares a full contributor environment with test, docs, and MCP extras.
- `make test`, `make test-unit`, `make test-integration` run the pytest suite with relevant markers; default output is uncaptured for easier debugging.
- `make format`, `make lint`, and `make typecheck` invoke Black, Ruff, and mypy; run all three before sending reviews.
- `make docs-serve` previews MkDocs locally; `python scripts/generate_llm_docs.py --format md --output llm.txt` refreshes LLM-facing docs when APIs change.

## Coding Style & Naming Conventions
- Use 4-space indentation and Black defaults; do not hand-tune formatting—rerun `make format` instead.
- Follow Ruff feedback for imports and unused code; silence false positives with targeted `# noqa` comments only when justified.
- Modules and functions use `snake_case`, classes use `PascalCase`, and CLI commands stay hyphenated to match existing interfaces.

## Testing Guidelines
- Pytest is the standard; place fast paths under the `unit` marker and slower orchestration tests under `integration` or `slow`.
- Name tests `test_<behavior>` and co-locate fixtures beside the modules they support.
- Use `make test-coverage` for HTML + terminal coverage; keep new logic covered and extend mocks rather than hitting external APIs.

## Commit & Pull Request Guidelines
- Keep commit subjects concise, present-tense, and capability-focused (e.g., `add router support`, `tighten stitching cache`).
- Group related changes per commit; update `CHANGELOG.md`, docs, or examples when behavior moves.
- Pull requests should outline intent, testing performed, and any model/API changes; attach sample CLI output or stitched artifacts when it aids reviewers.

## Environment & Access Notes
- Export `GEMINI_API_KEY` for direct Google access or set `VEO_PROVIDER=daydreams` with `DAYDREAMS_API_KEY` (and optional `DAYDREAMS_BASE_URL`) when routing through Dreams Router; never commit secrets—use `.env` and document required variables in PRs.
- Confirm ffmpeg availability when touching stitching code, and mention any new system dependencies in the PR description.
