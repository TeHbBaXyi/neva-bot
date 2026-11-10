from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    BOT_TOKEN: str
    ADMIN_ID: int | None = None
    ADMIN_IDS: str = ""
    DATABASE_URL: str
    SITE_HOST: str = "127.0.0.1"
    SITE_PORT: int = 8000
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_FROM_NAME: str = "Нева—Темза"
    SMTP_TIMEOUT: int = 15

    @property
    def admin_ids(self) -> set[int]:
        ids = {int(value.strip()) for value in self.ADMIN_IDS.split(",") if value.strip()}
        if self.ADMIN_ID is not None:
            ids.add(self.ADMIN_ID)
        return ids


settings = Settings()
