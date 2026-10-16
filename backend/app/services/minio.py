"""
MinIO S3 Client Service.
Provides object storage for case documents and policy documents.
"""

from __future__ import annotations

import io

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings

class MinioService:
    def __init__(self):
        settings = get_settings()
        # Connect to local MinIO using boto3
        # FLAG: Never fallback to public S3.
        self.s3 = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1" # MinIO default region
        )

    def ensure_bucket(self, bucket_name: str) -> None:
        """Create bucket if it doesn't already exist."""
        try:
            self.s3.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                self.s3.create_bucket(Bucket=bucket_name)
            else:
                raise e

    def upload_file(self, bucket: str, object_key: str, file_bytes: bytes, content_type: str) -> str:
        """
        Upload a file to a bucket and return the object_key.
        """
        self.s3.upload_fileobj(
            io.BytesIO(file_bytes),
            bucket,
            object_key,
            ExtraArgs={"ContentType": content_type}
        )
        return object_key

    def download_file(self, bucket: str, object_key: str) -> bytes:
        """
        Download a file from a bucket and return its contents as bytes.
        """
        file_obj = io.BytesIO()
        self.s3.download_fileobj(bucket, object_key, file_obj)
        return file_obj.getvalue()

    def delete_file(self, bucket: str, object_key: str) -> None:
        """
        Delete a file from a bucket.
        """
        self.s3.delete_object(Bucket=bucket, Key=object_key)

# Singleton instance
minio_service = MinioService()
