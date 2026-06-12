import re

from embedding_service import embedding_backend
from index_store import get_or_build_index


QUERY_EXPANSIONS = {
    "\u8def\u7531": [
        "route",
        "routing",
        "add_url_rule",
        "url_rule",
        "url_map",
        "Rule",
        "Map",
        "view_functions",
        "endpoint",
        "werkzeug.routing",
    ],
    "\u6ce8\u518c": [
        "register",
        "decorator",
        "add_url_rule",
        "view_func",
        "view_functions",
        "endpoint",
    ],
    "\u84dd\u56fe": ["blueprint", "Blueprint", "register_blueprint"],
    "\u8bf7\u6c42": [
        "request",
        "dispatch_request",
        "full_dispatch_request",
        "wsgi_app",
        "request_context",
        "RequestContext",
        "preprocess_request",
        "finalize_request",
        "view_functions",
    ],
    "\u5206\u53d1": ["dispatch_request", "full_dispatch_request", "view_functions"],
    "\u89c6\u56fe": ["view", "view_func", "view_functions", "dispatch_request"],
    "CLI": ["cli", "FlaskGroup", "ScriptInfo", "load_app", "locate_app", "main"],
    "\u547d\u4ee4": ["cli", "command", "FlaskGroup", "ScriptInfo"],
    "\u542f\u52a8": ["run", "wsgi_app", "FlaskGroup", "load_app"],
    "\u52a0\u8f7d": ["load_app", "locate_app", "ScriptInfo", "import_string"],
    "\u6d4b\u8bd5": ["test_client", "FlaskClient", "EnvironBuilder", "open", "invoke"],
    "\u5ba2\u6237\u7aef": ["test_client", "FlaskClient", "EnvironBuilder", "open"],
    "\u6a21\u62df": ["test_client", "FlaskClient", "EnvironBuilder", "environ"],
    "\u8ba4\u8bc1": ["auth", "authentication", "login", "session"],
    "\u9519\u8bef": [
        "errorhandler",
        "register_error_handler",
        "error_handler_spec",
        "_find_error_handler",
        "handle_exception",
        "handle_user_exception",
    ],
    "\u5904\u7406": ["handler", "errorhandler", "register_error_handler"],
    "\u4e0a\u4e0b\u6587": [
        "AppContext",
        "RequestContext",
        "app_context",
        "request_context",
        "push",
        "pop",
        "ctx.py",
    ],
    "\u5e94\u7528\u4e0a\u4e0b\u6587": ["AppContext", "app_context", "push", "pop"],
    "\u8bf7\u6c42\u4e0a\u4e0b\u6587": ["RequestContext", "request_context", "push", "pop"],
    "\u914d\u7f6e": [
        "Config",
        "from_object",
        "from_pyfile",
        "from_prefixed_env",
        "from_envvar",
        "from_mapping",
    ],
    "\u73af\u5883\u53d8\u91cf": ["from_prefixed_env", "from_envvar", "os.environ"],
    "\u6587\u4ef6": ["from_pyfile", "from_file"],
    "\u5bf9\u8c61": ["from_object", "from_mapping"],
    "\u6570\u636e\u5e93": [
        "database",
        "db",
        "sql",
        "repository",
        "dao",
        "model",
        "migration",
        "connection",
        "session",
    ],
    "\u7f13\u5b58": ["cache", "redis", "memo", "ttl"],
    "\u6743\u9650": ["permission", "authorize", "authorization", "role", "policy"],
    "API": ["api", "router", "controller", "handler", "endpoint"],
    "\u63a5\u53e3": ["api", "router", "controller", "handler", "endpoint"],
    "\u63a7\u5236\u5668": ["controller", "handler", "route", "endpoint"],
    "\u670d\u52a1": ["service", "manager", "provider", "usecase"],
    "\u6a21\u578b": ["model", "entity", "schema", "dto"],
    "\u65e5\u5fd7": ["logger", "logging", "log"],
    "\u4e2d\u95f4\u4ef6": ["middleware", "interceptor", "filter"],
    "\u5165\u53e3": ["main", "entry", "bootstrap", "startup", "application"],
}

FILENAME_HINTS = {
    "auth": ["auth", "login", "session", "jwt", "token", "permission", "role"],
    "config": ["config", "settings", "env", "option"],
    "database": ["database", "db", "sql", "repository", "dao", "migration"],
    "route": ["route", "router", "url", "endpoint"],
    "controller": ["controller", "handler", "view"],
    "service": ["service", "manager", "provider", "usecase"],
    "model": ["model", "entity", "schema", "dto"],
    "test": ["test", "spec", "mock", "fixture"],
    "middleware": ["middleware", "interceptor", "filter"],
    "logging": ["log", "logger", "logging"],
    "main": ["main", "entry", "bootstrap", "startup", "application"],
}


