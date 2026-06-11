from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ANTHROPIC_API_KEY: str
    GIT_REPOS_BASE_PATH: str
    SECRET_ENCRYPTION_KEY: str
    ENVIRONMENT: str = "development"
    APP_BASE_URL: str = "http://localhost"

    # Post-receive hook — if set, trigger endpoint requires matching X-Hook-Secret header
    HOOK_SECRET: str = ""
    # URL baked into the post-receive hook script so it can call back to the API.
    # In Docker set this to http://api:8000; locally it stays http://localhost:8000.
    HOOK_CALLBACK_URL: str = "http://localhost:8000"

    # SSH git service — used to build the clone URL shown in the UI
    GIT_SSH_HOST: str = "localhost"
    GIT_SSH_PORT: int = 2222

    # Email — all optional; if SMTP_HOST is unset, notifications log only
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@gatekeeper.local"
    SMTP_USE_TLS: bool = True
    APPROVER_EMAILS: str = ""  # comma-separated fallback list

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


_SENSITIVE = {
    "SECRET_KEY", "SECRET_ENCRYPTION_KEY", "ANTHROPIC_API_KEY",
    "SMTP_PASSWORD", "HOOK_SECRET",
}


class _SafeSettings(Settings):
    def __repr__(self) -> str:
        pairs = []
        for k, v in self.__dict__.items():
            pairs.append(f"{k}={'***' if k.upper() in _SENSITIVE else repr(v)}")
        return f"Settings({', '.join(pairs)})"

    def __str__(self) -> str:
        return self.__repr__()


settings = _SafeSettings()
