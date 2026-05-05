"""
Models endpoint - List available base models for fine-tuning
"""

import logging
from fastapi import APIRouter, Request

from ..database import db_manager
from ..middleware import limiter
from ..errors import ServerError
from ..schemas import ModelListResponse
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["Models"])
settings = get_settings()


@router.get("/models", response_model=ModelListResponse)
@limiter.limit(f"{settings.rate_limit.models}/minute")
async def list_models(request: Request):
    """
    List available base models for fine-tuning

    Returns a list of models that can be used as base models for fine-tuning.
    Compatible with OpenAI's models endpoint.

    **Example Response:**
    ```json
    {
      "object": "list",
      "data": [
        {
          "id": "meta-llama/Llama-3.2-3B-Instruct",
          "object": "model",
          "created": 1699046400,
          "owned_by": "meta"
        }
      ]
    }
    ```
    """
    try:
        rows = await db_manager.fetch_all("""
            SELECT id, object, created, owned_by
            FROM base_models
            WHERE is_active = true
            ORDER BY created DESC
        """)

        return {
            "object": "list",
            "data": [
                {
                    "id": row["id"],
                    "object": row["object"],
                    "created": row["created"],
                    "owned_by": row["owned_by"]
                }
                for row in rows
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list models: {e}", exc_info=True)
        raise ServerError("Failed to retrieve models list")
