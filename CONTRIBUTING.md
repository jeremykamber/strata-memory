# Contributing to Strata

Thanks for your interest in Strata. This document covers how to set up the project, run tests, and submit changes.

## Table of Contents

- [Getting Started](#getting-started)
- [Running Tests](#running-tests)
- [Branch Strategy](#branch-strategy)
- [Commit Messages](#commit-messages)
- [Pull Requests](#pull-requests)
- [Documentation](#documentation)
- [Dependencies](#dependencies)
- [Reporting Issues](#reporting-issues)
- [License](#license)

---

## Getting Started

```bash
git clone git@github.com:jeremykamber/strata-memory.git
cd strata-memory
pip install -e .
pip install pytest

# Verify it works
strata init --non-interactive
strata add hello.md "# Hello from Strata"
strata read hello.md
```

Strata has zero core dependencies — you just need Python 3.9+.

For optional features during development:

```bash
# QMD hybrid search (needs Node.js)
npm install -g @tobilu/qmd

# LLM integration testing
pip install strata-memory[all]
```

Before committing, run the linter if you have it:

```bash
pip install ruff
ruff check strata/ tests/
```

---

## Running Tests

```bash
# Full suite
python -m pytest tests/

# A single file
python -m pytest tests/test_janitor.py -v

# A single test
python -m pytest tests/test_cli.py::test_cli_init -v

# With coverage
python -m pytest tests/ --cov=strata
```

All tests should pass before you open a pull request.

---

## Branch Strategy

- **`main`** is production. Only tagged releases go here.
- **`dev`** is the integration branch. All pull requests go here.
- **Feature branches** branch from `dev` and get merged back into `dev`.

Name branches with a prefix: `feat/`, `fix/`, `refactor/`, `docs/`, `test/`, `chore/` followed by a short description in kebab-case. For example: `feat/add-json-export`. If a branch lives a while, rebase it onto `dev` periodically to keep conflicts manageable.

---

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): short description in imperative mood

Optional body explaining why the change was made.
```

### Types

| Type | Use for |
|---|---|
| `feat` | New user-facing feature |
| `fix` | Bug fix |
| `refactor` | Code change with no behavior change |
| `docs` | Documentation only |
| `test` | Adding or fixing tests |
| `chore` | Build config, CI, tooling |

The scope is optional — use it for the area being changed (`cli`, `janitor`, `storage`, `config`, `docs`, `landing-page`, etc.). Keep the body line length under 72 characters.

### Before you commit

```bash
git diff --staged   # Check for debug artifacts, secrets, commented code
git status          # Check you're not committing unrelated files
```

---

## Pull Requests

1. Create a feature branch from `dev`.
2. Make your changes with focused commits.
3. Run the tests. Fix anything that breaks.
4. Update documentation if you changed user-facing behavior.
5. Open the pull request against `dev`. Include:
   - **What** the change does
   - **Why** it's needed
   - **How you tested it**
6. Respond to review feedback. Review is collaborative — if you disagree with a suggestion, explain your reasoning.

### CI

Every pull request runs:

1. Python tests (`pytest`)
2. Linting (`ruff`)
3. Package build (`pip install -e .`)
4. Landing page build (`cd landing_page && npm run build`) if landing page files changed

### Keeping Pull Requests Focused

Small, focused pull requests are easier to review. If a change touches many files, consider splitting it into multiple pull requests. Avoid mixing unrelated changes — a formatting fix shouldn't share a pull request with a new feature.

---

## Documentation

Strata's documentation is hand-written markdown. If you change user-facing behavior, update the relevant docs in the same pull request.

Key files:

| File | Update when |
|---|---|
| `README.md` | Adding/changing any user-facing feature |
| `AGENTS.md` | Changing architecture, API, or contribution rules |
| `docs/cli-reference.md` | Adding, removing, or changing any CLI command or flag |
| `docs/architecture.md` | Changing strata behavior, Janitor lifecycle, or data flow |
| `docs/configuration.md` | Adding or changing config fields or defaults |
| `docs/installation.md` | Changing install methods or requirements |
| `docs/search.md` | Changing search backends or query syntax |
| `docs/tracking.md` | Changing cost tracking methodology |
| `docs/pi-integration.md` | Changing Pi integration |
| `strata/_cli_main.py` / `strata/cli/commands/` | Adding or changing any CLI command |

---

## Dependencies

Strata's core has zero dependencies by design. If you need a third-party library, make it optional — add it to `[project.optional-dependencies]` in `pyproject.toml`, wrap imports in `try/except ImportError`, and document the dependency.

Optional dependencies (`[openai]`, `[anthropic]`, `[all]`) are fine for gated features.

---

## Reporting Issues

Open an issue on [GitHub](https://github.com/jeremykamber/strata-memory/issues). Include:

- What you were doing
- What you expected to happen
- What actually happened
- Your environment (Python version, OS, Strata version)
- Steps to reproduce, if possible

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](https://github.com/jeremykamber/strata-memory/blob/main/LICENSE).
