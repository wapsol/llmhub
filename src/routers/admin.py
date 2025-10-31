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
from src.models.database import APIClient, PromptTemplate, LLMGenerationLog, LLMProvider, LLMModel
from src.utils.logger import logger
import anthropic
import openai as openai_lib
from groq import Groq

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
# Providers & Models
# ============================================================================

@router.get("/providers/registry")
async def get_providers_from_registry(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Get all LLM providers dynamically from the provider registry
    This endpoint is fully programmatic - new providers appear automatically
    Shows ALL registered providers, including unconfigured ones
    Also includes stored API keys from database
    """
    try:
        from src.providers import ProviderRegistry
        from src.providers.base import ProviderConfig

        # Query database for stored API keys
        db_providers = db.query(LLMProvider).filter(LLMProvider.is_active == True).all()
        db_keys_map = {p.provider_key: p.api_key for p in db_providers}

        providers_list = []

        # Get ALL registered providers (not just initialized ones)
        for provider_name in ProviderRegistry.list_all_providers():
            # Try to get initialized provider instance
            provider = ProviderRegistry.get_provider(provider_name)

            # If not initialized, create temporary instance to get metadata
            if not provider:
                provider_class = ProviderRegistry._providers.get(provider_name)
                if provider_class:
                    temp_config = ProviderConfig(name=provider_name, api_key=None)
                    provider = provider_class(temp_config)

            if not provider:
                logger.warning(f"Could not create provider instance for: {provider_name}")
                continue

            # Get metadata from provider
            metadata = provider.get_metadata()

            # Check if provider is actually configured and available
            is_configured = provider.is_available()

            # Get models list (only if configured)
            models_with_pricing = []
            if is_configured:
                models = provider.get_models()
                pricing_config = provider.config.pricing or {}

                # Build models with pricing info
                for model_key in models:
                    # Find pricing for this model (exact match or pattern match)
                    model_pricing = {"input": 0.0, "output": 0.0}

                    if model_key in pricing_config:
                        model_pricing = pricing_config[model_key]
                    else:
                        # Try pattern matching (e.g., "claude-3-sonnet" matches any sonnet model)
                        for price_key, price_data in pricing_config.items():
                            if price_key.lower() in model_key.lower():
                                model_pricing = price_data
                                break

                    models_with_pricing.append({
                        "id": model_key,
                        "name": model_key.replace("-", " ").replace("_", " ").title(),
                        "inputCost": model_pricing.get("input", 0.0),
                        "outputCost": model_pricing.get("output", 0.0),
                        "enabled": True,
                        "contextWindow": "varies"  # Could be enhanced per model
                    })

            # Get stored API key from database (if exists)
            stored_api_key = db_keys_map.get(provider.provider_name)
            api_key_masked = None
            has_stored_key = False

            if stored_api_key:
                has_stored_key = True
                # Mask the API key (first 8 chars + ... + last 4 chars)
                if len(stored_api_key) > 12:
                    api_key_masked = stored_api_key[:8] + "..." + stored_api_key[-4:]
                else:
                    api_key_masked = "***"

            providers_list.append({
                "provider_key": provider.provider_name,
                "display_name": metadata.display_name,
                "description": metadata.description,
                "logo_url": metadata.logo_url,
                "website_url": metadata.website_url,
                "requires_api_key": metadata.requires_api_key,
                "requires_base_url": metadata.requires_base_url,
                "configured": is_configured,
                "models": models_with_pricing,
                "api_key_masked": api_key_masked,
                "has_stored_key": has_stored_key
            })

        logger.info(f"Returned {len(providers_list)} providers from registry (including unconfigured)")
        return providers_list

    except Exception as e:
        logger.error(f"Error getting providers from registry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch providers from registry: {str(e)}"
        )


@router.get("/providers")
async def get_providers(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Get all LLM providers with their configuration status and model count
    """
    try:
        providers = db.query(LLMProvider).filter(
            LLMProvider.is_active == True
        ).order_by(LLMProvider.sort_order).all()

        result = []
        for provider in providers:
            # Check if API key is configured
            api_key_configured = False
            if provider.api_key_env_var:
                api_key_configured = bool(getattr(settings, provider.api_key_env_var, None))

            # Count models for this provider
            model_count = db.query(LLMModel).filter(
                LLMModel.provider_id == provider.provider_id,
                LLMModel.is_active == True
            ).count()

            # Mask the stored API key if it exists
            api_key_masked = None
            if provider.api_key:
                api_key_masked = provider.api_key[:8] + "..." + provider.api_key[-4:] if len(provider.api_key) > 12 else "***"

            result.append({
                "provider_id": str(provider.provider_id),
                "provider_key": provider.provider_key,
                "display_name": provider.display_name,
                "description": provider.description,
                "api_key_configured": api_key_configured,
                "api_key_masked": api_key_masked,
                "has_stored_key": bool(provider.api_key),
                "model_count": model_count,
                "logo_url": provider.logo_url,
                "website_url": provider.website_url
            })

        return result

    except Exception as e:
        logger.error(f"Error getting providers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch providers"
        )


@router.get("/providers/{provider_id}/models")
async def get_provider_models(provider_id: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Get all models for a specific provider
    """
    try:
        models = db.query(LLMModel).filter(
            LLMModel.provider_id == provider_id,
            LLMModel.is_active == True
        ).order_by(LLMModel.sort_order).all()

        return [
            {
                "model_id": str(model.model_id),
                "model_key": model.model_key,
                "display_name": model.display_name,
                "description": model.description,
                "context_window": model.context_window,
                "cost_per_million_input": float(model.cost_per_million_input),
                "cost_per_million_output": float(model.cost_per_million_output),
                "price_per_million_input": float(model.price_per_million_input),
                "price_per_million_output": float(model.price_per_million_output),
                "is_enabled": model.is_enabled
            }
            for model in models
        ]

    except Exception as e:
        logger.error(f"Error getting provider models: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch provider models"
        )


@router.get("/models")
async def get_all_models(
    provider_key: str = None,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get all LLM models, optionally filtered by provider
    """
    try:
        query = db.query(LLMModel, LLMProvider).join(
            LLMProvider, LLMModel.provider_id == LLMProvider.provider_id
        ).filter(
            LLMModel.is_active == True,
            LLMProvider.is_active == True
        )

        # Filter by provider if specified
        if provider_key:
            query = query.filter(LLMProvider.provider_key == provider_key)

        results = query.order_by(
            LLMProvider.sort_order,
            LLMModel.sort_order
        ).all()

        return [
            {
                "model_id": str(model.model_id),
                "model_key": model.model_key,
                "display_name": model.display_name,
                "description": model.description,
                "context_window": model.context_window,
                "cost_per_million_input": float(model.cost_per_million_input),
                "cost_per_million_output": float(model.cost_per_million_output),
                "price_per_million_input": float(model.price_per_million_input),
                "price_per_million_output": float(model.price_per_million_output),
                "is_enabled": model.is_enabled,
                "provider": {
                    "provider_id": str(provider.provider_id),
                    "provider_key": provider.provider_key,
                    "display_name": provider.display_name
                }
            }
            for model, provider in results
        ]

    except Exception as e:
        logger.error(f"Error getting models: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch models"
        )


@router.patch("/models/{model_id}")
async def update_model(
    model_id: str,
    model_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update model pricing and configuration
    """
    try:
        model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model not found"
            )

        # Update allowed fields
        if "cost_per_million_input" in model_data:
            model.cost_per_million_input = model_data["cost_per_million_input"]
        if "cost_per_million_output" in model_data:
            model.cost_per_million_output = model_data["cost_per_million_output"]
        if "price_per_million_input" in model_data:
            model.price_per_million_input = model_data["price_per_million_input"]
        if "price_per_million_output" in model_data:
            model.price_per_million_output = model_data["price_per_million_output"]
        if "is_enabled" in model_data:
            model.is_enabled = model_data["is_enabled"]

        model.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(model)

        logger.info(f"Updated model: {model.model_key}")

        return {
            "model_id": str(model.model_id),
            "message": "Model updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating model: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update model: {str(e)}"
        )


@router.post("/models/{model_id}/toggle")
async def toggle_model(model_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Toggle model enabled status
    """
    try:
        model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model not found"
            )

        model.is_enabled = not model.is_enabled
        model.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(model)

        logger.info(f"Toggled model {model.model_key} to {'enabled' if model.is_enabled else 'disabled'}")

        return {
            "model_id": str(model.model_id),
            "is_enabled": model.is_enabled,
            "message": f"Model {'enabled' if model.is_enabled else 'disabled'} successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error toggling model: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle model"
        )


# ============================================================================
# Provider Management
# ============================================================================

@router.put("/providers/{provider_key}/api-key")
async def update_provider_api_key(
    provider_key: str,
    data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update provider API key
    """
    try:
        provider = db.query(LLMProvider).filter(
            LLMProvider.provider_key == provider_key
        ).first()

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        api_key = data.get("api_key", "").strip()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key is required"
            )

        provider.api_key = api_key
        provider.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(provider)

        logger.info(f"Updated API key for provider: {provider_key}")

        # Mask the key for display
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"

        return {
            "provider_key": provider_key,
            "api_key_masked": masked_key,
            "message": "API key updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating provider API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update API key: {str(e)}"
        )


@router.delete("/providers/{provider_key}/api-key")
async def delete_provider_api_key(
    provider_key: str,
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete provider API key
    """
    try:
        provider = db.query(LLMProvider).filter(
            LLMProvider.provider_key == provider_key
        ).first()

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        provider.api_key = None
        provider.updated_at = datetime.utcnow()

        db.commit()

        logger.info(f"Deleted API key for provider: {provider_key}")

        return {"message": "API key deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting provider API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete API key"
        )


@router.post("/providers/{provider_key}/test-key")
async def test_provider_api_key(
    provider_key: str,
    data: Dict[str, Any] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Test provider API key and fetch available models with costs
    Returns detailed step-by-step status of the testing process
    Accepts optional api_key in request body to test before saving
    """
    steps = []

    def add_step(name: str, status: str, message: str = "", error: str = ""):
        steps.append({
            "step": name,
            "status": status,  # "running", "success", "failed"
            "message": message,
            "error": error
        })

    try:
        # Step 1: Validate provider
        add_step("validate_provider", "running", "Validating provider configuration...")

        provider = db.query(LLMProvider).filter(
            LLMProvider.provider_key == provider_key
        ).first()

        if not provider:
            add_step("validate_provider", "failed", "", "Provider not found in database")
            return {
                "success": False,
                "steps": steps,
                "error": "Provider not found"
            }

        add_step("validate_provider", "success", f"Provider '{provider.display_name}' found")

        # Step 2: Get API key
        add_step("get_api_key", "running", "Retrieving API key...")

        # Use provided key from request body, or fall back to stored/env key
        api_key = None
        if data and "api_key" in data:
            api_key = data.get("api_key", "").strip()
            add_step("get_api_key", "success", "Using API key from request")
        else:
            api_key = provider.api_key or getattr(settings, provider.api_key_env_var, None)
            if api_key:
                add_step("get_api_key", "success", "Using stored/environment API key")
            else:
                add_step("get_api_key", "failed", "", "No API key configured for this provider")
                return {
                    "success": False,
                    "steps": steps,
                    "error": "No API key configured"
                }

        # Step 3: Initialize client
        add_step("init_client", "running", f"Initializing {provider.display_name} client...")

        discovered_models = []

        try:
            # Test the API key and fetch models based on provider
            if provider_key == "claude":
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    add_step("init_client", "success", "Anthropic client initialized")

                    # Step 4: Test authentication & fetch models
                    add_step("authenticate", "running", "Fetching models from Anthropic API...")

                    # Call Anthropic models API
                    import httpx
                    response = httpx.get(
                        "https://api.anthropic.com/v1/models",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01"
                        },
                        timeout=30.0
                    )
                    response.raise_for_status()
                    models_data = response.json()

                    add_step("authenticate", "success", "Authentication successful")

                    # Step 5: Parse models and add pricing
                    add_step("fetch_models", "running", "Processing models and pricing data...")

                    # Pricing lookup for Claude models (per million tokens)
                    claude_pricing = {
                        "claude-opus-4": {"input": 15.00, "output": 75.00},
                        "claude-sonnet-4": {"input": 3.00, "output": 15.00},
                        "claude-haiku-4.5": {"input": 1.00, "output": 5.00},
                        "claude-3.5-haiku": {"input": 0.80, "output": 4.00},
                        "claude-3-haiku": {"input": 0.25, "output": 1.25},
                        "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
                        "claude-3-sonnet": {"input": 3.00, "output": 15.00},
                        "claude-3-opus": {"input": 15.00, "output": 75.00},
                    }

                    discovered_models = []
                    for model in models_data.get("data", []):
                        model_id = model.get("id", "")
                        display_name = model.get("display_name", model_id)

                        # Find pricing based on model ID
                        pricing = {"input": 0.0, "output": 0.0}
                        for key, price in claude_pricing.items():
                            if key in model_id.lower():
                                pricing = price
                                break

                        discovered_models.append({
                            "model_key": model_id,
                            "display_name": display_name,
                            "cost_input": pricing["input"],
                            "cost_output": pricing["output"]
                        })

                    add_step("fetch_models", "success", f"Found {len(discovered_models)} models with pricing data")

                except anthropic.AuthenticationError as e:
                    add_step("init_client", "failed", "", f"Authentication failed: Invalid API key")
                    return {
                        "success": False,
                        "steps": steps,
                        "error": "Invalid API key"
                    }
                except anthropic.PermissionDeniedError as e:
                    add_step("authenticate", "failed", "", f"Permission denied: {str(e)}")
                    return {
                        "success": False,
                        "steps": steps,
                        "error": "Permission denied"
                    }
                except anthropic.RateLimitError as e:
                    add_step("authenticate", "failed", "", f"Rate limit exceeded: {str(e)}")
                    return {
                        "success": False,
                        "steps": steps,
                        "error": "Rate limit exceeded"
                    }
                except anthropic.APIError as e:
                    add_step("authenticate", "failed", "", f"API error: {str(e)}")
                    return {
                        "success": False,
                        "steps": steps,
                        "error": f"API error: {str(e)}"
                    }

            elif provider_key == "openai":
                try:
                    client = openai_lib.OpenAI(api_key=api_key)
                    add_step("init_client", "success", "OpenAI client initialized")

                    # Step 4: Test authentication & fetch models
                    add_step("authenticate", "running", "Fetching models from OpenAI API...")

                    models_response = client.models.list()
                    add_step("authenticate", "success", "Authentication successful")

                    # Step 5: Parse models and add pricing
                    add_step("fetch_models", "running", "Processing models and pricing data...")

                    # Pricing lookup for OpenAI models (per million tokens)
                    openai_pricing = {
                        "gpt-4o": {"input": 2.50, "output": 10.00},
                        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
                        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
                        "gpt-4": {"input": 30.00, "output": 60.00},
                        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
                        "dall-e-3": {"input": 0.04, "output": 0.08},  # per image
                        "dall-e-2": {"input": 0.02, "output": 0.02},  # per image
                        "whisper-1": {"input": 0.006, "output": 0.0},  # per minute
                        "tts-1": {"input": 15.00, "output": 0.0},  # per million characters
                        "tts-1-hd": {"input": 30.00, "output": 0.0},  # per million characters
                        "text-embedding-3-small": {"input": 0.02, "output": 0.0},
                        "text-embedding-3-large": {"input": 0.13, "output": 0.0},
                        "text-embedding-ada-002": {"input": 0.10, "output": 0.0},
                    }

                    discovered_models = []
                    for model in models_response.data:
                        model_id = model.id

                        # Find pricing based on model ID
                        pricing = {"input": 0.0, "output": 0.0}
                        for key, price in openai_pricing.items():
                            if key in model_id:
                                pricing = price
                                break

                        # Create display name from model ID
                        display_name = model_id.replace("-", " ").title()

                        discovered_models.append({
                            "model_key": model_id,
                            "display_name": display_name,
                            "cost_input": pricing["input"],
                            "cost_output": pricing["output"]
                        })

                    add_step("fetch_models", "success", f"Found {len(discovered_models)} models with pricing data")

                except openai_lib.AuthenticationError as e:
                    add_step("authenticate", "failed", "", f"Authentication failed: Invalid API key")
                    return {
                        "success": False,
                        "steps": steps,
                        "error": "Invalid API key"
                    }
                except openai_lib.PermissionDeniedError as e:
                    add_step("authenticate", "failed", "", f"Permission denied: {str(e)}")
                    return {
                        "success": False,
                        "steps": steps,
                        "error": "Permission denied"
                    }
                except openai_lib.RateLimitError as e:
                    add_step("authenticate", "failed", "", f"Rate limit exceeded: {str(e)}")
                    return {
                        "success": False,
                        "steps": steps,
                        "error": "Rate limit exceeded"
                    }
                except openai_lib.APIError as e:
                    add_step("authenticate", "failed", "", f"API error: {str(e)}")
                    return {
                        "success": False,
                        "steps": steps,
                        "error": f"API error: {str(e)}"
                    }

            elif provider_key == "groq":
                try:
                    client = Groq(api_key=api_key)
                    add_step("init_client", "success", "Groq client initialized")

                    # Step 4: Test authentication & fetch models
                    add_step("authenticate", "running", "Fetching models from Groq API...")

                    models_response = client.models.list()
                    add_step("authenticate", "success", "Authentication successful")

                    # Step 5: Parse models and add pricing
                    add_step("fetch_models", "running", "Processing models and pricing data...")

                    # Pricing lookup for Groq models (per million tokens)
                    groq_pricing = {
                        "llama-3.3-70b": {"input": 0.59, "output": 0.79},
                        "llama-3.1-70b": {"input": 0.59, "output": 0.79},
                        "llama-3.1-8b": {"input": 0.05, "output": 0.08},
                        "llama3-70b": {"input": 0.59, "output": 0.79},
                        "llama3-8b": {"input": 0.05, "output": 0.08},
                        "llama2-70b": {"input": 0.70, "output": 0.80},
                        "mixtral-8x7b": {"input": 0.24, "output": 0.24},
                        "gemma-7b": {"input": 0.07, "output": 0.07},
                        "gemma2-9b": {"input": 0.20, "output": 0.20},
                        "llama-guard": {"input": 0.20, "output": 0.20},
                    }

                    discovered_models = []
                    for model in models_response.data:
                        model_id = model.id

                        # Find pricing based on model ID
                        pricing = {"input": 0.0, "output": 0.0}
                        for key, price in groq_pricing.items():
                            if key in model_id.lower():
                                pricing = price
                                break

                        # Create display name from model ID
                        display_name = model_id.replace("-", " ").replace("_", " ").title()

                        discovered_models.append({
                            "model_key": model_id,
                            "display_name": display_name,
                            "cost_input": pricing["input"],
                            "cost_output": pricing["output"]
                        })

                    add_step("fetch_models", "success", f"Found {len(discovered_models)} models with pricing data")

                except Exception as e:
                    error_msg = str(e)
                    if "401" in error_msg or "authentication" in error_msg.lower():
                        add_step("authenticate", "failed", "", f"Authentication failed: Invalid API key")
                        return {
                            "success": False,
                            "steps": steps,
                            "error": "Invalid API key"
                        }
                    else:
                        add_step("authenticate", "failed", "", f"API error: {error_msg}")
                        return {
                            "success": False,
                            "steps": steps,
                            "error": f"API error: {error_msg}"
                        }

        except Exception as e:
            add_step("init_client", "failed", "", f"Client initialization error: {str(e)}")
            return {
                "success": False,
                "steps": steps,
                "error": f"Client initialization error: {str(e)}"
            }

        # Step 6: Save models to database
        add_step("save_models", "running", "Saving discovered models to database...")

        try:
            models_saved = 0
            models_updated = 0

            for model_data in discovered_models:
                # Check if model already exists
                existing_model = db.query(LLMModel).filter(
                    LLMModel.model_key == model_data["model_key"],
                    LLMModel.provider_id == provider.provider_id
                ).first()

                if existing_model:
                    # Update existing model
                    existing_model.display_name = model_data["display_name"]
                    existing_model.cost_per_million_input = model_data["cost_input"]
                    existing_model.cost_per_million_output = model_data["cost_output"]
                    existing_model.price_per_million_input = model_data["cost_input"]
                    existing_model.price_per_million_output = model_data["cost_output"]
                    existing_model.is_active = True
                    existing_model.updated_at = datetime.utcnow()
                    models_updated += 1
                else:
                    # Create new model
                    new_model = LLMModel(
                        provider_id=provider.provider_id,
                        model_key=model_data["model_key"],
                        display_name=model_data["display_name"],
                        description=f"{model_data['display_name']} model",
                        cost_per_million_input=model_data["cost_input"],
                        cost_per_million_output=model_data["cost_output"],
                        price_per_million_input=model_data["cost_input"],
                        price_per_million_output=model_data["cost_output"],
                        is_enabled=True,
                        is_active=True,
                        sort_order=0
                    )
                    db.add(new_model)
                    models_saved += 1

            db.commit()
            add_step("save_models", "success", f"Saved {models_saved} new models, updated {models_updated} existing models")

        except Exception as e:
            db.rollback()
            logger.error(f"Error saving models to database: {str(e)}")
            add_step("save_models", "failed", "", f"Failed to save models: {str(e)}")

        logger.info(f"Successfully tested API key for provider: {provider_key}")

        return {
            "success": True,
            "provider_key": provider_key,
            "steps": steps,
            "models_discovered": len(discovered_models),
            "models": discovered_models,
            "message": f"API key is valid! Found {len(discovered_models)} models."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing provider API key: {str(e)}")
        add_step("unknown_error", "failed", "", f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "steps": steps,
            "error": f"Unexpected error: {str(e)}"
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


@router.patch("/clients/{client_id}")
async def update_client(
    client_id: str,
    client_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update API client details
    Allows updating: client_name, organization, contact_email, rate_limit, monthly_budget_usd, is_active
    """
    try:
        client = db.query(APIClient).filter(APIClient.client_id == client_id).first()

        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )

        # Update allowed fields
        if "client_name" in client_data:
            # Check if new name conflicts with existing client
            existing = db.query(APIClient).filter(
                APIClient.client_name == client_data["client_name"],
                APIClient.client_id != client_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Client with name '{client_data['client_name']}' already exists"
                )
            client.client_name = client_data["client_name"]

        if "organization" in client_data:
            client.organization = client_data["organization"]
        if "contact_email" in client_data:
            client.contact_email = client_data["contact_email"]
        if "rate_limit" in client_data:
            client.rate_limit = client_data["rate_limit"]
        if "monthly_budget_usd" in client_data:
            client.monthly_budget_usd = client_data["monthly_budget_usd"]
        if "is_active" in client_data:
            client.is_active = client_data["is_active"]

        client.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(client)

        logger.info(f"Updated client: {client.client_name}")

        return {
            "client_id": str(client.client_id),
            "client_name": client.client_name,
            "api_key": client.api_key,
            "organization": client.organization,
            "contact_email": client.contact_email,
            "is_active": client.is_active,
            "rate_limit": client.rate_limit,
            "monthly_budget_usd": float(client.monthly_budget_usd) if client.monthly_budget_usd else None,
            "message": "Client updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating client: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update client: {str(e)}"
        )


# ============================================================================
# Billing & Usage
# ============================================================================

@router.get("/billing/organizations")
async def get_organizations(db: Session = Depends(get_db)) -> List[str]:
    """
    Get list of unique organizations from API clients
    Used for filtering billing data by organization
    """
    try:
        results = db.query(APIClient.organization).distinct().filter(
            APIClient.organization.isnot(None),
            APIClient.organization != ''
        ).order_by(APIClient.organization).all()

        return [row[0] for row in results]

    except Exception as e:
        logger.error(f"Error getting organizations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch organizations"
        )


@router.get("/billing/stats")
async def get_billing_stats(
    days: int = 30,
    organization: str = None,
    client_name: str = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get billing statistics for specified time range
    Optionally filtered by organization and/or client name
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Build query with optional filters
        query = db.query(
            func.count(LLMGenerationLog.log_id).label('total_calls'),
            func.sum(LLMGenerationLog.input_cost_usd + LLMGenerationLog.output_cost_usd).label('total_cost')
        ).join(
            APIClient,
            LLMGenerationLog.client_id == APIClient.client_id
        ).filter(
            LLMGenerationLog.created_at >= cutoff_date
        )

        # Apply organization filter if provided
        if organization:
            query = query.filter(APIClient.organization == organization)

        # Apply client name filter if provided
        if client_name:
            query = query.filter(APIClient.client_name == client_name)

        stats = query.first()

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
    organization: str = None,
    client_name: str = None,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get daily cost breakdown by provider
    Optionally filtered by organization and/or client name
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Build query with optional filters
        query = db.query(
            func.date_trunc('day', LLMGenerationLog.created_at).label('day'),
            LLMGenerationLog.provider,
            func.count(LLMGenerationLog.log_id).label('total_calls'),
            func.sum(LLMGenerationLog.input_cost_usd + LLMGenerationLog.output_cost_usd).label('total_cost')
        ).join(
            APIClient,
            LLMGenerationLog.client_id == APIClient.client_id
        ).filter(
            LLMGenerationLog.created_at >= cutoff_date
        )

        # Apply organization filter if provided
        if organization:
            query = query.filter(APIClient.organization == organization)

        # Apply client name filter if provided
        if client_name:
            query = query.filter(APIClient.client_name == client_name)

        results = query.group_by(
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
    organization: str = None,
    client_name: str = None,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get cost breakdown by client
    Optionally filtered by organization and/or client name
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Build query with optional filters
        query = db.query(
            APIClient.client_name,
            APIClient.organization,
            APIClient.monthly_budget_usd,
            func.count(LLMGenerationLog.log_id).label('total_calls'),
            func.sum(LLMGenerationLog.input_tokens + LLMGenerationLog.output_tokens).label('total_tokens'),
            func.sum(LLMGenerationLog.input_cost_usd + LLMGenerationLog.output_cost_usd).label('total_cost')
        ).join(
            LLMGenerationLog,
            APIClient.client_id == LLMGenerationLog.client_id
        ).filter(
            LLMGenerationLog.created_at >= cutoff_date
        )

        # Apply organization filter if provided
        if organization:
            query = query.filter(APIClient.organization == organization)

        # Apply client name filter if provided
        if client_name:
            query = query.filter(APIClient.client_name == client_name)

        results = query.group_by(
            APIClient.client_name,
            APIClient.organization,
            APIClient.monthly_budget_usd
        ).order_by(
            func.sum(LLMGenerationLog.input_cost_usd + LLMGenerationLog.output_cost_usd).desc()
        ).all()

        return [
            {
                "client_name": row.client_name,
                "organization": row.organization,
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
