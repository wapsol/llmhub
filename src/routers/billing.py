"""
Billing Router
API endpoints for usage reports and cost analytics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID

from src.config.database import get_db
from src.models.database import APIClient, LLMGenerationLog
from src.models.schemas import (
    UsageReportRequest,
    UsageReportResponse,
    UsageSummary
)
from src.services.auth import get_current_client
from src.services.billing import billing_service
from src.utils.logger import logger

router = APIRouter()


@router.get("/usage/summary", response_model=UsageReportResponse)
async def get_usage_summary(
    start_date: Optional[datetime] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (defaults to now)"),
    group_by: str = Query("day", description="Group by: hour, day, month"),
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Get usage summary for the current client

    Returns aggregated usage data grouped by time period.
    Includes cost, token usage, call counts, and success rates.
    """
    # Default date range: last 30 days
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    try:
        logger.info(
            "usage_summary_requested",
            client=client.client_name,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            group_by=group_by
        )

        # Query appropriate materialized view based on group_by
        if group_by == "hour":
            view_name = "llm_hourly_costs"
            time_column = "hour"
        elif group_by == "month":
            view_name = "llm_monthly_costs"
            time_column = "month"
        else:  # day (default)
            view_name = "llm_daily_costs"
            time_column = "day"

        # Query aggregated data
        query = db.execute(
            f"""
            SELECT
                {time_column} as period,
                SUM(call_count)::INTEGER as call_count,
                SUM(total_tokens)::INTEGER as total_tokens,
                SUM(total_cost)::FLOAT as total_cost,
                AVG(avg_generation_time_ms)::FLOAT as avg_generation_time_ms,
                AVG(success_rate)::FLOAT as success_rate
            FROM {view_name}
            WHERE client_id = :client_id
              AND {time_column} >= :start_date
              AND {time_column} <= :end_date
            GROUP BY {time_column}
            ORDER BY {time_column} DESC
            """,
            {
                "client_id": str(client.client_id),
                "start_date": start_date,
                "end_date": end_date
            }
        )

        results = query.fetchall()

        # Build summary list
        summary_list = []
        total_cost = 0.0
        total_calls = 0

        for row in results:
            period, call_count, total_tokens, cost, avg_time, success_rate = row

            summary_list.append(UsageSummary(
                period=period,
                call_count=call_count or 0,
                total_tokens=total_tokens or 0,
                total_cost_usd=round(cost or 0.0, 4),
                avg_generation_time_ms=round(avg_time or 0.0, 2),
                success_rate=round(success_rate or 0.0, 4)
            ))

            total_cost += (cost or 0.0)
            total_calls += (call_count or 0)

        return UsageReportResponse(
            client_name=client.client_name,
            start_date=start_date,
            end_date=end_date,
            summary=summary_list,
            total_cost_usd=round(total_cost, 4),
            total_calls=total_calls
        )

    except Exception as e:
        logger.error(f"Failed to get usage summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get usage summary: {str(e)}"
        )


