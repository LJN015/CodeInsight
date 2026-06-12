from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize

from settings import get_setting


class EmbeddingBackend:
    def __init__(self):
        self.name = "hashing-vectorizer"
        self.model_name = get_setting(
            "EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        self.local_only = get_setting("EMBEDDING_LOCAL_ONLY", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        self.query_prefix = get_setting("EMBEDDING_QUERY_PREFIX", "")
        self.document_prefix = get_setting("EMBEDDING_DOCUMENT_PREFIX", "")
        self.model = None
        self._sentence_transformer_checked = False
        self.vectorizer = HashingVectorizer(
            n_features=384,
            alternate_sign=False,
            norm=None,
            analyzer="word",
            ngram_range=(1, 2),
        )

    def _load_sentence_transformer(self):
        if self._sentence_transformer_checked:
            return

        self._sentence_transformer_checked = True

        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(
                self.model_name,
                local_files_only=self.local_only,
            )
            self.name = self.model_name
        except Exception as exc:
            print(
                "sentence-transformers 不可用，使用本地 HashingVectorizer 兜底: "
                f"{exc}"
            )

    def encode(self, texts, kind="document"):
        self._load_sentence_transformer()

        if self.model is not None:
            prefix = self.query_prefix if kind == "query" else self.document_prefix
            encoded_texts = [f"{prefix}{text}" for text in texts]
            vectors = self.model.encode(
                encoded_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return vectors.astype("float32")

        vectors = self.vectorizer.transform(texts)
        vectors = normalize(vectors, norm="l2", copy=False)
        return vectors.astype("float32").toarray()


embedding_backend = EmbeddingBackend()


def current_embedding_info():
    probe = embedding_backend.encode(["dimension probe"], kind="document")

    return {
        "embedding_backend": embedding_backend.name,
        "embedding_model": embedding_backend.model_name,
        "embedding_local_only": embedding_backend.local_only,
        "dimension": int(probe.shape[1]),
    }
