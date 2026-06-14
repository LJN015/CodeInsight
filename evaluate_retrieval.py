import argparse
import json
from pathlib import Path

from retrieval import search_chunks


DEFAULT_EVAL_FILE = Path("eval_cases.json")


def normalize_path(path: str):
    return path.replace("\\", "/").strip().lower()


def load_eval_cases(path=DEFAULT_EVAL_FILE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data


def score_case(case, results):
    expected_paths = {normalize_path(path) for path in case["expected_paths"]}
    returned_paths = {normalize_path(item["path"]) for item in results}
    hit_paths = sorted(expected_paths & returned_paths)
    missed_paths = sorted(expected_paths - returned_paths)
    recall = len(hit_paths) / len(expected_paths) if expected_paths else 0.0

    return {
        "id": case["id"],
        "question": case["question"],
        "expected_count": len(expected_paths),
        "hit_count": len(hit_paths),
        "recall": round(recall, 4),
        "hit_paths": hit_paths,
        "missed_paths": missed_paths,
        "top_results": [
            {
                "path": item["path"],
                "chunk_id": item["chunk_id"],
                "score": round(item["score"], 4),
                "vector_score": round(item.get("vector_score", 0.0), 4),
                "keyword_score": round(item.get("keyword_score", 0.0), 4),
            }
            for item in results[:5]
        ],
    }


def evaluate_cases(eval_data, repo_name=None, top_k=None):
    repo_name = repo_name or eval_data["repo_name"]
    reports = []

    for case in eval_data["cases"]:
        case_top_k = top_k or case.get("top_k", 8)
        results = search_chunks(repo_name, case["question"], case_top_k)
        reports.append(score_case(case, results))

    total_expected = sum(item["expected_count"] for item in reports)
    total_hits = sum(item["hit_count"] for item in reports)
    macro_recall = (
        sum(item["recall"] for item in reports) / len(reports) if reports else 0.0
    )
    micro_recall = total_hits / total_expected if total_expected else 0.0

    return {
        "repo_name": repo_name,
        "case_count": len(reports),
        "macro_recall": round(macro_recall, 4),
        "micro_recall": round(micro_recall, 4),
        "cases": reports,
    }


def print_report(report):
    print(f"repo: {report['repo_name']}")
    print(f"cases: {report['case_count']}")
    print(f"macro_recall: {report['macro_recall']:.2%}")
    print(f"micro_recall: {report['micro_recall']:.2%}")
    print()

    for item in report["cases"]:
        status = "PASS" if not item["missed_paths"] else "MISS"
        print(
            f"[{status}] {item['id']} "
            f"recall={item['recall']:.2%} "
            f"hits={item['hit_count']}/{item['expected_count']}"
        )

        if item["missed_paths"]:
            print("  missed:")
            for path in item["missed_paths"]:
                print(f"    - {path}")

        print("  top_results:")
        for result in item["top_results"]:
            print(
                "    - "
                f"{result['path']}#chunk-{result['chunk_id']} "
                f"score={result['score']}"
            )
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate CodeInsight retrieval against expected source files."
    )
    parser.add_argument("--file", default=str(DEFAULT_EVAL_FILE))
    parser.add_argument("--repo", default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Exit with code 1 if micro recall is below this value, e.g. 0.8.",
    )
    args = parser.parse_args()

    eval_data = load_eval_cases(args.file)
    report = evaluate_cases(eval_data, repo_name=args.repo, top_k=args.top_k)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)

    if args.fail_under is not None and report["micro_recall"] < args.fail_under:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
