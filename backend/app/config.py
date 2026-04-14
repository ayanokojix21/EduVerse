from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = "EduVerse Backend"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = True
    frontend_origin: str = "http://localhost:3000"

    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "eduverse"
    mongo_oauth_tokens_collection: str = "oauth_tokens"
    mongo_child_chunks_collection: str = "course_chunks_child"
    mongo_parent_chunks_collection: str = "course_chunks_parent"
    mongo_semantic_cache_collection: str = "semantic_cache"
    mongo_user_profiles_collection: str = "user_profiles"
    mongo_checkpoints_collection: str = "checkpoints"
    mongo_checkpoint_writes_collection: str = "checkpoint_writes"
    mongo_timetables_collection: str = "timetables"
    mongo_events_collection: str = "student_events"
    mongo_chat_sessions_collection: str = "chat_sessions"
    mongo_ingestion_jobs_collection: str = "ingestion_jobs"

    # Atlas search index names
    mongo_child_vector_index_name: str = "child_vector_index"
    mongo_child_bm25_index_name: str = "child_bm25_index"
    mongo_semantic_cache_vector_index_name: str = "cache_vector_index"

    # LangChain Indexing API dedup state (SQLite)
    record_manager_db_url: str = "sqlite:///record_manager_cache.db"

    # ── JWT (app auth) ────────────────────────────────────────────────────────
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # ── Encryption (Fernet) ───────────────────────────────────────────────────
    fernet_key: str = "replace-with-generated-fernet-key"

    # ── Internal API secret (NextAuth → backend store-tokens) ─────────────────
    # Generate: python -c "import secrets; print(secrets.token_urlsafe(48))"
    internal_api_secret: str = "replace-with-random-64-char-string"

    # ── Google OAuth ──────────────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_url: str = "http://localhost:8765/"
    google_api_key: str = ""

    # ── Groq — all agent models ───────────────────────────────────────────────
    groq_api_key: str = ""
    groq_vision_enabled: bool = True
    
    # ── Cloudinary ────────────────────────────────────────────────────────────
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    groq_vision_temperature: float = 0.0
    groq_vision_max_tokens: int = 1024

    # Agent LLM model IDs
    groq_supervisor_model: str = "llama-3.1-8b-instant"
    groq_rewriter_model: str = "llama-3.1-8b-instant"
    groq_tutor_a_model: str = "llama-3.3-70b-versatile"
    groq_tutor_b_model: str = "openai/gpt-oss-120b"
    groq_synthesizer_model: str = "llama-3.3-70b-versatile"
    groq_critic_model: str = "llama-3.3-70b-versatile"
    groq_timetable_model: str = "openai/gpt-oss-20b"

    # ── Nomic Embeddings ──────────────────────────────────────────────────────
    nomic_api_key: str = ""
    nomic_embedding_model: str = "nomic-embed-text-v1.5"

    # ── Chunking ──────────────────────────────────────────────────────────────
    parent_chunk_size: int = 2000
    child_chunk_size: int = 300
    chunk_overlap: int = 100

    # ── Retrieval ─────────────────────────────────────────────────────────────
    retrieval_k: int = 30           # Candidates from hybrid search
    reranker_top_n: int = 4         # Top-N after Cohere cross-encoder reranking
    reranker_model: str = "rerank-v3.5"  # Current Cohere standard
    cohere_api_key: str = ""

    # ── Grounding Threshold ───────────────────────────────────────────────────
    grounding_threshold: float = 0.35  # threshold for grounding confidence labels

    # ── LangSmith observability ───────────────────────────────────────────────
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langchain_project: str = "eduverse-v11"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