def expand_query(query: str):
    terms = [query]
    lowered_query = query.lower()

    for keyword, expansions in QUERY_EXPANSIONS.items():
        if keyword in query:
            terms.extend(expansions)

    if "route" in lowered_query or "add_url_rule" in lowered_query:
        terms.extend(QUERY_EXPANSIONS["\u8def\u7531"])

    if "blueprint" in lowered_query:
        terms.extend(QUERY_EXPANSIONS["\u84dd\u56fe"])

    if "cli" in lowered_query:
        terms.extend(QUERY_EXPANSIONS["CLI"])

    if "test_client" in lowered_query or "flaskclient" in lowered_query:
        terms.extend(QUERY_EXPANSIONS["\u6d4b\u8bd5"])

    if "dispatch" in lowered_query:
        terms.extend(QUERY_EXPANSIONS["\u5206\u53d1"])

    for hint_terms in FILENAME_HINTS.values():
        if any(term in lowered_query for term in hint_terms):
            terms.extend(hint_terms)

    if "Flask" in query or "flask" in query:
        terms.extend(["Flask"])

    seen = []
    for term in terms:
        if term and term not in seen:
            seen.append(term)

    return " ".join(seen), seen


def tokenize_query_terms(query: str, expanded_terms):
    terms = set()

    for term in expanded_terms:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\.]*", term):
            terms.add(term.lower())

    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", query):
        terms.add(token.lower())

    return terms


def keyword_score(chunk, terms):
    content = chunk["content"].lower()
    path = chunk["relative_path"].lower()
    score = 0.0
    route_related = bool(
        terms
        & {
            "route",
            "routing",
            "add_url_rule",
            "url_rule",
            "url_map",
            "rule",
            "view_functions",
            "endpoint",
            "werkzeug.routing",
        }
    )
    cli_related = bool(
        terms
        & {
            "cli",
            "command",
            "flaskgroup",
            "scriptinfo",
            "load_app",
            "locate_app",
            "main",
        }
    )
    test_related = bool(
        terms
        & {
            "test_client",
            "flaskclient",
            "environbuilder",
            "invoke",
            "environ",
        }
    )
    dispatch_related = bool(
        terms
        & {
            "dispatch_request",
            "full_dispatch_request",
            "wsgi_app",
            "request_context",
            "preprocess_request",
            "finalize_request",
        }
    )
    error_related = bool(
        terms
        & {
            "errorhandler",
            "register_error_handler",
            "error_handler_spec",
            "_find_error_handler",
            "handle_exception",
            "handle_user_exception",
        }
    )
    context_related = bool(
        terms
        & {
            "appcontext",
            "requestcontext",
            "app_context",
            "request_context",
            "push",
            "pop",
            "ctx.py",
        }
    )
    config_related = bool(
        terms
        & {
            "config",
            "from_object",
            "from_pyfile",
            "from_prefixed_env",
            "from_envvar",
            "from_mapping",
        }
    )

    for term in terms:
        term_count = content.count(term)
        path_count = path.count(term)

        if term_count:
            score += min(term_count, 5) * 0.25

        if path_count:
            score += 0.4

    if path.endswith(".py"):
        score += 0.2

    if path.startswith("src\\") or path.startswith("src/"):
        score += 0.3

    if "changes" in path or "readme" in path:
        score -= 0.4

    path_parts = set(re.split(r"[^a-z0-9_]+", path))
    for hint_name, hint_terms in FILENAME_HINTS.items():
        if hint_name in path_parts and terms.intersection(hint_terms):
            score += 1.0

    if route_related and "def add_url_rule" in content:
        score += 2.0

    if route_related and "add_url_rule" in content:
        score += 1.5

    if route_related and "def route" in content:
        score += 1.0

    if route_related and "self.url_map.add" in content:
        score += 1.5

    if route_related and "self.view_functions" in content:
        score += 1.0

    if route_related and "endpoint = _endpoint_from_view_func" in content:
        score += 1.0

    if route_related and "self.url_rule_class" in content:
        score += 1.0

    if cli_related and path.endswith("cli.py"):
        score += 1.5

    if cli_related and ("class flaskgroup" in content or "class scriptinfo" in content):
        score += 1.5

    if cli_related and ("def locate_app" in content or "def load_app" in content):
        score += 1.2

    if test_related and path.endswith("testing.py"):
        score += 1.5

    if test_related and ("class flaskclient" in content or "def open" in content):
        score += 1.5

    if test_related and "environbuilder" in content:
        score += 1.0

    if dispatch_related and path.endswith("app.py"):
        score += 0.8

    if dispatch_related and (
        "def wsgi_app" in content
        or "def full_dispatch_request" in content
        or "def dispatch_request" in content
    ):
        score += 1.8

    if error_related and ("scaffold.py" in path or path.endswith("app.py")):
        score += 1.0

    if error_related and (
        "def errorhandler" in content
        or "def register_error_handler" in content
        or "def _find_error_handler" in content
        or "error_handler_spec" in content
    ):
        score += 2.0

    if context_related and path.endswith("ctx.py"):
        score += 2.0

    if context_related and (
        "class appcontext" in content
        or "class requestcontext" in content
        or "def app_context" in content
        or "def request_context" in content
        or "def push" in content
        or "def pop" in content
    ):
        score += 1.5

    if config_related and path.endswith("config.py"):
        score += 2.0

    if config_related and (
        "def from_object" in content
        or "def from_pyfile" in content
        or "def from_prefixed_env" in content
        or "def from_envvar" in content
        or "class config" in content
    ):
        score += 1.5

    return score


