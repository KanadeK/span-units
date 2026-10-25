# Contributing

Please start with an issue describing the input, expected behavior and minimal
synthetic reproduction. Never attach private datasets. Issues and patch proposals
are welcome; no automatic merge or dependency-bot commits are enabled.

Use Python 3.11 or later in a virtual environment:

```sh
python -m pip install -r requirements-dev.txt
python -m pip install --no-build-isolation -e .
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check .
python -m build --no-isolation
```

Add behavior-focused tests for changed semantics and update the README. Keep
runtime dependencies minimal. Preserve all third-party notices if proposing reuse.
Release commits are maintained by the repository owner; no automated authoring.
