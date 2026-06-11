import os
from langchain_text_splitters import RecursiveCharacterTextSplitter

def load_python_files(repo_path):
    documents = []

    IGNORE_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    "docs",
    "tests",
    "examples",
    "requirements"
}

    for root, dirs, files in os.walk(repo_path):

        dirs[:] = [
            d for d in dirs
            if d not in IGNORE_DIRS
        ]

        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)

                try:
                    with open(path,
                              "r",
                              encoding="utf-8",
                              errors="ignore") as f:

                        content = f.read()

                    documents.append({
                        "path": path,
                        "content": content
                    })

                except Exception as e:
                    print("读取失败：", path)

    return documents

def split_documents(documents):

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks = []

    for doc in documents:
        parts = splitter.split_text(doc["content"])

        for part in parts:
            chunks.append({
                "path": doc["path"],
                "content": part
            })

    return chunks

if __name__ == "__main__":
    docs = load_python_files("repos/flask")

    print("Python文件数：", len(docs))

    print(docs[0]["path"])

    print(docs[0]["content"][:300])

    chunks = split_documents(docs)

    print("代码块数量：", len(chunks))

    print(chunks[0]["path"])

    print(chunks[0]["content"][:300])

    print("\n前5个文件：")

    for doc in docs[:5]:
        print(doc["path"])