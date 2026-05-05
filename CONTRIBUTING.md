# Contributing

Thanks for your interest!

## Quick start

1. Fork → clone → create a branch: `git checkout -b feat/my-change`.
2. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. Make your change. Keep it focused.
4. Verify it runs: `python list_channels.py --no-left -o /tmp/test.txt`
5. Open a PR with a clear description and, if relevant, sample output.

## Guidelines

- Python 3.10+ syntax is fine.
- Follow the existing style (no formatter enforced — match what's there).
- Don't commit `.env`, `*.session`, or generated reports.
- Bug reports: include OS, Python version, exact command, and the error traceback.

## Issues

Use GitHub Issues for bugs and feature requests. One topic per issue.
