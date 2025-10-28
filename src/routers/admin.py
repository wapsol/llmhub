"""
Admin Router
API endpoints for the web UI management console
No authentication required (internal tool)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import secrets

from src.config.database import get_db
from src.config.settings import settings
from src.models.database import APIClient, PromptTemplate, LLMGenerationLog
from src.models.schemas import APIClientCreate, APIClientResponse
from src.utils.logger import logger

router = APIRouter()


# ============================================================================
# Dashboard Stats
# ============================================================================

@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get dashboard statistics
    Returns counts and aggregated data for the dashboard
    """
    try:
        # Count total clients
        total_clients = db.query(APIClient).filter(APIClient.is_active == True).count()

        # Count total templates
        total_templates = db.query(PromptTemplate).filter(PromptTemplate.is_active == True).count()

        # Get stats for last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # Total calls and cost in last 30 days
        stats = db.query(
            func.count(LLMGenerationLog.log_id).label('total_calls'),
            func.sum(LLMGenerationLog.input_cost_usd + LLMGenerationLog.output_cost_usd).label('total_cost')
        ).filter(
            LLMGenerationLog.created_at >= thirty_days_ago
        ).first()

        total_calls = stats.total_calls or 0
        total_cost = float(stats.total_cost or 0)

        return {
            "totalClients": total_clients,
            "totalTemplates": total_templates,
            "totalCalls": total_calls,
            "totalCost": round(total_cost, 2)
        }

    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard stats"
        )


# ============================================================================
# Providers
# ============================================================================

@router.get("/providers")
async def get_providers() -> Dict[str, Any]:
    """
    Get provider configuration status
    Returns which providers have API keys configured
    """
    return {
        "claude_configured": bool(settings.ANTHROPIC_API_KEY),
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "groq_configured": bool(settings.GROQ_API_KEY)
    }


# ============================================================================
# API Clients Management
# ============================================================================

