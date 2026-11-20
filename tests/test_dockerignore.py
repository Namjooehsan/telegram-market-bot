from pathlib import Path


def test_dockerignore_excludes_root_and_nested_secrets():
    rules = {
        line.strip()
        for line in Path(".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert ".env" in rules
    assert ".env.*" in rules
    assert "**/.env" in rules
    assert "**/.env.*" in rules
    assert "!.env.example" in rules
    assert "**/*.pem" in rules
    assert "**/*.key" in rules
    assert "**/id_rsa" in rules
    assert "**/id_ed25519" in rules
    assert "**/*credentials*.json" in rules
    assert "**/*service-account*.json" in rules


def test_dockerignore_excludes_local_database_and_development_artifacts():
    rules = {
        line.strip()
        for line in Path(".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    for pattern in (
        "*.db",
        "*.sqlite",
        "*.sqlite3",
        "*.db-journal",
        "*.sqlite-wal",
        "*.sqlite-shm",
        "*.log",
        "*.bak",
        "*.tmp",
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
    ):
        assert pattern in rules
