# Contributing to eovpanel

Thanks for your interest in contributing.  Here's how to get started.

## Development Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env    # edit with your settings
alembic upgrade head    # run migrations
uvicorn app.main:app --reload
```

The API is now running at `http://localhost:8000`.  Interactive docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite dev server runs at `http://localhost:5173` and proxies `/api/` to the backend.

### Installer

```bash
cd installer
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m installer
```

## Running Tests

```bash
# Backend — all tests
cd backend && python -m pytest tests/ -v

# Backend — single test file
cd backend && python -m pytest tests/test_security.py -v

# Backend — lint
cd backend && ruff check .
```

```bash
# Frontend — lint
cd frontend && npm run lint

# Frontend — build
cd frontend && npm run build
```

Or use the Makefile shortcuts from the repo root:

```bash
make test     # run backend tests
make lint     # run backend lint
```

## Code Style

- **Python:** Ruff for linting, Black for formatting.  Config in `backend/pyproject.toml`.  Line length 120.
- **TypeScript:** ESLint via oxlint.  Config in `frontend/`.
- **Follow existing patterns.**  Look at neighboring files before introducing new libraries, naming conventions, or architectural patterns.

## Commit Messages

Keep commit messages short, human, and on one line.  No conventional commit prefixes required — just describe what changed in plain language.

Good:
- `add user management page with search and pagination`
- `fix subscription token revocation test`
- `security and concurrency hardening pass`

Bad:
- `feat: added users page (#123)`
- `chore: update dependencies`
- `FIX BUG`

If you want to add more detail, add a blank line after the subject and write a brief body.  But most changes can be explained in one line.

## Pull Requests

1. Fork the repo and create a feature branch from `main`.
2. Make your changes, following existing code conventions.
3. Ensure `ruff check` passes for Python changes.
4. Ensure `npm run build` succeeds for frontend changes.
5. Run `cd backend && python -m pytest tests/ -v` to make sure all tests pass.
6. Open a PR with a clear description of what changed and why.

Keep PRs focused.  One feature or fix per PR.

## Project Structure

```
backend/        FastAPI application (app/ subfolder)
frontend/       React + TypeScript + Vite + Chakra UI
installer/      Textual TUI installer
vpn-core/       OpenVPN helpers (wraps easy-rsa + Nyr's script logic)
docker/         Dockerfiles and docker-compose
docs/           Architecture docs and ADRs
```

## Reporting Issues

For bugs and feature requests, open a GitHub issue.  For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
