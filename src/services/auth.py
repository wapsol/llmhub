"""
Authentication Service - API Key Validation
"""

from fastapi import HTTPException, Header, Depends
from sqlalchemy.orm import Session
from typing import Optional
import time

from src.config.database import get_db
from src.models.database import APIClient
from src.utils.logger import logger


class AuthService:
    """Authentication service for API key validation"""

    @staticmethod
    def verify_api_key(
        api_key: str = Header(..., alias="X-API-Key"),
        db: Session = Depends(get_db)
    ) -> APIClient:
        """
        Verify API key and return the associated client

        Args:
            api_key: API key from X-API-Key header
            db: Database session

        Returns:
            APIClient object if valid

        Raises:
            HTTPException: 401 if invalid or inactive API key
        """
        if not api_key:
            logger.warning("Missing API key in request")
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "MISSING_API_KEY",
                    "message": "API key is required. Include X-API-Key header."
                }
            )

        # Query database for API client
        client = db.query(APIClient).filter(
            APIClient.api_key == api_key
        ).first()

        if not client:
            logger.warning("Invalid API key attempted", api_key_prefix=api_key[:10])
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "INVALID_API_KEY",
                    "message": "Invalid API key"
                }
            )

        if not client.is_active:
            logger.warning(
                "Inactive API key attempted",
                client_name=client.client_name
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "INACTIVE_CLIENT",
                    "message": "API key is inactive. Contact support."
                }
            )

        logger.debug(
            "API key validated",
            client_name=client.client_name,
            client_id=str(client.client_id)
        )

        return client


# Dependency function for FastAPI
def get_current_client(
    api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> APIClient:
    """
    FastAPI dependency to get current authenticated client

    Usage:
        @router.get("/endpoint")
        def endpoint(client: APIClient = Depends(get_current_client)):
            # client is authenticated
            pass
    """
    return AuthService.verify_api_key(api_key, db)
