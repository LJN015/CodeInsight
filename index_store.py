import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

import faiss
from fastapi import HTTPException

from code_loader import load_source_files, split_documents
from embedding_service import current_embedding_info, embedding_backend
from repo_service import get_repo_path
from settings import CHUNK_OVERLAP, CHUNK_SIZE, INDEX_DIR


INDEX_CACHE: dict[str, dict[str, Any]] = {}


def get_index_dir(repo_name: str):
    safe_name = Path(repo_name).name
    index_dir = (INDEX_DIR / safe_name).resolve()

    if not str(index_dir).startswith(str(INDEX_DIR.resolve())):
        raise HTTPException(status_code=400, detail="非法仓库名称")

    return index_dir


def get_index_files(repo_name: str):
    index_dir = get_index_dir(repo_name)

    return {
        "dir": index_dir,
        "faiss": index_dir / "index.faiss",
        "chunks": index_dir / "chunks.json",
        "meta": index_dir / "metadata.json",
    }


def build_repo_snapshot(repo_path: Path, documents=None):
    hasher = hashlib.sha256()
    file_count = 0
    total_bytes = 0
    latest_mtime_ns = 0

    if documents is None:
        documents = load_source_files(repo_path)

    repo_root = repo_path.resolve()

    for doc in sorted(documents, key=lambda item: item["relative_path"]):
        path = Path(doc["path"])

        try:
            stat = path.stat()
        except OSError:
            continue

        relative_path = doc.get("relative_path", str(path.relative_to(repo_root)))
        file_count += 1
        total_bytes += stat.st_size
        latest_mtime_ns = max(latest_mtime_ns, stat.st_mtime_ns)
        hasher.update(relative_path.replace("\\", "/").encode("utf-8"))
        hasher.update(str(stat.st_size).encode("ascii"))
        hasher.update(str(stat.st_mtime_ns).encode("ascii"))

    return {
        "file_count": file_count,
        "total_bytes": total_bytes,
        "latest_mtime_ns": latest_mtime_ns,
        "fingerprint": hasher.hexdigest(),
    }


def is_index_metadata_fresh(repo_name: str, metadata):
    repo_path = get_repo_path(repo_name)
    current_snapshot = build_repo_snapshot(repo_path)

    return (
        metadata.get("repo_snapshot") == current_snapshot
        and metadata.get("chunk_size") == CHUNK_SIZE
        and metadata.get("chunk_overlap") == CHUNK_OVERLAP
    )


def save_index(repo_name: str, index, chunks, embedding_info, repo_snapshot):
    files = get_index_files(repo_name)
    files["dir"].mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(files["faiss"]))
    files["chunks"].write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    files["meta"].write_text(
        json.dumps(
            {
                "repo_name": repo_name,
                "chunk_count": len(chunks),
                "created_at": int(time.time()),
                "chunk_size": CHUNK_SIZE,
                "chunk_overlap": CHUNK_OVERLAP,
                "repo_snapshot": repo_snapshot,
                **embedding_info,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_persisted_index(repo_name: str):
    files = get_index_files(repo_name)

    if not (
        files["faiss"].exists()
        and files["chunks"].exists()
        and files["meta"].exists()
    ):
        return None

    metadata = json.loads(files["meta"].read_text(encoding="utf-8"))
    embedding_info = current_embedding_info()

    if metadata.get("dimension") != embedding_info["dimension"]:
        return None

    if metadata.get("embedding_backend") != embedding_info["embedding_backend"]:
        return None

    if metadata.get("embedding_model") != embedding_info["embedding_model"]:
        return None

    if not is_index_metadata_fresh(repo_name, metadata):
        return None

    index = faiss.read_index(str(files["faiss"]))
    chunks = json.loads(files["chunks"].read_text(encoding="utf-8"))

    INDEX_CACHE[repo_name] = {
        "index": index,
        "chunks": chunks,
        "embedding_backend": metadata.get(
            "embedding_backend",
            embedding_info["embedding_backend"],
        ),
        "persisted": True,
        "metadata": metadata,
    }

    return INDEX_CACHE[repo_name]


def build_index(repo_name: str):
    repo_path = get_repo_path(repo_name)
    documents = load_source_files(repo_path)
    repo_snapshot = build_repo_snapshot(repo_path, documents)
    chunks = split_documents(
        documents,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    if not chunks:
        raise HTTPException(status_code=400, detail="没有可索引的源码文件")

    texts = [chunk["content"] for chunk in chunks]
    vectors = embedding_backend.encode(texts, kind="document")
    embedding_info = {
        "embedding_backend": embedding_backend.name,
        "embedding_model": embedding_backend.model_name,
        "embedding_local_only": embedding_backend.local_only,
        "dimension": int(vectors.shape[1]),
    }

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    INDEX_CACHE[repo_name] = {
        "index": index,
        "chunks": chunks,
        "embedding_backend": embedding_info["embedding_backend"],
        "persisted": False,
        "metadata": {
            "repo_name": repo_name,
            "chunk_count": len(chunks),
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "repo_snapshot": repo_snapshot,
            **embedding_info,
        },
    }
    save_index(repo_name, index, chunks, embedding_info, repo_snapshot)
    INDEX_CACHE[repo_name]["persisted"] = True

    return INDEX_CACHE[repo_name]


def get_or_build_index(repo_name: str):
    cached = INDEX_CACHE.get(repo_name)

    if cached and is_index_metadata_fresh(repo_name, cached.get("metadata", {})):
        return cached

    if cached:
        INDEX_CACHE.pop(repo_name, None)

    persisted = load_persisted_index(repo_name)

    if persisted:
        return persisted

    return build_index(repo_name)


def delete_index_data(repo_name: str):
    files = get_index_files(repo_name)
    existed = files["dir"].exists()

    INDEX_CACHE.pop(repo_name, None)

    if existed:
        shutil.rmtree(files["dir"])

    return existed, files["dir"]


def list_index_metadata():
    indexes = []

    for path in sorted(INDEX_DIR.iterdir()):
        if not path.is_dir():
            continue

        files = get_index_files(path.name)
        metadata = {}

        if files["meta"].exists():
            metadata = json.loads(files["meta"].read_text(encoding="utf-8"))

        stale = False
        if metadata:
            try:
                stale = not is_index_metadata_fresh(path.name, metadata)
            except HTTPException:
                stale = True

        indexes.append(
            {
                "repo_name": path.name,
                "path": str(path),
                "has_faiss": files["faiss"].exists(),
                "has_chunks": files["chunks"].exists(),
                "cached": path.name in INDEX_CACHE,
                "stale": stale,
                **metadata,
            }
        )

    return indexes