@router.get("/clients")
async def get_clients(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Get all API clients
    """
    try:
        clients = db.query(APIClient).order_by(APIClient.created_at.desc()).all()

        return [
            {
                "client_id": str(client.client_id),
                "client_name": client.client_name,
                "api_key": client.api_key,
                "organization": client.organization,
                "contact_email": client.contact_email,
                "is_active": client.is_active,
                "rate_limit": client.rate_limit,
                "monthly_budget_usd": float(client.monthly_budget_usd) if client.monthly_budget_usd else None,
                "created_at": client.created_at.isoformat() if client.created_at else None,
                "updated_at": client.updated_at.isoformat() if client.updated_at else None
            }
            for client in clients
        ]

    except Exception as e:
        logger.error(f"Error getting clients: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch clients"
        )


@router.post("/clients", status_code=status.HTTP_201_CREATED)
async def create_client(
    client_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a new API client
    Generates a secure API key automatically
    """
    try:
        # Check if client name already exists
        existing = db.query(APIClient).filter(
            APIClient.client_name == client_data.get("client_name")
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Client with name '{client_data.get('client_name')}' already exists"
            )

        # Generate secure API key
        api_key = f"{client_data.get('client_name').replace(' ', '_').lower()}_{secrets.token_hex(16)}"

        # Create client
        new_client = APIClient(
            client_name=client_data.get("client_name"),
            api_key=api_key,
            organization=client_data.get("organization"),
            contact_email=client_data.get("contact_email"),
            rate_limit=client_data.get("rate_limit", 100),
            monthly_budget_usd=client_data.get("monthly_budget_usd"),
            is_active=True
        )

        db.add(new_client)
        db.commit()
        db.refresh(new_client)

        logger.info(f"Created new API client: {new_client.client_name}")

        return {
            "client_id": str(new_client.client_id),
            "client_name": new_client.client_name,
            "api_key": new_client.api_key,
            "message": "Client created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating client: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create client: {str(e)}"
        )


@router.delete("/clients/{client_id}")
async def delete_client(client_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    """
    Delete an API client
    """
    try:
        client = db.query(APIClient).filter(APIClient.client_id == client_id).first()

        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )

        db.delete(client)
        db.commit()

        logger.info(f"Deleted API client: {client.client_name}")

        return {"message": "Client deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting client: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete client"
        )


@router.post("/clients/{client_id}/regenerate-key")
async def regenerate_api_key(client_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Regenerate API key for a client
    """
    try:
        client = db.query(APIClient).filter(APIClient.client_id == client_id).first()

        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )

        # Generate new API key
        new_api_key = f"{client.client_name.replace(' ', '_').lower()}_{secrets.token_hex(16)}"
        client.api_key = new_api_key
        client.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(client)

        logger.info(f"Regenerated API key for client: {client.client_name}")

        return {
            "client_id": str(client.client_id),
            "api_key": client.api_key,
            "message": "API key regenerated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error regenerating API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate API key"
        )


# ============================================================================
# Billing & Usage
# ============================================================================

@router.get("/billing/stats")
async def get_billing_stats(
    days: int = 30,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get billing statistics for specified time range
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        stats = db.query(
            func.count(LLMGenerationLog.log_id).label('total_calls'),
            func.sum(LLMGenerationLog.input_cost_usd + LLMGenerationLog.output_cost_usd).label('total_cost')
        ).filter(
            LLMGenerationLog.created_at >= cutoff_date
        ).first()

        total_calls = stats.total_calls or 0
        total_cost = float(stats.total_cost or 0)
        avg_cost_per_call = (total_cost / total_calls) if total_calls > 0 else 0

        return {
            "totalCalls": total_calls,
            "totalCost": round(total_cost, 2),
            "avgCostPerCall": round(avg_cost_per_call, 4)
        }

    except Exception as e:
        logger.error(f"Error getting billing stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch billing stats"
        )


@router.get("/billing/daily")
async def get_daily_costs(
    days: int = 30,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get daily cost breakdown by provider
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        results = db.query(
            func.date_trunc('day', LLMGenerationLog.created_at).label('day'),
            LLMGenerationLog.provider,
            func.count(LLMGenerationLog.log_id).label('total_calls'),
            func.sum(LLMGenerationLog.input_cost_usd + LLMGenerationLog.output_cost_usd).label('total_cost')
        ).filter(
            LLMGenerationLog.created_at >= cutoff_date
        ).group_by(
            func.date_trunc('day', LLMGenerationLog.created_at),
            LLMGenerationLog.provider
        ).order_by(
            func.date_trunc('day', LLMGenerationLog.created_at).asc()
        ).all()

        return [
            {
                "day": row.day.isoformat() if row.day else None,
                "provider": row.provider,
                "total_calls": row.total_calls or 0,
                "total_cost": float(row.total_cost or 0)
            }
            for row in results
        ]

    except Exception as e:
        logger.error(f"Error getting daily costs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch daily costs"
        )


@router.get("/billing/by-client")
async def get_client_costs(
    days: int = 30,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get cost breakdown by client
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        results = db.query(
            APIClient.client_name,
            APIClient.monthly_budget_usd,
            func.count(LLMGenerationLog.log_id).label('total_calls'),
            func.sum(LLMGenerationLog.input_tokens + LLMGenerationLog.output_tokens).label('total_tokens'),
            func.sum(LLMGenerationLog.input_cost_usd + LLMGenerationLog.output_cost_usd).label('total_cost')
        ).join(
            LLMGenerationLog,
            APIClient.client_id == LLMGenerationLog.client_id
        ).filter(
            LLMGenerationLog.created_at >= cutoff_date
        ).group_by(
            APIClient.client_name,
            APIClient.monthly_budget_usd
        ).order_by(
            func.sum(LLMGenerationLog.input_cost_usd + LLMGenerationLog.output_cost_usd).desc()
        ).all()

        return [
            {
                "client_name": row.client_name,
                "total_calls": row.total_calls or 0,
                "total_tokens": row.total_tokens or 0,
                "total_cost": float(row.total_cost or 0),
                "monthly_budget": float(row.monthly_budget_usd) if row.monthly_budget_usd else None
            }
            for row in results
        ]

    except Exception as e:
        logger.error(f"Error getting client costs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch client costs"
        )
