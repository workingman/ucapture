"""Cloudflare R2 storage client (S3-compatible).

Provides fetch_object() and put_object() operations using boto3 with
S3-compatible API against Cloudflare R2 endpoints.
"""

from __future__ import annotations

import logging
import os

import boto3
from botocore.exceptions import ClientError

from audio_processor.utils.errors import AudioFetchError, StorageError

logger = logging.getLogger(__name__)


class R2Client:
    """S3-compatible client for Cloudflare R2 storage.

    Reads configuration from environment variables:
        R2_ENDPOINT, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
    """

    def __init__(
        self,
        endpoint_url: str | None = None,
        bucket: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url or os.environ.get("R2_ENDPOINT", "")
        self.bucket = bucket or os.environ.get("R2_BUCKET", "")
        self.access_key_id = access_key_id or os.environ.get(
            "R2_ACCESS_KEY_ID", ""
        )
        self.secret_access_key = secret_access_key or os.environ.get(
            "R2_SECRET_ACCESS_KEY", ""
        )

        if not self.endpoint_url:
            raise StorageError("R2_ENDPOINT is required", operation="init")
        if not self.bucket:
            raise StorageError("R2_BUCKET is required", operation="init")

        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto",
        )

    def fetch_object(self, key: str) -> bytes:
        """Retrieve an object from R2 by key.

        Args:
            key: The R2 object key (e.g., "{user_id}/{batch_id}/raw-audio/recording.m4a").

        Returns:
            Raw bytes of the object.

        Raises:
            AudioFetchError: If the object cannot be retrieved.
        """
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise AudioFetchError(
                f"Failed to fetch R2 object '{key}': {error_code}",
                key=key,
            ) from exc

    def put_object(self, key: str, data: bytes, content_type: str = "") -> None:
        """Store an object in R2.

        Args:
            key: The R2 object key.
            data: Raw bytes to store.
            content_type: Optional MIME content type.

        Raises:
            StorageError: If the object cannot be stored.
        """
        try:
            kwargs: dict = {"Bucket": self.bucket, "Key": key, "Body": data}
            if content_type:
                kwargs["ContentType"] = content_type
            self._client.put_object(**kwargs)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise StorageError(
                f"Failed to put R2 object '{key}': {error_code}",
                operation="put_object",
            ) from exc
