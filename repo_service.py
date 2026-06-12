import os
from pathlib import Path

from fastapi import HTTPException

from settings import REPO_DIR


def get_repo_path(repo_name: str):
    repo_path = (REPO_DIR / repo_name).resolve()

    if not str(repo_path).startswith(str(REPO_DIR.resolve())):
        raise HTTPException(status_code=400, detail="非法仓库名称")

    if not repo_path.exists():
        raise HTTPException(status_code=404, detail="仓库不存在，请先调用 /clone")

    return repo_path


def analyze_repo(repo_path):
    stats = {
        "total_files": 0,
        "python_files": 0,
        "markdown_files": 0,
        "javascript_files": 0,
    }
    core_dirs = []

    for root, dirs, files in os.walk(repo_path):
        if Path(root) == repo_path:
            core_dirs.extend(dirs)

        for filename in files:
            stats["total_files"] += 1

            if filename.endswith(".py"):
                stats["python_files"] += 1
            elif filename.lower().endswith((".md", ".rst")):
                stats["markdown_files"] += 1
            elif filename.endswith((".js", ".ts", ".jsx", ".tsx")):
                stats["javascript_files"] += 1

    return stats, core_dirs


def read_readme(repo_path):
    for filename in ("README.md", "readme.md", "README.rst", "README.txt"):
        path = repo_path / filename

        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")

    return None
