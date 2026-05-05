from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
    main_site_domain: str = Field(default="localhost:3000", alias="MAIN_SITE_DOMAIN")

    db_user: str = Field(default="eqsitecmsdev", alias="POSTGRES_USER")
    db_password: str = Field(default="eqsitecmsdev", alias="POSTGRES_PASSWORD")
    db_host: str = Field(default="db", alias="POSTGRES_HOST")
    db_name: str = Field(default="eqsitecmsdev", alias="POSTGRES_NAME")
    db_port: int = Field(default=5432, alias="POSTGRES_PORT")

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


settings = Settings()
