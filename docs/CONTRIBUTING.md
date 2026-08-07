# Contributing to eovpanel

## Development Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Installer

```bash
cd installer
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m installer
```

## Code Style

- **Python**: Ruff (linting + formatting), Black (formatting). Config in `backend/pyproject.toml`.
- **TypeScript**: ESLint + Prettier. Config in `frontend/`.
- **Commits**: Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, etc.). Keep commit bodies short or empty.

## Project Structure

```
backend/        FastAPI application (app/ subfolder)
frontend/       React + TypeScript + Vite + Chakra UI
installer/      Textual TUI installer
vpn-core/       OpenVPN helpers (wraps easy-rsa + Nyr's script logic)
docker/         Dockerfiles and docker-compose
docs/           Architecture docs and ADRs
```

## Pull Requests

1. Fork the repo and create a feature branch.
2. Write clear commit messages.
3. Ensure `ruff check` passes for Python changes.
4. Ensure `npm run build` succeeds for frontend changes.
5. Open a PR with a clear description of what changed and why.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
