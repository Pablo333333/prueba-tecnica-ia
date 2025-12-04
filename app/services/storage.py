import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class S3StorageService:
    def __init__(self):
        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        self.client = session.client("s3")
        self.bucket = settings.aws_s3_bucket

    def upload(self, *, content: bytes, filename: str) -> str:
        key = f"uploads/{uuid.uuid4()}/{filename}"
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        except (ClientError, BotoCoreError) as exc:
            raise RuntimeError("No se pudo subir el archivo a S3") from exc
        return key



