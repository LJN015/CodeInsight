import subprocess
import time
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException

from embedding_service import current_embedding_info
from index_store import (
    INDEX_CACHE,
    build_index,
    delete_index_data,
    get_index_files,
    get_or_build_index,
    list_index_metadata,
    load_persisted_index,
)
from llm_service import (
    answer_with_llm,
    build_fallback_answer,
    format_model_error,
    summarize_readme,
)
from repo_service import analyze_repo, get_repo_path, read_readme
from retrieval import build_sources, estimate_confidence, search_chunks
from schemas import AskRequest, IndexRequest, SearchRequest
from settings import INDEX_DIR, REPO_DIR, get_setting


app = FastAPI(title="CodeInsight")


@app.get("/")
def root():
    return {"message": "CodeInsight is running!"}


@app.get("/health")
def health():
    key = get_setting("DEEPSEEK_API_KEY")
    embedding_info = current_embedding_info()

    return {
        "status": "ok",
        "repos_dir": str(REPO_DIR),
        "indexes_dir": str(INDEX_DIR),
        "deepseek_api_key_set": bool(key),
        "deepseek_api_key_tail": key[-4:] if key else None,
        **embedding_info,
        "cached_indexes": list(INDEX_CACHE.keys()),
    }


@app.get("/repos")
def list_repos():
    repos = []

    for path in sorted(REPO_DIR.iterdir()):
        if not path.is_dir():
            continue

        stats, core_dirs = analyze_repo(path)
        repos.append(
            {
                "repo_name": path.name,
                "path": str(path),
                **stats,
                "core_directories": core_dirs,
                "indexed": get_index_files(path.name)["faiss"].exists(),
                "cached": path.name in INDEX_CACHE,
            }
        )

    return {"repos": repos}


@app.get("/indexes")
def list_indexes():
    return {"indexes": list_index_metadata()}


def parse_repo_name(repo_url: str):
    repo_name = repo_url.rstrip("/").split("/")[-1]

    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    return repo_name


def validate_repo_url(repo_url: str):
    repo_url = repo_url.strip()

    if not repo_url:
        raise HTTPException(status_code=400, detail="仓库 URL 不能为空")

    parsed = urlparse(repo_url)
    is_http_url = parsed.scheme in {"http", "https", "ssh", "git"} and parsed.netloc
    is_ssh_url = repo_url.startswith("git@") and ":" in repo_url

    if not (is_http_url or is_ssh_url):
        raise HTTPException(
            status_code=400,
            detail="仓库 URL 格式不正确，请使用 GitHub HTTPS 或 SSH 地址",
        )

    repo_name = parse_repo_name(repo_url)
    if not repo_name or repo_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="无法从 URL 解析仓库名称")

    return repo_url, repo_name


@app.post("/clone")
def clone_repo(repo_url: str):
    repo_url, repo_name = validate_repo_url(repo_url)
    target_path = REPO_DIR / repo_name

    if target_path.exists():
        return {"status": "already exists", "path": str(target_path)}

    try:
        subprocess.run(
            ["git", "clone", repo_url, str(target_path)],
            check=True,
            timeout=120,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="未找到 git 命令，请先安装 Git 并确保它在 PATH 中",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail="克隆超时，请检查网络或稍后重试",
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise HTTPException(status_code=400, detail=f"克隆失败：{message}") from exc

    return {"status": "success", "path": str(target_path)}


@app.get("/analyze")
def analyze(repo_name: str):
    repo_path = get_repo_path(repo_name)
    stats, core_dirs = analyze_repo(repo_path)

    return {
        "project_name": repo_name,
        **stats,
        "core_directories": core_dirs,
    }


@app.get("/summarize")
def summarize(repo_name: str):
    repo_path = get_repo_path(repo_name)
    readme = read_readme(repo_path)

    if not readme:
        raise HTTPException(status_code=404, detail="README 不存在")

    return {
        "project_name": repo_name,
        "summary": summarize_readme(readme),
    }


@app.post("/index")
def index_repo(request: IndexRequest):
    if not request.force_rebuild:
        persisted = load_persisted_index(request.repo_name)

        if persisted:
            return {
                "project_name": request.repo_name,
                "status": "loaded",
                "embedding_backend": persisted["embedding_backend"],
                "chunks": len(persisted["chunks"]),
                "persisted": True,
            }

    data = build_index(request.repo_name)

    return {
        "project_name": request.repo_name,
        "status": "success",
        "embedding_backend": data["embedding_backend"],
        "chunks": len(data["chunks"]),
        "persisted": data["persisted"],
    }


@app.delete("/index")
def delete_index(repo_name: str):
    existed, index_path = delete_index_data(repo_name)

    return {
        "project_name": repo_name,
        "status": "deleted" if existed else "not_found",
        "path": str(index_path),
    }


@app.get("/chunks")
def list_chunks(repo_name: str, limit: int = 20):
    data = get_or_build_index(repo_name)
    chunks = data["chunks"][: max(0, min(limit, 100))]

    return {
        "project_name": repo_name,
        "total_chunks": len(data["chunks"]),
        "returned_chunks": len(chunks),
        "chunks": [
            {
                "path": chunk["relative_path"],
                "chunk_id": chunk["chunk_id"],
                "preview": chunk["content"][:300],
            }
            for chunk in chunks
        ],
    }


@app.post("/search")
def search(request: SearchRequest):
    return {
        "project_name": request.repo_name,
        "query": request.query,
        "results": search_chunks(request.repo_name, request.query, request.top_k),
    }


@app.post("/ask")
def ask(request: AskRequest):
    total_start = time.perf_counter()
    search_start = time.perf_counter()
    search_top_k = max(request.top_k, 8)
    contexts = search_chunks(request.repo_name, request.question, search_top_k)
    search_ms = round((time.perf_counter() - search_start) * 1000, 2)

    if not contexts:
        raise HTTPException(status_code=404, detail="没有检索到相关代码片段")

    model_status = "success"
    sources = build_sources(contexts)
    confidence = estimate_confidence(contexts)
    llm_ms = 0.0

    try:
        llm_start = time.perf_counter()
        answer = answer_with_llm(request.question, contexts)
        llm_ms = round((time.perf_counter() - llm_start) * 1000, 2)
    except Exception as exc:
        llm_ms = round((time.perf_counter() - llm_start) * 1000, 2)
        model_status = "failed"
        confidence = {
            "level": "low",
            "score": min(confidence["score"], 0.3),
            "reason": f"Model call failed. {confidence['reason']}",
        }
        answer = build_fallback_answer(
            request.question,
            contexts,
            format_model_error(exc),
        )

    response = {
        "project_name": request.repo_name,
        "question": request.question,
        "model_status": model_status,
        "confidence": confidence,
        "sources": sources,
        "timing": {
            "search_ms": search_ms,
            "llm_ms": llm_ms,
            "total_ms": round((time.perf_counter() - total_start) * 1000, 2),
        },
        "answer": answer,
    }

    if request.debug:
        response["contexts"] = contexts

    return response
