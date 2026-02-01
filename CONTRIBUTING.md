# Contributing to Truth Core

Thank you for your interest in contributing to Truth Core! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Node.js 18+ (for dashboard development)
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/your-org/truth-core.git
cd truth-core

# Install Python dependencies
pip install -e '.[dev,parquet]'

# Install dashboard dependencies
cd dashboard
npm install
cd ..

# Verify setup
python -m pytest -q
```

## Development Workflow

1. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes** with tests

3. **Run verification**:
   ```bash
   # Linting
   ruff check .
   ruff format .

   # Type checking
   pyright src/truthcore

   # Tests
   python -m pytest -q

   # Build
   python -m build
   ```

4. **Commit** with clear messages:
   ```bash
   git commit -m "feat: add new invariant rule for X"
   ```

5. **Push** and create a Pull Request

## Code Style

We use:
- **Ruff** for linting and formatting (configured in pyproject.toml)
- **Pyright** for type checking
- **Google-style** docstrings

### Python Code Guidelines

```python
"""Module docstring.

This module provides functionality for X.
"""

from pathlib import Path

def process_data(input_path: Path, strict: bool = False) -> dict:
    """Process data from input path.

    Args:
        input_path: Path to input file
        strict: Whether to enforce strict validation

    Returns:
        Processed data as dictionary

    Raises:
        FileNotFoundError: If input_path doesn't exist
        ValidationError: If data fails validation
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")
    
    # Process logic here
    return {"result": "success"}
```

### Type Hints

- All functions must have type hints
- Use `from __future__ import annotations` for Python 3.11+ features
- Use `|` for union types (e.g., `str | None`)

## Testing

### Running Tests

```bash
# All tests
pytest

# Specific test
pytest tests/test_findings.py::test_specific

# With coverage
pytest --cov=src/truthcore --cov-report=html
```

### Writing Tests

```python
import pytest
from truthcore.findings import Finding

def test_finding_creation():
    """Test that findings are created correctly."""
    finding = Finding(
        id="test-1",
        severity="HIGH",
        message="Test message"
    )
    assert finding.severity == "HIGH"
```

### Test Guidelines

- All code changes must include tests
- Aim for >80% coverage
- Use descriptive test names
- Group related tests in classes

## Documentation

### Docstrings

All public APIs must have docstrings following Google style:

```python
def my_function(arg1: str, arg2: int) -> bool:
    """Short description.

    Longer description if needed. Can span multiple lines
    and include code examples.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When arg2 is negative

    Examples:
        >>> my_function("test", 5)
        True
    """
```

### Documentation Files

- Update `docs/` for user-facing changes
- Update `CHANGELOG.md` for all changes
- Keep `README.md` examples working

## Pull Request Process

1. **Before submitting**:
   - [ ] Tests pass locally
   - [ ] Linting passes
   - [ ] Type checking passes
   - [ ] Documentation updated
   - [ ] CHANGELOG.md updated

2. **PR Description** should include:
   - What changed and why
   - How to test the changes
   - Any breaking changes
   - Related issues

3. **Review Process**:
   - All PRs require at least one review
   - Address review comments
   - Maintain respectful discussion

## Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build, deps, tooling

Examples:
```
feat(verdict): add score normalization
fix(cli): handle missing config file
docs(readme): update installation instructions
test(invariants): add edge case coverage
```

## Dashboard Development

### Dashboard Structure

```
dashboard/
├── src/
│   ├── main.ts          # Main application
│   ├── styles.css       # Styles
│   ├── types/           # TypeScript types
│   └── utils/           # Utilities
```

### Dashboard Development Workflow

```bash
cd dashboard

# Install deps
npm install

# Dev server
npm run dev

# Build
npm run build

# Preview production build
npm run preview
```

### Dashboard Guidelines

- Use vanilla TypeScript (no frameworks)
- SVG charts only (no external chart libs)
- CSS variables for theming
- Accessible (keyboard nav, ARIA)
- Mobile responsive

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create git tag: `git tag v1.2.3`
4. Push tag: `git push origin v1.2.3`
5. GitHub Actions creates release automatically

## Questions?

- Open an issue for bugs or features
- Start a discussion for questions
- Read [docs/](/docs) for detailed info

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

Thank you for contributing! 🎉
