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

    # ── MongoDB Atlas ─────────────────────────────────────────────────────────
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
    mongo_chat_sessions_collection: str = "chat_sessions"

    # ── Cloud Inference (Gemma 4 via Google AI Studio) ────────────────────────
    # Tier 1: Routing & Guardrails (Fastest Gemma 4 variant)
    gemma_routing_model: str = "gemma-4-26b-a4b-it"
    # Tier 2: Parallel Swarms & Fast Reasoning (MoE)
    gemma_fast_reasoning_model: str = "gemma-4-26b-a4b-it"
    # Tier 3: Deep Pedagogical Reasoning (Dense)
    gemma_heavy_reasoning_model: str = "gemma-4-31b-it"

    # ── Cloudinary (Document Storage) ─────────────────────────────────────────
    cloudinary_cloud_name: str = Field(default="", alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key: str = Field(default="", alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str = Field(default="", alias="CLOUDINARY_API_SECRET")
    cloudinary_folder: str = "eduverse"

    # ── Nomic (Cloud Embeddings) ───────────────────────────────────────────────
    nomic_api_key: str = Field(default="", alias="NOMIC_API_KEY")
    nomic_embedding_model: str = Field(default="nomic-embed-text-v1.5", alias="NOMIC_EMBEDDING_MODEL")

    # ── Cohere (Cloud Reranker) ────────────────────────────────────────────────
    cohere_api_key: str = Field(default="", alias="COHERE_API_KEY")
    cohere_reranker_model: str = Field(default="rerank-v3.5", alias="RERANKER_MODEL")

    # ── E2B (Cloud Code Sandbox) ───────────────────────────────────────────────
    e2b_api_key: str = Field(default="", alias="E2B_API_KEY")

    # ── Chunking ─────────────────────────────────────────────────────────────
    parent_chunk_size: int = 4000
    child_chunk_size: int = 1000
    chunk_overlap: int = 200
    # Max pages analyzed by vision model per document (prevents API cost explosion)
    max_vision_images_per_doc: int = 10

    # ── Web Search (SerperDev) ────────────────────────────────────────────────
    serper_api_key: str | None = Field(default=None, alias="SERPER_API_KEY")

    # ── Retrieval ─────────────────────────────────────────────────────────────
    retrieval_k: int = 20
    reranker_top_n: int = 5

    # ── Grounding Threshold ───────────────────────────────────────────────────
    grounding_threshold: float = 0.35

    # ── JWT Security ──────────────────────────────────────────────────────────
    jwt_secret: str = Field(default="", description="MUST be set via JWT_SECRET env var")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080

    # ── Encryption (Fernet — for OAuth token encryption at rest) ──────────────
    fernet_key: str = Field(default="", description="MUST be set via FERNET_KEY env var")

    # ── Internal API secret (NextAuth -> backend store-tokens) ────────────────
    internal_api_secret: str = Field(default="", description="MUST be set via INTERNAL_API_SECRET env var")

    # ── Google OAuth ──────────────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_url: str = "http://localhost:8765/"
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/callback/google"

    # ── Cloud Teacher (DPO Distillation ONLY) ─────────────────────────────────
    google_api_key: str = ""
    eval_judge_model: str = "gemini-2.5-pro"

    # ── Autonomous Training via Kaggle ────────────────────────────────────────
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

    # ── LangSmith observability ───────────────────────────────────────────────
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
            if not self.cloudinary_cloud_name:
                raise ValueError("CLOUDINARY_CLOUD_NAME must be set in production")
            if not self.nomic_api_key:
                raise ValueError("NOMIC_API_KEY must be set in production")
            if not self.cohere_api_key:
                raise ValueError("COHERE_API_KEY must be set in production")

    @property
    def has_kaggle(self) -> bool:
        return bool(self.kaggle_username and self.kaggle_key)

    @property
    def has_google_api(self) -> bool:
        return bool(self.google_api_key)

    @property
    def has_cloudinary(self) -> bool:
        return bool(self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
