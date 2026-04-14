"""
Storage handler for MinIO/S3 operations
"""
import os
import urllib3
from pathlib import Path
from typing import BinaryIO, Optional
from datetime import datetime, timedelta
from urllib.parse import urlunsplit
from urllib3 import Retry
from urllib3.util import Timeout
from urllib3.util.url import parse_url

from minio import Minio
from minio.error import S3Error
from minio.credentials import EnvMinioProvider
from minio.signer import presign_v4

from core.config import settings


class StorageHandler:
    """
    Handles file storage operations with MinIO/S3

    Supports:
    - MinIO (local/remote)
    - AWS S3
    - S3-compatible storage
    - Proxy support
    - SSL certificate verification
    - Connection pooling with retries
    """

    def __init__(self):
        self.region = settings.MINIO_REGION
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self.client = self._create_client()
        self._ensure_bucket()

    def _get_http_client(self, endpoint: str, cert_check: bool = True) -> urllib3.PoolManager:
        """
        Create HTTP client with proxy support, retries, and timeouts

        Args:
            endpoint: MinIO/S3 endpoint URL
            cert_check: Whether to verify SSL certificates

        Returns:
            Configured urllib3 PoolManager or ProxyManager
        """
        from requests.utils import select_proxy, get_environ_proxies
        from requests.exceptions import InvalidProxyURL

        cert_check = str(cert_check).lower() not in ['false', '0', 'f', 'n', 'no']

        # Ensure endpoint has scheme
        if not endpoint.startswith(('http://', 'https://')):
            endpoint = f"http://{endpoint}"

        endpoint = parse_url(endpoint)
        proxy = select_proxy(endpoint.url, get_environ_proxies(endpoint.url))

        if endpoint.scheme == 'https' and not cert_check:
            urllib3.disable_warnings()  # Skip InsecureRequestWarning

        # Configure timeout and retries
        timeout_time = timedelta(seconds=30).seconds
        timeout = Timeout(connect=timeout_time, read=timeout_time)
        cert_reqs = 'CERT_REQUIRED' if cert_check else 'CERT_NONE'
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )

        # Use ProxyManager if proxy is configured
        if proxy:
            if not proxy.startswith(('http://', 'https://')):
                proxy = f"http://{proxy}"
            proxy_url = parse_url(proxy)
            if not proxy_url.host:
                raise InvalidProxyURL(
                    "Please check proxy URL. It is malformed "
                    "and could be missing the host."
                )
            return urllib3.ProxyManager(
                proxy_url.url,
                timeout=timeout,
                cert_reqs=cert_reqs,
                retries=retries
            )
        else:
            return urllib3.PoolManager(
                timeout=timeout,
                cert_reqs=cert_reqs,
                retries=retries
            )

    def _create_client(self) -> Minio:
        """
        Create MinIO/S3 client with advanced configuration

        Features:
        - Custom HTTP client with retries
        - Proxy support
        - SSL certificate verification
        - Environment-based credentials
        """
        endpoint = settings.MINIO_ENDPOINT
        cert_check = settings.MINIO_CERT_VERIFY

        # Create custom HTTP client
        http_client = self._get_http_client(endpoint, cert_check)

        # Parse endpoint to extract scheme
        if not endpoint.startswith(('http://', 'https://')):
            endpoint = f"http://{endpoint}"
        parsed_endpoint = parse_url(endpoint)

        # Create Minio client with credentials from settings
        return Minio(
            endpoint=parsed_endpoint._replace(scheme=None, path=None, query=None, fragment=None).url,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=True if parsed_endpoint.scheme == 'https' else settings.MINIO_SECURE,
            region=self.region,
            http_client=http_client,
            cert_check=cert_check
        )

    def _ensure_bucket(self):
        """Create bucket if it doesn't exist"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"Created bucket: {self.bucket_name}")
        except S3Error as e:
            print(f"Error ensuring bucket: {e}")

    def upload_file(self, file_id: str, file_data: BinaryIO, file_size: int, content_type: str = "application/octet-stream") -> bool:
        """
        Upload a file to storage

        Args:
            file_id: Unique file identifier
            file_data: File data stream
            file_size: Size of the file in bytes
            content_type: MIME type of the file

        Returns:
            True if successful
        """
        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=file_id,
                data=file_data,
                length=file_size,
                content_type=content_type
            )
            return True
        except S3Error as e:
            print(f"Error uploading file {file_id}: {e}")
            return False

    def get_file_stream(self, file_id: str):
        """
        Get a streaming file-like object from storage (MinIO)
        Args:
            file_id: Unique file identifier
        Returns:
            File-like object for streaming, or None if error
        """
        try:
            return self.client.get_object(self.bucket_name, file_id)
        except S3Error as e:
            print(f"Error streaming file {file_id}: {e}")
            return None

    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from storage

        Args:
            file_id: Unique file identifier

        Returns:
            True if successful
        """
        try:
            self.client.remove_object(self.bucket_name, file_id)
            return True
        except S3Error as e:
            print(f"Error deleting file {file_id}: {e}")
            return False

    def file_exists(self, file_id: str) -> bool:
        """
        Check if a file exists in storage

        Args:
            file_id: Unique file identifier

        Returns:
            True if file exists
        """
        try:
            print(self.bucket_name, file_id)
            self.client.stat_object(self.bucket_name, file_id)
            return True
        except S3Error:
            return False

    def get_presigned_url(self, file_id: str, method: str = "GET", expires_seconds: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for file access with custom signing

        Args:
            file_id: Unique file identifier
            method: HTTP method ('GET', 'PUT', 'DELETE')
            expires_seconds: URL expiration time in seconds

        Returns:
            Presigned URL string
        """
        try:
            expires = timedelta(seconds=expires_seconds)

            # Get credentials from client
            credentials = self.client._provider.retrieve()

            # Build base URL
            base_url = self.client._base_url.build(
                method,
                self.region,
                bucket_name=self.bucket_name,
                object_name=file_id,
                query_params={}
            )

            # Sign the URL
            presigned_url = presign_v4(
                method,
                base_url,
                self.region,
                credentials,
                datetime.now(),
                int(expires.total_seconds())
            )

            return urlunsplit(presigned_url)
        except S3Error as e:
            print(f"Error generating presigned URL for {file_id}: {e}")
            return None

    def list_buckets(self) -> list[str]:
        """
        List all available buckets

        Returns:
            List of bucket names
        """
        try:
            buckets = self.client.list_buckets()
            return [bucket.name for bucket in buckets]
        except S3Error as e:
            print(f"Error listing buckets: {e}")
            return []

    def get_file_stat(self, file_id: str) -> Optional[dict]:
        """
        Get file statistics/metadata

        Args:
            file_id: Unique file identifier

        Returns:
            Dictionary with file metadata (size, etag, last_modified)
        """
        try:
            stat = self.client.stat_object(self.bucket_name, file_id)
            return {
                "size": stat.size,
                "etag": stat.etag,
                "last_modified": stat.last_modified,
                "content_type": stat.content_type,
                "metadata": stat.metadata
            }
        except S3Error as e:
            print(f"Error getting file stat for {file_id}: {e}")
            return None
