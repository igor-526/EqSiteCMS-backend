from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=True, alias="DEBUG")
    swagger_title: str = Field(
        default="Equestrian Site CMS Manager", alias="SWAGGER_TITLE"
    )
    workers: int = Field(default=1, alias="WORKERS")

    secret_key: str = Field(default="your-secret-key", alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expires_in_minutes: int = Field(
        default=15, alias="ACCESS_TOKEN_EXPIRES_IN_MINUTES"
    )
    refresh_token_expires_in_days: int = Field(
        default=7, alias="REFRESH_TOKEN_EXPIRES_IN_DAYS"
    )

    cms_panel_domain: str = Field(default="localhost:3000", alias="CMS_PANEL_DOMAIN")
    cms_backend_domain: str = Field(
        default="localhost:8000", alias="CMS_BACKEND_DOMAIN"
    )
    cms_cors_origins_raw: str = Field(default="", alias="CMS_CORS_ORIGINS")

    db_user: str = Field(default="eqsitecmsdev", alias="POSTGRES_USER")
    db_password: str = Field(default="eqsitecmsdev", alias="POSTGRES_PASSWORD")
    db_host: str = Field(default="db", alias="POSTGRES_HOST")
    db_name: str = Field(default="eqsitecmsdev", alias="POSTGRES_NAME")
    db_port: int = Field(default=5432, alias="POSTGRES_PORT")

    # S3 / Minio
    s3_endpoint_url: str = Field(default="http://minio:9000", alias="S3_ENDPOINT_URL")
    s3_access_key: str = Field(default="eqsitecmsminio", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="eqsitecmsminio", alias="S3_SECRET_KEY")
    s3_bucket_name: str = Field(default="gallery", alias="S3_BUCKET_NAME")
    s3_public_endpoint_url: str = Field(
        default="http://localhost:9000", alias="S3_PUBLIC_ENDPOINT_URL"
    )
    s3_public_include_bucket: bool = Field(
        default=True, alias="S3_PUBLIC_INCLUDE_BUCKET"
    )

    # Service key for microservices auth
    service_key: str = Field(default="", alias="SERVICE_KEY")

    # Email Service
    email_service_url: str = Field(
        default="http://email-service:8000", alias="EMAIL_SERVICE_URL"
    )
    notification_service_url: str = Field(
        default="http://notification-service:8000", alias="NOTIFICATION_SERVICE_URL"
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment.lower() != "production":
            return self
        unsafe = {
            "",
            "app",
            "changeme",
            "eqsitecmsdev",
            "eqsitecmsminio",
            "your-secret-key",
        }
        required = {
            "SECRET_KEY": self.secret_key,
            "POSTGRES_PASSWORD": self.db_password,
            "S3_ACCESS_KEY": self.s3_access_key,
            "S3_SECRET_KEY": self.s3_secret_key,
            "SERVICE_KEY": self.service_key,
        }
        invalid = [
            name for name, value in required.items() if value.strip().lower() in unsafe
        ]
        if invalid:
            raise ValueError(
                f"Unsafe or missing production settings: {', '.join(invalid)}"
            )
        return self

    @property
    def cms_cors_origins(self) -> list[str]:
        if self.cms_cors_origins_raw.strip():
            return [
                o.strip() for o in self.cms_cors_origins_raw.split(",") if o.strip()
            ]
        return [
            "http://localhost:3000",
            f"http://{self.cms_panel_domain}",
            f"https://{self.cms_panel_domain}",
        ]

    model_config = SettingsConfigDict(populate_by_name=True)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


class SentrySettings(BaseSettings):
    sentry_enabled: bool = Field(default=False, alias="SENTRY_ENABLED")
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    sentry_environment: str = Field(default="development", alias="SENTRY_ENVIRONMENT")
    sentry_traces_sample_rate: float = Field(default=0.0, alias="SENTRY_TRACES_SAMPLE_RATE", ge=0.0, le=1.0)
    sentry_release: str | None = Field(default=None, alias="SENTRY_RELEASE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> SentrySettings:
        if self.sentry_enabled and not self.sentry_dsn:
            raise ValueError("SENTRY_DSN is required when SENTRY_ENABLED=true")
        return self


class NatsSettings(BaseSettings):
    # BASE
    nats_servers_raw: str = Field(default="nats://localhost:4222", alias="NATS_SERVERS")

    @property
    def nats_servers(self) -> list[str]:
        if self.nats_servers_raw.strip():
            return [o.strip() for o in self.nats_servers_raw.split(",") if o.strip()]
        return [
            "nats://eqcms-nats:4222",
        ]

    # STREAMS
    nats_stream_site_events: str = Field(
        default="SITE_EVENTS", alias="NATS_STREAM_SITE_EVENTS"
    )

    # SUBJECTS
    # SITE EVENTS
    nats_subjects_site_events_raw: str = Field(
        default="events.site.>", alias="NATS_SUBJECTS_SITE_EVENTS"
    )
    nats_subject_callback_requested: str = Field(
        default="events.site.callback.requested",
        alias="NATS_SUBJECT_CALLBACK_REQUESTED",
    )

    @property
    def nats_subjects_site_events(self) -> list[str]:
        if self.nats_subjects_site_events_raw.strip():
            return [
                o.strip()
                for o in self.nats_subjects_site_events_raw.split(",")
                if o.strip()
            ]
        return [
            "events.site.>",
        ]

    model_config = SettingsConfigDict(populate_by_name=True)


settings = Settings()
nats_settings = NatsSettings()
sentry_settings = SentrySettings()
