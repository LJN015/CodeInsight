import os
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter


IGNORE_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "docs",
    "tests",
    "examples",
    "requirements",
    "venv",
    ".venv",
    "node_modules",
}

SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".kt",
    ".py",
    ".md",
    ".php",
    ".rb",
    ".rst",
    ".rs",
    ".scala",
    ".swift",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
}


def load_source_files(repo_path):
    documents = []
    repo_root = Path(repo_path).resolve()

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for filename in files:
            path = Path(root) / filename

            if path.suffix.lower() not in SOURCE_SUFFIXES:
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                print(f"读取失败: {path} ({exc})")
                continue

            if not content.strip():
                continue

            documents.append(
                {
                    "path": str(path),
                    "relative_path": str(path.relative_to(repo_root)),
                    "content": content,
                }
            )

    return documents


def load_python_files(repo_path):
    return [
        doc
        for doc in load_source_files(repo_path)
        if Path(doc["path"]).suffix.lower() == ".py"
    ]


def split_documents(documents, chunk_size=1000, chunk_overlap=200):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\nclass ", "\ndef ", "\n## ", "\n### ", "\n", " ", ""],
    )

    chunks = []

    for doc in documents:
        parts = splitter.split_text(doc["content"])

        for index, part in enumerate(parts):
            chunks.append(
                {
                    "path": doc["path"],
                    "relative_path": doc.get("relative_path", doc["path"]),
                    "chunk_id": index,
                    "content": part,
                }
            )

    return chunks


if __name__ == "__main__":
    docs = load_source_files("repos/flask")
    chunks = split_documents(docs)

    print("源码文件数量:", len(docs))
    print("代码块数量:", len(chunks))

    if chunks:
        print(chunks[0]["relative_path"])
        print(chunks[0]["content"][:300])
