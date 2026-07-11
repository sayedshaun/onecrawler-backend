# AGENTS.md

## Overview

Follow the existing architecture and coding style. Make the smallest change necessary to solve the problem. Prioritize readability, maintainability, and correctness over cleverness.

## Python

- Target Python 3.12+
- Use type hints for all new code.
- Follow PEP 8; format and lint with `ruff` (line length 88, see `pyproject.toml`).
- Prefer f-strings, `pathlib`, context managers, and dataclasses/Pydantic where appropriate.
- Keep functions focused and reasonably short.

## Code Style

- Prefer simple, explicit code.
- Avoid duplication.
- Use meaningful names.
- Prefer early returns over nested conditionals.
- Do not introduce unnecessary abstractions.

## Project Structure

- Each feature lives under `src/api/.../<feature>/` with `router.py` (routes and DB access/business logic, inline in each endpoint function) and `schema.py` (Pydantic models).
- Reuse existing modules before creating new ones.
- Respect the current project architecture.

## Error Handling

- Raise meaningful exceptions.
- Never silently ignore errors.
- Catch only expected exceptions.

## Logging

- Use `logging` instead of `print()`.

## Testing

When changing behavior:

- Update or add tests if needed.
- Do not remove existing tests without reason.

## Dependencies

- Prefer the standard library when possible.
- Avoid adding new dependencies unless necessary.

## OneCrawler (dependency)

`onecrawler` (github.com/sayedshaun/onecrawler) is a crawling framework, published to PyPI and installed only in the `worker` image (see `Dockerfile`, `pip install .[worker]`) — it is not installed on the host or in the `api` image.

When you need to check its actual API/behavior, don't guess from the GitHub README — inspect the installed source inside the worker container:

    docker compose exec worker python -c "import onecrawler, os; print(os.path.dirname(onecrawler.__file__))"

Then read the source under that path for the real classes/functions in use.

## Before Finishing

Ensure:

- Code is formatted.
- Type hints are correct.
- No dead or commented-out code remains.
- Only relevant files were modified.
