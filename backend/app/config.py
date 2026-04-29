from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = "EduVerse Backend"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = True
    frontend_origin: str = "http://localhost:3000"

    # ── MongoDB (Local) ───────────────────────────────────────────────────────
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "eduverse"
    mongo_oauth_tokens_collection: str = "oauth_tokens"
    mongo_parent_chunks_collection: str = "parent_chunks"
    mongo_child_chunks_collection: str = "child_chunks"
    mongo_child_vector_index_name: str = "vector_index"
    mongo_child_bm25_index_name: str = "text_index"
    mongo_semantic_cache_collection: str = "semantic_cache"
    mongo_semantic_cache_vector_index_name: str = "cache_index"
    mongo_user_profiles_collection: str = "user_profiles"
    mongo_ingestion_jobs_collection: str = "ingestion_jobs"
    mongo_rl_trajectories_collection: str = "rl_trajectories"
    mongo_dpo_pairs_collection: str = "dpo_pairs"
    mongo_model_registry_collection: str = "model_registry"
    mongo_cached_courses_collection: str = "cached_courses"
    mongo_local_courses_collection: str = "local_courses"

    # ── Persistence (Local Disk) ──────────────────────────────────────────────
    data_dir: str = "./data"
    upload_dir: str = "./data/uploads"

    # ── Local Inference (Ollama — Gemma 4) ────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    local_num_threads: int = 8 
    local_context_window: int = 131072  

    # Role-based model mappings for local Gemma 4
    local_orchestrator_model: str = "gemma4:e4b"
    local_tutor_model: str = "gemma4:e4b"
    local_quiz_model: str = "gemma4:e4b"
    local_feedback_model: str = "gemma4:e4b"
    local_critic_model: str = "gemma4:e4b"
    local_vision_model: str = "gemma4:e4b"

    # ── Local RAG ─────────────────────────────────────────
    local_embedding_model: str = "snowflake/snowflake-arctic-embed-m-long"
    local_reranker_model: str = "ms-marco-MiniLM-L-6-v2"

    # ── Chunking ────────────────────────────────────
    parent_chunk_size: int = 4000
    child_chunk_size: int = 1000
    chunk_overlap: int = 200

    # ── Search ───────────────────────────────────────────────────────────
    serper_api_key: str | None = Field(default=None, alias="SERPER_API_KEY")

    # ── Retrieval ───────────────────────────────────
    retrieval_k: int = 150
    reranker_top_n: int = 100

    # ── Grounding Threshold ───────────────────────────────────────────────────
    grounding_threshold: float = 0.35

    # ── LangChain Indexing API dedup state ─────────────
    record_manager_db_url: str = "sqlite:///./data/record_manager_cache.db"

    # ── JWT Security ──────────────────────────────────────────────────────────
    jwt_secret: str = Field(default="", description="MUST be set via JWT_SECRET env var")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080

    # ── Encryption (Fernet — for OAuth token encryption at rest) ──────────────
    fernet_key: str = Field(default="", description="MUST be set via FERNET_KEY env var")

    # ── Internal API secret (NextAuth → backend store-tokens) ─────────────────
    internal_api_secret: str = Field(default="", description="MUST be set via INTERNAL_API_SECRET env var")

    # ── Google OAuth ──────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_url: str = "http://localhost:8765/"

    # ── Cloud Teacher (DPO Distillation ONLY) ────────────
    google_api_key: str = ""
    eval_judge_model: str = "gemini-2.5-pro"

    # ── Autonomous Training via Kaggle ──────────────────────
    kaggle_username: str = ""
    kaggle_key: str = ""
    kaggle_kernel_slug: str = "eduverse-dpo-trainer"
    auto_promote_models: bool = True
    local_adapters_path: str = "./local_weights"
    min_dpo_pairs_for_training: int = 150
    improvement_threshold: float = 0.15
    benchmark_set_size: int = 100

    # ── Admin & RBAC ──────────────────────────────────────────────────────────
    admin_emails: list[str] = []

    # ── LangSmith observability ──────────────────────────────────────────────
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langchain_project: str = "eduverse"

    def validate_secrets(self) -> None:
        """Validate that critical secrets are set in production."""
        if not self.app_debug:  
            if not self.jwt_secret:
                raise ValueError("JWT_SECRET must be set via environment variable in production")
            if not self.fernet_key:
                raise ValueError("FERNET_KEY must be set via environment variable in production")
            if not self.internal_api_secret:
                raise ValueError("INTERNAL_API_SECRET must be set via environment variable in production")

    @property
    def has_kaggle(self) -> bool:
        return bool(self.kaggle_username and self.kaggle_key)

    @property
    def has_google_api(self) -> bool:
        return bool(self.google_api_key)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
