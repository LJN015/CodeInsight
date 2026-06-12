from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "embedding_backend" in data


def test_repos_contains_flask():
    response = client.get("/repos")

    assert response.status_code == 200
    repos = response.json()["repos"]
    assert any(repo["repo_name"] == "flask" for repo in repos)


def test_clone_rejects_invalid_url():
    response = client.post("/clone", params={"repo_url": "not-a-git-url"})

    assert response.status_code == 400
    assert "仓库 URL 格式不正确" in response.json()["detail"]


def test_clone_existing_repo_does_not_call_git():
    response = client.post(
        "/clone",
        params={"repo_url": "https://github.com/pallets/flask.git"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "already exists"


def test_search_route_hits_core_sources():
    response = client.post(
        "/search",
        json={
            "repo_name": "flask",
            "query": "Flask 是如何把 @app.route 注册成 URL 规则的？",
            "top_k": 8,
        },
    )

    assert response.status_code == 200
    paths = [item["path"] for item in response.json()["results"]]
    assert "src\\flask\\sansio\\scaffold.py" in paths
    assert "src\\flask\\sansio\\app.py" in paths


def test_search_config_hits_config_source():
    response = client.post(
        "/search",
        json={
            "repo_name": "flask",
            "query": "Flask 配置对象如何从文件、环境变量或对象中加载配置？",
            "top_k": 8,
        },
    )

    assert response.status_code == 200
    paths = [item["path"] for item in response.json()["results"]]
    assert "src\\flask\\config.py" in paths


def test_ask_debug_false_hides_contexts():
    response = client.post(
        "/ask",
        json={
            "repo_name": "flask",
            "question": "Flask 是如何把 @app.route 注册成 URL 规则的？",
            "top_k": 8,
            "debug": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "contexts" not in data
    assert "sources" in data
    assert "confidence" in data
    assert "timing" in data


def test_delete_index_endpoint_is_idempotent():
    response = client.delete("/index?repo_name=__missing_test_repo__")

    assert response.status_code == 200
    assert response.json()["status"] == "not_found"