def search_chunks(repo_name: str, query: str, top_k: int):
    data = get_or_build_index(repo_name)
    expanded_query, expanded_terms = expand_query(query)
    keyword_terms = tokenize_query_terms(query, expanded_terms)
    candidate_count = min(len(data["chunks"]), max(top_k * 8, 40))
    query_vector = embedding_backend.encode([expanded_query], kind="query")
    scores, indices = data["index"].search(query_vector, candidate_count)

    candidates = {}
    for score, index in zip(scores[0], indices[0]):
        if index < 0:
            continue

        candidates[int(index)] = float(score)

    keyword_ranked = sorted(
        (
            (keyword_score(chunk, keyword_terms), index)
            for index, chunk in enumerate(data["chunks"])
        ),
        reverse=True,
    )

    for score, index in keyword_ranked[:candidate_count]:
        if score <= 0:
            continue

        candidates[index] = max(candidates.get(index, 0.0), 0.0)

    ranked = []
    for index, vector_score in candidates.items():
        chunk = data["chunks"][index]
        lexical_score = keyword_score(chunk, keyword_terms)
        final_score = vector_score + lexical_score
        ranked.append((final_score, vector_score, lexical_score, index))

    ranked.sort(reverse=True)

    results = []
    for final_score, vector_score, lexical_score, index in ranked[:top_k]:
        chunk = data["chunks"][index]
        results.append(
            {
                "score": float(final_score),
                "vector_score": float(vector_score),
                "keyword_score": float(lexical_score),
                "path": chunk["relative_path"],
                "chunk_id": chunk["chunk_id"],
                "content": chunk["content"][:1800],
            }
        )

    return results


def build_sources(contexts):
    sources = []

    for index, item in enumerate(contexts, 1):
        reasons = []

        if item.get("keyword_score", 0) > 0:
            reasons.append("matched query keywords")

        if item.get("vector_score", 0) > 0.45:
            reasons.append("semantic match")

        path = item["path"].lower()
        if path.endswith(".py"):
            reasons.append("source code")
        elif "readme" in path or "changes" in path:
            reasons.append("documentation/changelog")

        sources.append(
            {
                "rank": index,
                "path": item["path"],
                "chunk_id": item["chunk_id"],
                "score": item["score"],
                "vector_score": item.get("vector_score", 0.0),
                "keyword_score": item.get("keyword_score", 0.0),
                "reason": ", ".join(reasons) if reasons else "retrieved context",
            }
        )

    return sources


def estimate_confidence(contexts):
    if not contexts:
        return {
            "level": "low",
            "score": 0.0,
            "reason": "No code context was retrieved.",
        }

    top_score = contexts[0].get("score", 0.0)
    code_contexts = [
        item for item in contexts if item.get("path", "").lower().endswith(".py")
    ]
    unique_files = {item.get("path") for item in contexts}
    keyword_hits = sum(1 for item in contexts if item.get("keyword_score", 0.0) > 0)

    numeric_score = 0.0
    numeric_score += min(top_score / 10, 0.45)
    numeric_score += min(len(code_contexts) / 5, 1.0) * 0.25
    numeric_score += min(len(unique_files) / 4, 1.0) * 0.15
    numeric_score += min(keyword_hits / 4, 1.0) * 0.15
    numeric_score = round(min(numeric_score, 1.0), 2)

    if numeric_score >= 0.75:
        level = "high"
    elif numeric_score >= 0.45:
        level = "medium"
    else:
        level = "low"

    return {
        "level": level,
        "score": numeric_score,
        "reason": (
            f"top_score={top_score:.2f}, code_chunks={len(code_contexts)}, "
            f"unique_files={len(unique_files)}, keyword_hits={keyword_hits}"
        ),
    }
