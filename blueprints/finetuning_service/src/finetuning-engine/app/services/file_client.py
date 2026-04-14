# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import requests
import httpx
import os
import logging
import time
import shutil
import tarfile
import pgzip
from typing import Optional
from app.config import settings

logger = logging.getLogger("uvicorn")

class FileClientError(Exception):
    """Custom exception for file client errors"""
    pass

def retry_on_failure(max_retries: int = 3, delay: int = 2):
    """Decorator for retrying failed operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts")
            raise last_exception
        return wrapper
    return decorator

def get_file_id_by_filename(filename: str, bearer_token: str) -> str:
    """
    Get file ID by searching for filename in FILES API

    Args:
        filename: The filename to search for (e.g., 'dataset.jsonl')
        bearer_token: Bearer token for FILES API authentication

    Returns:
        File ID if found

    Raises:
        FileClientError: If file not found or API error
    """
    try:
        # Use bearer token directly
        headers = {"Authorization": f"Bearer {bearer_token}"}

        # List all files
        url = f"{settings.FILES_API_URL}/v1/files"
        logger.info(f"Searching for file: {filename}")

        response = requests.get(url, headers=headers, timeout=settings.FILES_API_TIMEOUT)
        response.raise_for_status()

        result = response.json()
        files = result.get("data", [])

        # Search for matching filename
        for file_info in files:
            if file_info.get("filename") == filename:
                file_id = file_info.get("id")
                logger.info(f"Found file: {filename} -> {file_id}")
                return file_id

        # File not found
        raise FileClientError(
            f"File '{filename}' not found in FILES API. "
            f"Available files: {[f.get('filename') for f in files[:10]]}"
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to search for file {filename}: {e}")
        raise FileClientError(f"Failed to search for file: {str(e)}") from e

@retry_on_failure(max_retries=3, delay=2)
def download_dataset(filename: str, bearer_token: str, force_download: bool = False) -> str:
    """
    Download dataset file from FILES API using file_id

    Args:
        filename: File ID to download (e.g., 'file-abc123' from FILES API)
        bearer_token: Bearer token for FILES API authentication
        force_download: If True, re-download even if file exists locally

    Returns:
        Local path to downloaded file

    Raises:
        FileClientError: If download fails
    """
    # Validate that filename looks like a file ID or might be a legacy filename
    if not filename.startswith('file-') and '.' in filename:
        logger.warning(
            f"⚠️  '{filename}' looks like a filename, not a file ID. "
            f"Attempting to resolve to file ID..."
        )
        try:
            filename = get_file_id_by_filename(filename, bearer_token)
            logger.info(f"✓ Resolved to file ID: {filename}")
        except FileClientError as e:
            logger.error(f"Failed to resolve filename: {e}")
            raise FileClientError(
                f"'{filename}' is not a valid file ID and could not be resolved. "
                f"Please use file IDs from FILES API (e.g., 'file-abc123xyz'). "
                f"Upload your file first or list files to get the correct ID."
            ) from e

    local_path = os.path.join(settings.TEMP_DATA_DIR, filename)

    # Check if file already exists and is valid
    if os.path.exists(local_path) and not force_download:
        file_size = os.path.getsize(local_path)
        if file_size > 0:
            logger.info(f"Using cached dataset: {filename} ({file_size} bytes)")
            return local_path
        else:
            logger.warning(f"Cached file {filename} is empty, re-downloading...")
            os.remove(local_path)

    # Use bearer token directly
    headers = {"Authorization": f"Bearer {bearer_token}"}

    try:
        # FILES API v1: Download file content using /content endpoint
        file_id = filename  # The input is the file_id
        url = f"{settings.FILES_API_URL}/v1/files/{file_id}/content"

        logger.info(f"Downloading file content from: {url}")
        start_time = time.time()

        with requests.get(url, headers=headers, stream=True, timeout=settings.FILES_API_TIMEOUT) as r:
            r.raise_for_status()

            # Get file size if available
            total_size = int(r.headers.get('content-length', 0))
            downloaded = 0

            # Create temp file first
            temp_path = local_path + ".tmp"

            with open(temp_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Log progress every 10MB
                        if downloaded % (10 * 1024 * 1024) == 0:
                            if total_size:
                                progress = (downloaded / total_size) * 100
                                logger.info(f"Download progress: {progress:.1f}% ({downloaded}/{total_size} bytes)")
                            else:
                                logger.info(f"Downloaded: {downloaded} bytes")

            # Verify file was downloaded
            if downloaded == 0:
                raise FileClientError(f"Downloaded file is empty: {filename}")

            # Rename temp file to final name
            os.rename(temp_path, local_path)

        elapsed_time = time.time() - start_time
        logger.info(
            f"Download completed: {filename} ({downloaded} bytes) in {elapsed_time:.2f}s "
            f"({downloaded / elapsed_time / 1024 / 1024:.2f} MB/s)"
        )

        return local_path

    except requests.exceptions.RequestException as e:
        logger.error(f"Download failed for {filename}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            status_code = e.response.status_code
            if status_code == 404:
                logger.error(
                    f"❌ File not found: '{filename}'. "
                    f"Make sure you're using the file ID (e.g., 'file-abc123'), not the filename. "
                    f"List available files: GET /v1/files"
                )
            elif status_code == 401:
                logger.error(f"❌ Authentication failed. Check if the bearer token is valid.")
            try:
                error_detail = e.response.json()
                logger.error(f"API Error Response: {error_detail}")
            except:
                logger.error(f"API Response Text: {e.response.text}")
        # Clean up partial download
        for path in [local_path, local_path + ".tmp"]:
            if os.path.exists(path):
                os.remove(path)

        error_msg = f"Failed to download {filename}: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code == 404:
                error_msg += (
                    f"\n\nℹ️  Tip: Make sure '{filename}' is a valid file ID from FILES API. "
                    f"If you're using a filename, upload it first to get a file ID."
                )
            elif e.response.status_code == 401:
                error_msg += f"\n\nℹ️  Tip: Check if the bearer token is valid and not expired."
        raise FileClientError(error_msg) from e
    except Exception as e:
        logger.error(f"Unexpected error during download: {e}")
        raise FileClientError(f"Download error: {str(e)}") from e

def create_model_archive(folder_path: str, output_path: Optional[str] = None) -> str:
    """
    Create a tar.gz archive of the model folder using multi-threaded pgzip

    Args:
        folder_path: Path to model folder
        output_path: Optional custom output path for tar.gz file

    Returns:
        Path to created tar.gz file
    """
    if not os.path.exists(folder_path):
        raise FileClientError(f"Model folder not found: {folder_path}")

    if output_path is None:
        output_path = f"{folder_path}.tar.gz"

    try:
        logger.info(f"Creating model archive with pgzip: {output_path}")
        start_time = time.time()

        # Use pgzip for multi-threaded compression
        # thread=None uses all available CPU cores
        # compression_level=1 is 3x faster with minimal size difference
        with pgzip.open(output_path, "wb", thread=None, compresslevel=1) as f_out:
            # Pipe tarfile into the parallel gzip stream
            with tarfile.open(mode="w", fileobj=f_out) as tar:
                # arcname prevents storing full absolute path
                tar.add(folder_path, arcname=os.path.basename(folder_path))

        archive_size = os.path.getsize(output_path)
        elapsed_time = time.time() - start_time

        logger.info(
            f"Archive created: {output_path} ({archive_size / 1024 / 1024:.2f} MB) "
            f"in {elapsed_time:.2f}s ({archive_size / elapsed_time / 1024 / 1024:.2f} MB/s)"
        )

        return output_path

    except Exception as e:
        logger.error(f"Failed to create archive: {e}")
        raise FileClientError(f"Archive creation failed: {str(e)}") from e

@retry_on_failure(max_retries=2, delay=10)
def upload_model(folder_path: str, model_name: str, bearer_token: str) -> str:
    """
    Upload fine-tuned model to file service using FILES API v1 with httpx

    Args:
        folder_path: Path to model folder
        model_name: Name of the model for metadata
        bearer_token: Bearer token for FILES API authentication

    Returns:
        File ID from file service

    Raises:
        FileClientError: If upload fails
    """
    # Create tar.gz archive
    zip_path = create_model_archive(folder_path)

    # Use bearer token directly
    headers = {"Authorization": f"Bearer {bearer_token}"}

    # FILES API v1 endpoint
    url = f"{settings.FILES_API_URL}/v1/files"

    try:
        file_size = os.path.getsize(zip_path)
        logger.info(f"Uploading model: {model_name} from {zip_path}")
        logger.info(f"Upload size: {file_size / 1024 / 1024:.2f} MB")

        # Check if file is very large
        if file_size > 100 * 1024 * 1024:  # > 100MB
            logger.warning(f"Large file upload ({file_size / 1024 / 1024:.2f} MB) - this may take several minutes")

        start_time = time.time()

        # Read and upload file using httpx with streaming
        with open(zip_path, 'rb') as f:
            files = {
                'file': (f"finetuned_models#{os.path.basename(zip_path)}", f, 'application/gzip')
            }
            data = {
                'purpose': 'fine-tune-results'
            }

            # Use httpx client with extended timeout for large files
            # connect: 60s, read: 4 hours (14400s), write: 4 hours, pool: 60s
            # Increased timeout for very large files
            with httpx.Client(timeout=httpx.Timeout(connect=60.0, read=14400.0, write=14400.0, pool=60.0)) as client:
                logger.info(f"Uploading finetuned_models#{os.path.basename(zip_path)} to {url}...")
                logger.info(f"File size: {file_size / 1024 / 1024:.2f} MB - estimated time: {file_size / (1024 * 1024):.0f} seconds at 1 MB/s")

                response = client.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data
                )

                logger.info(f"Upload response status: {response.status_code}")
                logger.info(f"Upload response body: {response.text[:500]}")  # First 500 chars

                # Check for gateway errors (502, 503, 504) - these indicate server-side issues
                if response.status_code in [502, 503, 504]:
                    error_msg = f"Gateway error: HTTP {response.status_code}"
                    logger.error(f"{error_msg} - Server timeout or unavailable. Response: {response.text}")
                    raise FileClientError(
                        f"{error_msg} - The FILES_API server timed out processing the upload. "
                        f"This usually means the nginx gateway timeout is too short for files of this size ({file_size / 1024 / 1024:.2f} MB). "
                        f"Please increase the nginx gateway timeout on the FILES_API server or use chunked uploads."
                    )

                # Check for auth errors
                if response.status_code == 401:
                    logger.error(f"Authentication failed - bearer token may be invalid or expired")
                    raise FileClientError(f"Authentication failed: Invalid or expired bearer token")

                # Check for other error status codes
                if response.status_code not in [200, 201]:
                    error_msg = f"Upload failed: HTTP {response.status_code}"
                    logger.error(f"{error_msg} - {response.text}")
                    raise FileClientError(f"{error_msg} - {response.text}")

                result = response.json()
                logger.info(f"Parsed response: {result}")

        elapsed_time = time.time() - start_time

        # Extract file ID from FILES API response
        file_id = result.get("id")

        if not file_id:
            logger.error(f"No file ID in response! Full response: {result}")
            raise FileClientError("No file ID returned from FILES API")

        filename = result.get("filename", "unknown")
        file_status = result.get("status", "unknown")

        logger.info(
            f"✅ Upload completed: {model_name} (ID: {file_id}, Status: {file_status}) "
            f"in {elapsed_time:.2f}s ({file_size / elapsed_time / 1024 / 1024:.2f} MB/s)"
        )

        # Clean up tar.gz file after successful upload
        try:
            os.remove(zip_path)
            logger.info(f"Cleaned up archive: {zip_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up archive {zip_path}: {e}")

        return file_id

    except httpx.TimeoutException as e:
        logger.error(f"Upload timeout for {model_name} after {time.time() - start_time:.0f}s: {e}")
        logger.error(f"File size was: {file_size / 1024 / 1024:.2f} MB")
        raise FileClientError(
            f"Upload timed out for {model_name}. File size: {file_size / 1024 / 1024:.2f} MB. "
            f"Elapsed time: {time.time() - start_time:.0f}s. "
            f"The client timeout is 4 hours, but the server may have a shorter timeout. "
            f"Consider splitting large models or increasing server-side timeouts."
        ) from e
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error during upload of {model_name}: {e}")
        logger.error(f"Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
        raise FileClientError(f"HTTP error during upload: {str(e)}") from e
    except FileClientError:
        # Re-raise FileClientError as-is (already formatted)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        raise FileClientError(f"Upload error: {str(e)}") from e
    finally:
        # Clean up zip file on error
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
                logger.info(f"Cleaned up archive after upload: {zip_path}")
            except Exception:
                pass

def cleanup_old_files(directory: str, max_age_hours: int = 24):
    """
    Clean up old files in a directory

    Args:
        directory: Directory to clean
        max_age_hours: Maximum age of files to keep in hours
    """
    if not os.path.exists(directory):
        return

    try:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0
        cleaned_size = 0

        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)

            # Get file age
            file_age = current_time - os.path.getmtime(item_path)

            if file_age > max_age_seconds:
                item_size = os.path.getsize(item_path) if os.path.isfile(item_path) else 0

                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

                cleaned_count += 1
                cleaned_size += item_size
                logger.info(f"Cleaned up old file/folder: {item} (age: {file_age / 3600:.1f}h)")

        if cleaned_count > 0:
            logger.info(
                f"Cleanup completed: {cleaned_count} items removed, "
                f"{cleaned_size / 1024 / 1024:.2f} MB freed"
            )

    except Exception as e:
        logger.error(f"Cleanup failed for {directory}: {e}")
