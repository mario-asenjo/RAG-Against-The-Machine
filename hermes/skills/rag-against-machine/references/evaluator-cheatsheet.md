# Evaluator cheat sheet

- Python >= 3.10; `uv sync`.
- Module/CLI: `uv run python -m src <command>`.
- Index: max 300s.
- Search docs+code private: 200 questions max 90s warm.
- Docs Recall@5 >= 0.80.
- Code Recall@5 >= 0.50.
- Chunk/result max 2000 chars.
- Exact `data/raw/vllm-0.10.1/...` path.
- Same-file source overlap evaluator threshold: IoU > 0.05 per supplied corrector guide.
- Required commands: index/search/search_dataset/answer/answer_dataset/evaluate.
- Fire, Pydantic, tqdm, flake8, mypy.
- Two chunkers: Python + Markdown/text.
- One lexical method: BM25 or TF-IDF.
- Qwen/Qwen3-0.6B must work.
- Edge tests: empty search; gibberish; `answer --k 0`; missing dataset path; no traceback.
- Never import/call moulinette.
