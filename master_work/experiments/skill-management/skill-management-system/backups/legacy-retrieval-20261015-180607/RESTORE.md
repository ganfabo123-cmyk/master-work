# Legacy retrieval backup

All files in BACKUP_MANIFEST.json are byte-verified copies made before integration.
The legacy skills_tests corpus and embedding_cache.json are included. No .env or API keys are copied.
Run python -B run_mock_session.py mock_session.jsonl from this directory. Supply the existing DYNAMIC_RETRIEVAL_EMBEDDING_* environment variables for remote embeddings.
Generic Trace / trigger / query / retrieval interfaces remain editable in retrieval_program.py.