@router.get("/usage/by-provider")
async def get_usage_by_provider(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Get usage breakdown by LLM provider

    Shows cost and usage distribution across Claude, OpenAI, Groq, etc.
    """
    # Default date range: last 30 days
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    try:
        query = db.execute(
            """
            SELECT
                provider,
                COUNT(*)::INTEGER as call_count,
                SUM(total_tokens)::INTEGER as total_tokens,
                SUM(total_cost_usd)::FLOAT as total_cost,
                AVG(generation_time_ms)::FLOAT as avg_generation_time_ms,
                SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as success_rate
            FROM llm_generation_log
            WHERE client_id = :client_id
              AND created_at >= :start_date
              AND created_at <= :end_date
            GROUP BY provider
            ORDER BY total_cost DESC
            """,
            {
                "client_id": str(client.client_id),
                "start_date": start_date,
                "end_date": end_date
            }
        )

        results = query.fetchall()

        return {
            "client_name": client.client_name,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "breakdown": [
                {
                    "provider": row[0],
                    "call_count": row[1] or 0,
                    "total_tokens": row[2] or 0,
                    "total_cost_usd": round(row[3] or 0.0, 4),
                    "avg_generation_time_ms": round(row[4] or 0.0, 2),
                    "success_rate": round(row[5] or 0.0, 4)
                }
                for row in results
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get provider breakdown: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get provider breakdown: {str(e)}"
        )


@router.get("/usage/by-endpoint")
async def get_usage_by_endpoint(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Get usage breakdown by API endpoint

    Shows which features are used most (content generation, images, translation, etc.)
    """
    # Default date range: last 30 days
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    try:
        query = db.execute(
            """
            SELECT
                endpoint,
                COUNT(*)::INTEGER as call_count,
                SUM(total_tokens)::INTEGER as total_tokens,
                SUM(total_cost_usd)::FLOAT as total_cost,
                AVG(generation_time_ms)::FLOAT as avg_generation_time_ms,
                SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as success_rate
            FROM llm_generation_log
            WHERE client_id = :client_id
              AND created_at >= :start_date
              AND created_at <= :end_date
            GROUP BY endpoint
            ORDER BY total_cost DESC
            """,
            {
                "client_id": str(client.client_id),
                "start_date": start_date,
                "end_date": end_date
            }
        )

        results = query.fetchall()

        return {
            "client_name": client.client_name,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "breakdown": [
                {
                    "endpoint": row[0],
                    "call_count": row[1] or 0,
                    "total_tokens": row[2] or 0,
                    "total_cost_usd": round(row[3] or 0.0, 4),
                    "avg_generation_time_ms": round(row[4] or 0.0, 2),
                    "success_rate": round(row[5] or 0.0, 4)
                }
                for row in results
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get endpoint breakdown: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get endpoint breakdown: {str(e)}"
        )


@router.get("/usage/current-month")
async def get_current_month_usage(
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Get current month usage summary with budget status

    Shows spending for current month and budget alerts if applicable.
    """
    try:
        # Query current month view
        query = db.execute(
            """
            SELECT * FROM v_current_month_costs
            WHERE client_name = :client_name
            """,
            {"client_name": client.client_name}
        )

        result = query.fetchone()

        if not result:
            return {
                "client_name": client.client_name,
                "month": datetime.now().strftime("%Y-%m"),
                "total_cost_usd": 0.0,
                "total_calls": 0,
                "monthly_budget_usd": float(client.monthly_budget_usd) if client.monthly_budget_usd else None,
                "budget_used_percentage": 0.0,
                "budget_alert": None
            }

        total_cost = float(result[2]) if result[2] else 0.0
        total_calls = result[3] or 0
        monthly_budget = float(client.monthly_budget_usd) if client.monthly_budget_usd else None

        # Calculate budget usage
        budget_used_pct = 0.0
        budget_alert = None

        if monthly_budget and monthly_budget > 0:
            budget_used_pct = (total_cost / monthly_budget) * 100

            if budget_used_pct >= 100:
                budget_alert = "EXCEEDED"
            elif budget_used_pct >= 90:
                budget_alert = "CRITICAL"
            elif budget_used_pct >= 80:
                budget_alert = "WARNING"

        return {
            "client_name": client.client_name,
            "month": result[1].strftime("%Y-%m") if result[1] else datetime.now().strftime("%Y-%m"),
            "total_cost_usd": round(total_cost, 4),
            "total_calls": total_calls,
            "monthly_budget_usd": monthly_budget,
            "budget_used_percentage": round(budget_used_pct, 2),
            "budget_remaining_usd": round(monthly_budget - total_cost, 2) if monthly_budget else None,
            "budget_alert": budget_alert
        }

    except Exception as e:
        logger.error(f"Failed to get current month usage: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get current month usage: {str(e)}"
        )


@router.get("/logs")
async def get_generation_logs(
    limit: int = Query(100, ge=1, le=1000, description="Number of logs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Get detailed generation logs

    Returns individual LLM API calls with full details.
    Useful for debugging and detailed analysis.
    """
    try:
        query = db.query(LLMGenerationLog).filter(
            LLMGenerationLog.client_id == client.client_id
        )

        # Apply filters
        if provider:
            query = query.filter(LLMGenerationLog.provider == provider)

        if endpoint:
            query = query.filter(LLMGenerationLog.endpoint == endpoint)

        if success is not None:
            query = query.filter(LLMGenerationLog.success == success)

        # Get total count
        total_count = query.count()

        # Apply pagination
        logs = query.order_by(
            LLMGenerationLog.created_at.desc()
        ).limit(limit).offset(offset).all()

        return {
            "client_name": client.client_name,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "logs": [
                {
                    "log_id": str(log.log_id),
                    "created_at": log.created_at.isoformat(),
                    "endpoint": log.endpoint,
                    "provider": log.provider,
                    "model": log.model,
                    "input_tokens": log.input_tokens,
                    "output_tokens": log.output_tokens,
                    "total_tokens": log.input_tokens + log.output_tokens,
                    "total_cost_usd": float(log.input_cost_usd + log.output_cost_usd),
                    "generation_time_ms": log.generation_time_ms,
                    "success": log.success,
                    "error_message": log.error_message,
                    "error_type": log.error_type
                }
                for log in logs
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get generation logs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get generation logs: {str(e)}"
        )


@router.get("/logs/{log_id}")
async def get_log_details(
    log_id: UUID,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Get detailed information for a specific log entry

    Includes request/response metadata.
    """
    # Find log
    log = db.query(LLMGenerationLog).filter(
        LLMGenerationLog.log_id == log_id,
        LLMGenerationLog.client_id == client.client_id
    ).first()

    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    return {
        "log_id": str(log.log_id),
        "created_at": log.created_at.isoformat(),
        "client_name": client.client_name,
        "template_id": str(log.template_id) if log.template_id else None,
        "endpoint": log.endpoint,
        "provider": log.provider,
        "model": log.model,
        "input_tokens": log.input_tokens,
        "output_tokens": log.output_tokens,
        "input_cost_usd": float(log.input_cost_usd),
        "output_cost_usd": float(log.output_cost_usd),
        "total_cost_usd": float(log.input_cost_usd + log.output_cost_usd),
        "generation_time_ms": log.generation_time_ms,
        "success": log.success,
        "error_message": log.error_message,
        "error_type": log.error_type,
        "request_metadata": log.request_metadata,
        "response_metadata": log.response_metadata
    }
