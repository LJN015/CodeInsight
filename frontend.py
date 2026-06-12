import time

import requests
import streamlit as st


DEFAULT_API_BASE = "http://127.0.0.1:8001"


st.set_page_config(
    page_title="CodeInsight",
    page_icon="CI",
    layout="wide",
)


def api_url(path):
    return f"{st.session_state.api_base.rstrip('/')}{path}"


def request_json(method, path, **kwargs):
    try:
        response = requests.request(method, api_url(path), timeout=180, **kwargs)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as exc:
        detail = getattr(exc.response, "text", "") if getattr(exc, "response", None) else ""
        return None, f"{exc}\n{detail}".strip()


def refresh_state():
    health, health_error = request_json("GET", "/health")
    repos, repos_error = request_json("GET", "/repos")
    indexes, indexes_error = request_json("GET", "/indexes")

    st.session_state.health = health
    st.session_state.repos = repos or {"repos": []}
    st.session_state.indexes = indexes or {"indexes": []}
    st.session_state.status_error = health_error or repos_error or indexes_error


def get_index_map():
    return {item["repo_name"]: item for item in st.session_state.indexes.get("indexes", [])}


def render_source(source, context_by_key):
    key = f"{source['path']}#chunk-{source['chunk_id']}"
    with st.expander(f"{source['rank']}. {key}  score={source['score']:.2f}"):
        cols = st.columns(3)
        cols[0].metric("Vector", f"{source.get('vector_score', 0):.2f}")
        cols[1].metric("Keyword", f"{source.get('keyword_score', 0):.2f}")
        cols[2].caption(source.get("reason", "retrieved context"))

        context = context_by_key.get(key)
        if context:
            st.code(context.get("content", ""), language="python")


if "api_base" not in st.session_state:
    st.session_state.api_base = DEFAULT_API_BASE
if "answer" not in st.session_state:
    st.session_state.answer = None
if "health" not in st.session_state:
    st.session_state.health = None
if "repos" not in st.session_state:
    st.session_state.repos = {"repos": []}
if "indexes" not in st.session_state:
    st.session_state.indexes = {"indexes": []}
if "status_error" not in st.session_state:
    st.session_state.status_error = None


st.title("CodeInsight")

with st.sidebar:
    st.subheader("Connection")
    st.session_state.api_base = st.text_input("FastAPI URL", st.session_state.api_base)

    if st.button("Refresh", use_container_width=True):
        refresh_state()

    if st.session_state.health is None:
        refresh_state()

    if st.session_state.status_error:
        st.error(st.session_state.status_error)
    else:
        health = st.session_state.health or {}
        st.success("API connected")
        st.caption(f"Embedding: {health.get('embedding_backend', 'unknown')}")
        st.caption(f"DeepSeek key: {health.get('deepseek_api_key_tail', 'not set')}")


repos = st.session_state.repos.get("repos", [])
repo_names = [repo["repo_name"] for repo in repos]

if not repo_names:
    st.info("No repositories found. Use /clone in Swagger first, then refresh this page.")
    st.stop()

left, right = st.columns([0.34, 0.66], gap="large")

with left:
    st.subheader("Repository")
    selected_repo = st.selectbox("Repo", repo_names)
    repo = next(item for item in repos if item["repo_name"] == selected_repo)
    index_map = get_index_map()
    index_meta = index_map.get(selected_repo)

    cols = st.columns(3)
    cols[0].metric("Files", repo.get("total_files", 0))
    cols[1].metric("Python", repo.get("python_files", 0))
    cols[2].metric("Markdown", repo.get("markdown_files", 0))

    st.caption("Core directories")
    st.write(", ".join(repo.get("core_directories", [])) or "None")

    if index_meta:
        status = "stale" if index_meta.get("stale") else "ready"
        st.info(
            f"Index: {status} | chunks={index_meta.get('chunk_count', '?')} | "
            f"model={index_meta.get('embedding_backend', 'unknown')}"
        )
    else:
        st.warning("No index found for this repository.")

    build_col, delete_col = st.columns(2)
    with build_col:
        if st.button("Build index", type="primary", use_container_width=True):
            with st.spinner("Building index..."):
                data, error = request_json(
                    "POST",
                    "/index",
                    json={"repo_name": selected_repo, "force_rebuild": True},
                )
            if error:
                st.error(error)
            else:
                st.success(f"Indexed {data.get('chunks', 0)} chunks.")
                refresh_state()

    with delete_col:
        if st.button("Delete index", use_container_width=True):
            data, error = request_json("DELETE", f"/index?repo_name={selected_repo}")
            if error:
                st.error(error)
            else:
                st.warning(data.get("status", "deleted"))
                refresh_state()

with right:
    st.subheader("Ask")

    examples = [
        "Flask 是如何把 @app.route 注册成 URL 规则的？",
        "Flask 配置对象如何从文件、环境变量或对象中加载配置？",
        "Flask 测试客户端如何构造 environ 并模拟 HTTP 请求？",
        "Flask 的应用上下文和请求上下文分别在什么代码里创建和释放？",
    ]
    question = st.text_area("Question", value=examples[0], height=100)

    controls = st.columns([0.24, 0.24, 0.52])
    top_k = controls[0].slider("Top K", 3, 10, 8)
    debug = controls[1].toggle("Show contexts", value=True)
    ask_clicked = controls[2].button("Ask CodeInsight", type="primary", use_container_width=True)

    with st.expander("Examples"):
        for example in examples:
            st.code(example, language="text")

    if ask_clicked:
        payload = {
            "repo_name": selected_repo,
            "question": question,
            "top_k": top_k,
            "debug": debug,
        }
        with st.spinner("Retrieving code and asking the model..."):
            start = time.perf_counter()
            data, error = request_json("POST", "/ask", json=payload)
            elapsed_ms = (time.perf_counter() - start) * 1000

        if error:
            st.error(error)
        else:
            data["_client_elapsed_ms"] = elapsed_ms
            st.session_state.answer = data

    data = st.session_state.answer
    if data:
        confidence = data.get("confidence", {})
        timing = data.get("timing", {})

        metric_cols = st.columns(4)
        metric_cols[0].metric("Confidence", confidence.get("level", "unknown"))
        metric_cols[1].metric("Score", confidence.get("score", 0))
        metric_cols[2].metric("Search", f"{timing.get('search_ms', 0):.0f} ms")
        metric_cols[3].metric("LLM", f"{timing.get('llm_ms', 0):.0f} ms")

        if data.get("model_status") != "success":
            st.warning(f"Model status: {data.get('model_status')}")

        st.markdown(data.get("answer", ""))

        st.subheader("Sources")
        contexts = data.get("contexts", [])
        context_by_key = {
            f"{item['path']}#chunk-{item['chunk_id']}": item for item in contexts
        }

        for source in data.get("sources", []):
            render_source(source, context_by_key)
