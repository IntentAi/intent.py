# Contributing to intent.py

intent.py is the Python bot SDK for Intent, modeled after discord.py.

## Pick an Issue

Check the [issues](https://github.com/IntentAi/intent.py/issues). Look at **relationship links** on the right side — if something is blocked, that dependency lands first. Comment to claim an issue, wait for assignment.

## Branching

Work is organized into phases. Check which phase branch is active or ask a maintainer.

```
git checkout <phase-branch> && git pull origin <phase-branch>
git checkout -b <phase-branch>/7-connection-state
```

No active phase branch? Use `feat/<issue>-description` off `dev`. PR against the **phase branch**, not dev or main.

## Before You Commit

All three must pass:

```bash
ruff check intent/ tests/
mypy intent/ --strict
pytest tests/ -v
```

## Commits

Conventional commits, issue references, one logical change each.

```
feat(state): parse MESSAGE_CREATE into cache [refs #7]

Caches messages in a bounded deque (1000 max). Updates channel
last_message_id and dispatches on_message to client listeners.
```

## Code Standards

- Python 3.10+ (`X | None`, not `Optional[X]`)
- Full type hints, mypy strict enforced
- `__slots__` on model classes
- Async/await throughout, line length 100
- Comment the reasoning, not the mechanics
- Tests alongside features

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## License

MIT
