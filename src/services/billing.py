"""
Billing Service
Tracks LLM API calls and costs to database for billing purposes
"""

from typing import Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.orm import Session

from src.models.database import LLMGenerationLog, APIClient
from src.utils.logger import logger


class BillingService:
    """Service for tracking LLM usage and costs"""

    @staticmethod
    def log_generation(
        db: Session,
        client: APIClient,
        endpoint: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        input_cost_usd: float,
        output_cost_usd: float,
        generation_time_ms: int,
        success: bool,
        template_id: Optional[UUID] = None,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
        request_metadata: Optional[Dict[str, Any]] = None,
        response_metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Log LLM generation to database for billing tracking

        Args:
            db: Database session
            client: API client who made the request
            endpoint: API endpoint called
            provider: LLM provider used
            model: Model used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            input_cost_usd: Cost of input tokens
            output_cost_usd: Cost of output tokens
            generation_time_ms: Time taken in milliseconds
            success: Whether generation succeeded
            template_id: Optional prompt template ID
            error_message: Optional error message if failed
            error_type: Optional error type classification
            request_metadata: Optional request details (JSONB)
            response_metadata: Optional response details (JSONB)

        Returns:
            UUID of created log entry
        """
        log_entry = LLMGenerationLog(
            log_id=uuid4(),
            created_at=datetime.now(),
            client_id=client.client_id,
            template_id=template_id,
            endpoint=endpoint,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_usd=input_cost_usd,
            output_cost_usd=output_cost_usd,
            generation_time_ms=generation_time_ms,
            success=success,
            error_message=error_message,
            error_type=error_type,
            request_metadata=request_metadata,
            response_metadata=response_metadata
        )

        try:
            db.add(log_entry)
            db.commit()

            logger.info(
                "billing_logged",
                client_name=client.client_name,
                endpoint=endpoint,
                provider=provider,
                total_cost=input_cost_usd + output_cost_usd,
                success=success
            )

            return log_entry.log_id

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to log billing: {str(e)}")
            raise

    @staticmethod
    def get_client_usage(
        db: Session,
        client_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get usage summary for a client within date range

        Args:
            db: Database session
            client_id: Client UUID
            start_date: Start date
            end_date: End date

        Returns:
            Dict with usage summary
        """
        # Query llm_daily_costs view
        query = db.execute(
            """
            SELECT
                DATE(day) as date,
                provider,
                endpoint,
                call_count,
                total_tokens,
                total_cost,
                avg_generation_time_ms,
                success_rate
            FROM llm_daily_costs
            WHERE client_id = :client_id
              AND day >= :start_date
              AND day <= :end_date
            ORDER BY day DESC, provider
            """,
            {
                "client_id": str(client_id),
                "start_date": start_date,
                "end_date": end_date
            }
        )

        results = query.fetchall()

        # Calculate totals
        total_cost = sum(row[5] for row in results)
        total_calls = sum(row[3] for row in results)
        total_tokens = sum(row[4] for row in results)

        return {
            "client_id": str(client_id),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_cost_usd": round(total_cost, 2),
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "daily_breakdown": [
                {
                    "date": row[0].isoformat() if row[0] else None,
                    "provider": row[1],
                    "endpoint": row[2],
                    "call_count": row[3],
                    "total_tokens": row[4],
                    "total_cost": float(row[5]),
                    "avg_generation_time_ms": float(row[6]) if row[6] else None,
                    "success_rate": float(row[7]) if row[7] else None
                }
                for row in results
            ]
        }

    @staticmethod
    def check_budget_alert(db: Session, client: APIClient) -> Optional[Dict[str, Any]]:
        """
        Check if client is approaching or over budget

        Args:
            db: Database session
            client: API client

        Returns:
            Dict with alert info if over 80% budget, None otherwise
        """
        if not client.monthly_budget_usd:
            return None

        # Query current month costs
        query = db.execute(
            """
            SELECT * FROM v_current_month_costs
            WHERE client_name = :client_name
            """,
            {"client_name": client.client_name}
        )

        result = query.fetchone()

        if not result:
            return None

        current_cost = float(result[2]) if result[2] else 0.0
        budget = float(client.monthly_budget_usd)
        usage_pct = (current_cost / budget * 100) if budget > 0 else 0

        if usage_pct >= 80:
            return {
                "alert": "budget_warning",
                "client_name": client.client_name,
                "monthly_budget_usd": budget,
                "current_cost_usd": current_cost,
                "usage_percentage": round(usage_pct, 2),
                "remaining_budget_usd": round(budget - current_cost, 2)
            }

        return None


# Create global instance
billing_service = BillingService()
