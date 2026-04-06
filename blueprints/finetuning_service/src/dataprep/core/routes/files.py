import logging

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Request, Query
from fastapi.responses import Response
from typing import Optional

from core.schemas import FileObject, DeleteResponse
from core.handlers import FileHandler, MetadataHandler
from core.handlers.auth_handler import get_current_user_id
from core.config.database import get_db
from core.middleware import limiter
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/files", tags=["files"])

# Initialize handlers - Note: metadata_handler is created per-request
file_handler = FileHandler()


def get_metadata_handler(db: Session = Depends(get_db)) -> MetadataHandler:
    """Create a new MetadataHandler with a fresh session for each request"""
    return MetadataHandler(db)


async def validate_file_type(file: UploadFile = File(...)):
    allowed_extensions = ('.txt', '.pdf', '.json', '.jsonl', '.tar.gz', '.docx', '.pptx')
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="currently only .txt, .pdf, .json, .jsonl, .tar.gz, .docx and .pptx files are supported")
    return file

@router.post("", response_model=FileObject)
@limiter.limit("10/minute")  # strict limit for file uploads (DoS protection)
async def upload_file(
    request: Request,
    file: UploadFile = Depends(validate_file_type),
    purpose: str = "finetuning",
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Upload a file for data preparation.
    Supports PDF, DOCX, PPTX, TXT, JSON, JSONL, and TAR.GZ files.
    """
    # Validate file type (already checked in dependency, but double-check for safety)
    allowed_extensions = ('.txt', '.pdf', '.json', '.jsonl', '.tar.gz', '.docx','.pptx')
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="Unsupported file type. Only .txt, .pdf, .json, .jsonl, .tar.gz, .docx and .pptx files are allowed.")

    try:
        file_metadata = await file_handler.save_file(file, db, purpose, user_id)
        return FileObject(**file_metadata)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.get("", response_model=dict)
async def list_files(
    purpose: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    metadata_handler: MetadataHandler = Depends(get_metadata_handler)
):
    """
    Get a list of your uploaded files.
    """
    try:
        files_list = metadata_handler.list_all(purpose=purpose, user_id=user_id)
        return {
            "object": "list",
            "data": files_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")


@router.get("/{file_id}", response_model=FileObject)
async def retrieve_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    metadata_handler: MetadataHandler = Depends(get_metadata_handler)
):
    """
    Get information about a specific file.
    """
    try:
        file_metadata = metadata_handler.get(file_id, user_id)

        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")

        return FileObject(**file_metadata)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")


@router.delete("/{file_id}", response_model=DeleteResponse)
async def delete_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    metadata_handler: MetadataHandler = Depends(get_metadata_handler),
    db: Session = Depends(get_db)
):
    """
    Delete a file.
    """
    try:
        file_metadata = metadata_handler.get(file_id, user_id)

        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")

        # Delete file from MinIO and metadata
        file_handler.delete_file(file_id, db, user_id)

        return DeleteResponse(id=file_id, object="file", deleted=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


@router.get("/{file_id}/content")
async def retrieve_file_content(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    metadata_handler: MetadataHandler = Depends(get_metadata_handler)
):
    """
    Download the contents of a file.
    Supports large files with 1MB chunk streaming and proper Content-Length header.
    """
    try:
        # Get metadata
        file_metadata = metadata_handler.get(file_id, user_id)

        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")

        filename = file_metadata.get("filename", "download")

        # Check if file exists in MinIO
        if not file_handler.file_exists(file_id, user_id):
            raise HTTPException(status_code=404, detail="File content not found")

        # Get file size for Content-Length header
        file_size = file_metadata.get("bytes", 0)


        file_stream = file_handler.get_file_stream(file_id, user_id)
        if file_stream is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve file content")

        from fastapi.responses import StreamingResponse

        # Build response headers
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes"
        }


        return StreamingResponse(
            file_stream.stream(amt=1024 * 1024),  # 1MB chunks (optimal for large files)
            media_type="application/octet-stream",
            headers=headers
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving file content: {str(e)}")


@router.get("/{file_id}/presigned-url")
async def get_presigned_url(
    file_id: str,
    expires: int = 3600,
    user_id: str = Depends(get_current_user_id)
):
    """
    Generate a presigned URL for direct file access.

    Args:
        file_id: File identifier
        expires: URL expiration time in seconds (default: 1 hour)

    Returns:
        Presigned URL for file download
    """
    try:
        file_metadata = metadata_handler.get(file_id, user_id)

        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")

        # Check if file exists in MinIO
        if not file_handler.file_exists(file_id):
            raise HTTPException(status_code=404, detail="File not found in storage")

        # Generate presigned URL
        presigned_url = file_handler.get_presigned_url(file_id, method="GET", expires_seconds=expires)

        if not presigned_url:
            raise HTTPException(status_code=500, detail="Failed to generate presigned URL")

        return {
            "url": presigned_url,
            "expires_in": expires,
            "file_id": file_id,
            "filename": file_metadata["filename"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating presigned URL: {str(e)}")
