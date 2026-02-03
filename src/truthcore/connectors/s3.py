"""S3-compatible connector for truth-core (optional, disabled by default)."""

from __future__ import annotations

import os
from pathlib import Path

from truthcore.connectors.base import BaseConnector, ConnectorConfig, ConnectorResult


class S3Connector(BaseConnector):
    """Connector for S3-compatible object storage.
    
    This connector is disabled by default and only available if
    the truth-core[s3] extra is installed (boto3/botocore).
    
    Example source format:
        s3://bucket-name/path/to/object.zip
        s3://bucket-name/path/to/prefix/
    """

    def __init__(self, config: ConnectorConfig | None = None):
        """Initialize S3 connector.
        
        Args:
            config: Connector configuration
        """
        super().__init__(config)
        self._boto3 = None
        self._botocore = None
        self._client = None
        self._endpoint_url = os.environ.get("S3_ENDPOINT_URL")
        self._region = os.environ.get("AWS_REGION", "us-east-1")
        self._access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        self._secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

    @property
    def name(self) -> str:
        return "s3"

    @property
    def is_available(self) -> bool:
        """Check if S3 support is available (boto3 installed and credentials configured)."""
        try:
            import boto3
            import botocore
            self._boto3 = boto3
            self._botocore = botocore

            # Check for credentials
            if self._access_key and self._secret_key:
                return True

            # Check for other credential sources (IAM role, etc)
            session = boto3.Session()
            credentials = session.get_credentials()
            return credentials is not None

        except ImportError:
            return False

    def fetch(self, source: str, destination: Path) -> ConnectorResult:
        """Fetch object(s) from S3.
        
        Args:
            source: S3 URI in format s3://bucket/key
            destination: Destination directory for downloaded content
            
        Returns:
            ConnectorResult with status and file list
        """
        if not self.is_available:
            return ConnectorResult(
                success=False,
                error="S3 connector not available. Install 'boto3' and configure AWS credentials."
            )

        # Parse S3 URI
        parsed = self._parse_s3_uri(source)
        if not parsed:
            return ConnectorResult(
                success=False,
                error=f"Invalid S3 URI: {source}. Expected: s3://bucket-name/key"
            )

        bucket, key = parsed

        destination.mkdir(parents=True, exist_ok=True)

        try:
            self._ensure_client()

            # Check if key is a prefix (ends with /) or single object
            if key.endswith("/"):
                return self._fetch_prefix(bucket, key, destination)
            else:
                return self._fetch_object(bucket, key, destination)

        except Exception as e:
            return ConnectorResult(success=False, error=f"S3 error: {e}")

    def _parse_s3_uri(self, source: str) -> tuple[str, str] | None:
        """Parse S3 URI into bucket and key.
        
        Args:
            source: S3 URI
            
        Returns:
            Tuple of (bucket, key) or None if invalid
        """
        if not source.startswith("s3://"):
            return None

        path = source[5:]  # Remove s3://
        parts = path.split("/", 1)

        if len(parts) < 1 or not parts[0]:
            return None

        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""

        return bucket, key

    def _ensure_client(self) -> None:
        """Ensure S3 client is initialized."""
        if self._client is None and self._boto3:
            session = self._boto3.Session(
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
            )

            kwargs = {}
            if self._endpoint_url:
                kwargs["endpoint_url"] = self._endpoint_url

            self._client = session.client("s3", **kwargs)

    def _fetch_object(self, bucket: str, key: str, destination: Path) -> ConnectorResult:
        """Fetch single S3 object.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            destination: Destination directory
            
        Returns:
            ConnectorResult
        """
        # Get object info
        response = self._client.head_object(Bucket=bucket, Key=key)
        size = response.get("ContentLength", 0)

        if size > self.config.max_size_bytes:
            return ConnectorResult(
                success=False,
                error=f"Object exceeds size limit ({self.config.max_size_bytes} bytes)"
            )

        # Validate key
        filename = Path(key).name
        if not self.validate_path(filename):
            return ConnectorResult(
                success=False,
                error=f"File type blocked: {Path(filename).suffix}"
            )

        dest_file = destination / filename

        # Download
        self._client.download_file(bucket, key, str(dest_file))

        return ConnectorResult(
            success=True,
            local_path=destination,
            files=[filename],
            metadata={
                "source": f"s3://{bucket}/{key}",
                "bucket": bucket,
                "key": key,
                "files_extracted": 1,
                "total_bytes": size,
            }
        )

    def _fetch_prefix(self, bucket: str, prefix: str, destination: Path) -> ConnectorResult:
        """Fetch all objects under a prefix.
        
        Args:
            bucket: S3 bucket name
            prefix: S3 key prefix (ends with /)
            destination: Destination directory
            
        Returns:
            ConnectorResult
        """
        files_downloaded: list[str] = []
        total_size = 0
        errors: list[str] = []

        # List objects
        paginator = self._client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj.get("Key", "")
                size = obj.get("Size", 0)

                # Skip directories
                if key.endswith("/"):
                    continue

                # Check file count
                if len(files_downloaded) >= self.config.max_files:
                    errors.append(f"Reached max file limit ({self.config.max_files})")
                    break

                # Calculate relative path
                rel_path = key[len(prefix):] if key.startswith(prefix) else key

                # Validate path
                if not self.validate_path(rel_path):
                    errors.append(f"Skipped blocked file: {rel_path}")
                    continue

                # Check size limit
                if not self.check_size_limit(total_size, size):
                    errors.append(f"Reached max size limit ({self.config.max_size_bytes} bytes)")
                    break

                # Download
                dest_file = destination / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                self._client.download_file(bucket, key, str(dest_file))

                files_downloaded.append(rel_path)
                total_size += size

        return ConnectorResult(
            success=True,
            local_path=destination,
            files=files_downloaded,
            metadata={
                "source": f"s3://{bucket}/{prefix}",
                "bucket": bucket,
                "prefix": prefix,
                "files_extracted": len(files_downloaded),
                "total_bytes": total_size,
                "errors": errors if errors else None,
            }
        )
