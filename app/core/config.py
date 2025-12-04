from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_name: str = "Data Quality API"
    environment: str = Field(default="local", validation_alias="APP_ENV")

    jwt_secret_key: str = Field(..., min_length=32, validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 15
    jwt_refresh_extension_minutes: int = 15

    aws_access_key_id: str | None = Field(default=None, validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, validation_alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", validation_alias="AWS_REGION")
    aws_s3_bucket: str = Field(..., validation_alias="AWS_S3_BUCKET")

    sqlserver_uri: str = Field(..., validation_alias="SQLSERVER_URI")

    ai_model: str = Field(default="google/flan-t5-small", validation_alias="AI_MODEL")
    timezone: str = Field(default="UTC", validation_alias="APP_TIMEZONE")

    allowed_roles: list[str] = Field(default_factory=lambda: ["data_uploader"])

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


