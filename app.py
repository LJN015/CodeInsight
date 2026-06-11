from fastapi import FastAPI
import os
import subprocess
from fastapi import FastAPI
from openai import OpenAI

app = FastAPI()

client = OpenAI(
    api_key = "sk-8929b6c022f74905ac70c49ce8e1d5e7",
    base_url="https://api.deepseek.com"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(BASE_DIR, "repos")

os.makedirs(REPO_DIR, exist_ok=True)


@app.get("/")
def root():
    return {"message": "CodeInsight is running!"}


@app.post("/clone")
def clone_repo(repo_url: str):
    repo_name = repo_url.rstrip("/").split("/")[-1]

    target_path = os.path.join(REPO_DIR, repo_name)

    if os.path.exists(target_path):
        return {
            "status": "already exists",
            "path": target_path
        }

    print("开始 clone...")

    subprocess.run(
        ["git", "clone", repo_url, target_path],
        check=True,
        timeout=120
    )

    print("clone 完成")

    return {
        "status": "success",
        "path": target_path
    }

def analyze_repo(repo_path):
    stats = {
        "total_files": 0,
        "python_files": 0,
        "markdown_files": 0,
        "javascript_files": 0
    }

    core_dirs = []

    for root, dirs, files in os.walk(repo_path):

        # 记录第一层目录
        if root == repo_path:
            core_dirs.extend(dirs)

        for file in files:
            stats["total_files"] += 1

            if file.endswith(".py"):
                stats["python_files"] += 1

            elif file.endswith(".md"):
                stats["markdown_files"] += 1

            elif file.endswith(".js"):
                stats["javascript_files"] += 1

    return stats, core_dirs

@app.get("/analyze")
def analyze(repo_name: str):

    repo_path = os.path.join(REPO_DIR, repo_name)

    print("REPO_DIR =", REPO_DIR)
    print("repo_name =", repo_name)
    print("repo_path =", repo_path)
    print("exists =", os.path.exists(repo_path))

    if not os.path.exists(repo_path):
        return {
            "error": "仓库不存在"
        }

    stats, core_dirs = analyze_repo(repo_path)

    return {
        "project_name": repo_name,
        **stats,
        "core_directories": core_dirs
    }

def read_readme(repo_path):
    """
    自动寻找 README 文件并读取内容
    """

    candidates = [
        "README.md",
        "readme.md",
        "README.rst"
    ]

    for filename in candidates:
        path = os.path.join(repo_path, filename)

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    return None

def summarize_readme(readme_text):

    readme_text = readme_text[:3000]

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一名资深软件工程师。"
                    "请根据GitHub项目README生成中文总结。"
                )
            },
            {
                "role": "user",
                "content": f"""
                请总结下面这个GitHub项目：

                要求：
                1. 用一句话说明项目是做什么的；
                2. 总结3个核心功能；
                3. 说明适合学习哪些技术；
                4. 控制在300字以内。

                README：

                {readme_text}
                """
            }
        ]
    )

    return response.choices[0].message.content

@app.get("/summarize")
def summarize(repo_name: str):

    repo_path = os.path.join(REPO_DIR, repo_name)

    if not os.path.exists(repo_path):
        return {"error": "仓库不存在"}

    readme = read_readme(repo_path)

    if not readme:
        return {"error": "README不存在"}

    summary = summarize_readme(readme)

    return {
        "project_name": repo_name,
        "summary": summary
    }