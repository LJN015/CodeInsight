import argparse

from sentence_transformers import SentenceTransformer


def main():
    parser = argparse.ArgumentParser(description="Download an embedding model locally.")
    parser.add_argument(
        "--model",
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        help="SentenceTransformer model name or local path.",
    )
    args = parser.parse_args()

    model = SentenceTransformer(args.model)
    print("model loaded:", args.model)
    print("embedding dimension:", model.get_sentence_embedding_dimension())


if __name__ == "__main__":
    main()
