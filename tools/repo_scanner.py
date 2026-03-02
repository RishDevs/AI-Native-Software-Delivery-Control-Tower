"""Repository scanner — extracts metadata, file trees, and code context."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


class RepoScanner:
    """Scans a local Git repository to extract context for agents."""

    # Common directories to skip during scanning
    SKIP_DIRS = {
        ".git", "__pycache__", ".venv", "venv", "node_modules",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
        ".egg-info", ".tox", "htmlcov", ".coverage",
    }

    # File extensions to consider as source code
    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
        ".java", ".rb", ".php", ".c", ".cpp", ".h", ".hpp",
    }

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.exists():
            raise FileNotFoundError(f"Repository not found: {repo_path}")

    def get_summary(self) -> dict[str, Any]:
        """Get a high-level summary of the repository."""
        return {
            "path": str(self.repo_path),
            "language": self._detect_language(),
            "file_count": self._count_files(),
            "has_tests": self._has_tests(),
            "has_config": self._has_config(),
            "has_docker": self._has_docker(),
            "key_modules": self._find_key_modules(),
        }

    def get_file_tree(self, max_depth: int = 4, max_files: int = 200) -> list[str]:
        """Get a filtered file tree of the repository."""
        tree = []
        count = 0

        for root, dirs, files in os.walk(self.repo_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]

            depth = len(Path(root).relative_to(self.repo_path).parts)
            if depth > max_depth:
                dirs.clear()
                continue

            rel_root = Path(root).relative_to(self.repo_path)
            indent = "  " * depth

            if depth > 0:
                tree.append(f"{indent}{rel_root.name}/")

            for f in sorted(files):
                if count >= max_files:
                    tree.append(f"{indent}  ... (truncated)")
                    return tree
                tree.append(f"{indent}  {f}")
                count += 1

        return tree

    def get_file_content(self, relative_path: str) -> str:
        """Read file content by relative path."""
        full_path = self.repo_path / relative_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        if not full_path.is_file():
            raise ValueError(f"Not a file: {relative_path}")

        with open(full_path, "r", errors="replace") as f:
            return f.read()

    def get_multiple_files(self, paths: list[str]) -> list[dict[str, str]]:
        """Read multiple files and return as list of {path, content} dicts."""
        results = []
        for p in paths:
            try:
                content = self.get_file_content(p)
                results.append({"path": p, "content": content})
            except (FileNotFoundError, ValueError) as e:
                results.append({"path": p, "content": "", "error": str(e)})
        return results

    def search_code(self, pattern: str, max_results: int = 20) -> list[dict[str, Any]]:
        """Search for a pattern in the repository using ripgrep or grep."""
        results = []

        try:
            # Try ripgrep first
            cmd = [
                "rg", "--json", "--max-count", str(max_results),
                pattern, str(self.repo_path)
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if proc.returncode == 0:
                import json
                for line in proc.stdout.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("type") == "match":
                            data = entry["data"]
                            results.append({
                                "file": str(Path(data["path"]["text"]).relative_to(self.repo_path)),
                                "line": data["line_number"],
                                "text": data["lines"]["text"].strip(),
                            })
                    except (json.JSONDecodeError, KeyError):
                        continue

        except FileNotFoundError:
            # Fall back to grep
            try:
                cmd = [
                    "grep", "-rn", "--include=*.py",
                    "-m", str(max_results), pattern, str(self.repo_path)
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                for line in proc.stdout.strip().split("\n")[:max_results]:
                    if ":" in line:
                        parts = line.split(":", 2)
                        if len(parts) >= 3:
                            results.append({
                                "file": str(Path(parts[0]).relative_to(self.repo_path)),
                                "line": int(parts[1]) if parts[1].isdigit() else 0,
                                "text": parts[2].strip(),
                            })
            except Exception:
                pass
        except subprocess.TimeoutExpired:
            pass

        return results[:max_results]

    def _detect_language(self) -> str:
        """Detect the primary language of the repository."""
        ext_counts: dict[str, int] = {}
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            for f in files:
                ext = Path(f).suffix
                if ext in self.CODE_EXTENSIONS:
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1

        if not ext_counts:
            return "unknown"

        primary_ext = max(ext_counts, key=ext_counts.get)
        ext_to_lang = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby",
        }
        return ext_to_lang.get(primary_ext, "unknown")

    def _count_files(self) -> int:
        """Count source code files."""
        count = 0
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            count += sum(1 for f in files if Path(f).suffix in self.CODE_EXTENSIONS)
        return count

    def _has_tests(self) -> bool:
        """Check if the repository has test files."""
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            for f in files:
                if f.startswith("test_") or f.endswith("_test.py") or f == "conftest.py":
                    return True
        return False

    def _has_config(self) -> bool:
        """Check for common configuration files."""
        config_files = [
            "pyproject.toml", "setup.py", "setup.cfg", "package.json",
            "Cargo.toml", "go.mod", "Makefile",
        ]
        return any((self.repo_path / f).exists() for f in config_files)

    def _has_docker(self) -> bool:
        """Check for Docker files."""
        return (self.repo_path / "Dockerfile").exists() or (
            self.repo_path / "docker-compose.yml"
        ).exists()

    def _find_key_modules(self) -> list[str]:
        """Identify key Python modules."""
        modules = []
        for item in self.repo_path.iterdir():
            if item.is_dir() and not item.name.startswith(".") and item.name not in self.SKIP_DIRS:
                init_file = item / "__init__.py"
                if init_file.exists() or any(
                    f.suffix == ".py" for f in item.iterdir() if f.is_file()
                ):
                    modules.append(item.name)
            elif item.is_file() and item.suffix == ".py" and item.name != "setup.py":
                modules.append(item.name)
        return sorted(modules)
