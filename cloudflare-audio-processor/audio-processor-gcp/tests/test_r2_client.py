"""Tests for audio_processor.storage.r2_client module."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from audio_processor.storage.r2_client import R2Client
from audio_processor.utils.errors import AudioFetchError, StorageError


class TestR2ClientInit:
    """Tests for R2Client initialization."""

    def test_init_with_explicit_params(self):
        """R2Client initializes with explicit parameters."""
        with patch("audio_processor.storage.r2_client.boto3") as mock_boto:
            client = R2Client(
                endpoint_url="https://r2.example.com",
                bucket="test-bucket",
                access_key_id="key-id",
                secret_access_key="secret-key",
            )
        assert client.endpoint_url == "https://r2.example.com"
        assert client.bucket == "test-bucket"

    def test_init_missing_endpoint_raises_storage_error(self):
        """R2Client raises StorageError if endpoint is missing."""
        with pytest.raises(StorageError, match="R2_ENDPOINT is required"):
            R2Client(
                endpoint_url="",
                bucket="bucket",
                access_key_id="key",
                secret_access_key="secret",
            )

    def test_init_missing_bucket_raises_storage_error(self):
        """R2Client raises StorageError if bucket is missing."""
        with pytest.raises(StorageError, match="R2_BUCKET is required"):
            R2Client(
                endpoint_url="https://r2.example.com",
                bucket="",
                access_key_id="key",
                secret_access_key="secret",
            )


class TestR2ClientFetchObject:
    """Tests for R2Client.fetch_object()."""

    def _make_client(self):
        """Create a client with a mocked boto3 s3 client."""
        with patch("audio_processor.storage.r2_client.boto3") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.client.return_value = mock_s3
            client = R2Client(
                endpoint_url="https://r2.example.com",
                bucket="test-bucket",
                access_key_id="key-id",
                secret_access_key="secret-key",
            )
        return client, mock_s3

    def test_fetch_object_returns_bytes(self):
        """fetch_object returns raw bytes from R2."""
        client, mock_s3 = self._make_client()
        mock_body = MagicMock()
        mock_body.read.return_value = b"audio-data-bytes"
        mock_s3.get_object.return_value = {"Body": mock_body}

        result = client.fetch_object("user1/batch1/raw-audio/recording.m4a")

        assert result == b"audio-data-bytes"
        mock_s3.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="user1/batch1/raw-audio/recording.m4a"
        )

    def test_fetch_object_raises_audio_fetch_error_on_client_error(self):
        """fetch_object raises AudioFetchError when S3 client fails."""
        client, mock_s3 = self._make_client()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        with pytest.raises(AudioFetchError, match="NoSuchKey"):
            client.fetch_object("missing/key")


class TestR2ClientPutObject:
    """Tests for R2Client.put_object()."""

    def _make_client(self):
        """Create a client with a mocked boto3 s3 client."""
        with patch("audio_processor.storage.r2_client.boto3") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.client.return_value = mock_s3
            client = R2Client(
                endpoint_url="https://r2.example.com",
                bucket="test-bucket",
                access_key_id="key-id",
                secret_access_key="secret-key",
            )
        return client, mock_s3

    def test_put_object_stores_data(self):
        """put_object calls S3 put_object with correct args."""
        client, mock_s3 = self._make_client()

        client.put_object("user1/batch1/transcript/formatted.txt", b"hello")

        mock_s3.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="user1/batch1/transcript/formatted.txt",
            Body=b"hello",
        )

    def test_put_object_with_content_type(self):
        """put_object includes ContentType when provided."""
        client, mock_s3 = self._make_client()

        client.put_object("key", b"data", content_type="text/plain")

        mock_s3.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="key",
            Body=b"data",
            ContentType="text/plain",
        )

    def test_put_object_raises_storage_error_on_client_error(self):
        """put_object raises StorageError when S3 client fails."""
        client, mock_s3 = self._make_client()
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}},
            "PutObject",
        )

        with pytest.raises(StorageError, match="AccessDenied"):
            client.put_object("key", b"data")
