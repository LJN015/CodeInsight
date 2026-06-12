from pydantic import BaseModel, Field


class RepoRequest(BaseModel):
    repo_name: str = Field(..., examples=["flask"])


class IndexRequest(RepoRequest):
    force_rebuild: bool = False


class AskRequest(RepoRequest):
    question: str = Field(..., examples=["Flask 是如何实现路由注册的？"])
    top_k: int = Field(default=5, ge=1, le=10)
    debug: bool = True


class SearchRequest(RepoRequest):
    query: str = Field(..., examples=["routing register blueprint"])
    top_k: int = Field(default=5, ge=1, le=20)
