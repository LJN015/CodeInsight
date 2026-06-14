from evaluate_retrieval import normalize_path, score_case


def test_normalize_path_handles_windows_and_case():
    assert normalize_path("SRC\\Flask\\App.py") == "src/flask/app.py"


def test_score_case_reports_hits_and_misses():
    case = {
        "id": "sample",
        "question": "How does routing work?",
        "expected_paths": [
            "src/flask/sansio/scaffold.py",
            "src/flask/sansio/app.py",
        ],
    }
    results = [
        {
            "path": "src\\flask\\sansio\\scaffold.py",
            "chunk_id": 1,
            "score": 2.5,
            "vector_score": 0.5,
            "keyword_score": 2.0,
        },
        {
            "path": "src\\flask\\testing.py",
            "chunk_id": 0,
            "score": 1.0,
            "vector_score": 1.0,
            "keyword_score": 0.0,
        },
    ]

    report = score_case(case, results)

    assert report["hit_count"] == 1
    assert report["expected_count"] == 2
    assert report["recall"] == 0.5
    assert report["hit_paths"] == ["src/flask/sansio/scaffold.py"]
    assert report["missed_paths"] == ["src/flask/sansio/app.py"]
