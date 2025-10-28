"""
Prompt Library Router
API endpoints for managing reusable prompt templates
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from src.config.database import get_db
from src.models.database import APIClient, PromptTemplate, PromptVersion
from src.models.schemas import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse
)
from src.services.auth import get_current_client
from src.utils.logger import logger

router = APIRouter()


@router.get("/templates", response_model=List[PromptTemplateResponse])
async def list_templates(
    template_type: Optional[str] = Query(None, description="Filter by template type"),
    is_public: Optional[bool] = Query(None, description="Filter by public status"),
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    List all accessible prompt templates

    Returns:
        - Public templates (is_public=true)
        - Templates owned by the current client
    """
    try:
        query = db.query(PromptTemplate)

        # Filter: public templates OR owned by current client
        from sqlalchemy import or_
        query = query.filter(
            or_(
                PromptTemplate.is_public == True,
                PromptTemplate.owner_client_id == client.client_id
            )
        )

        # Optional filters
        if template_type:
            query = query.filter(PromptTemplate.template_type == template_type)

        if is_public is not None:
            query = query.filter(PromptTemplate.is_public == is_public)

        # Only active templates
        query = query.filter(PromptTemplate.is_active == True)

        templates = query.order_by(PromptTemplate.created_at.desc()).all()

        logger.info(
            "templates_listed",
            client=client.client_name,
            count=len(templates),
            template_type=template_type
        )

        return templates

    except Exception as e:
        logger.error(f"Failed to list templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list templates")


@router.get("/templates/{template_id}", response_model=PromptTemplateResponse)
async def get_template(
    template_id: UUID,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Get a specific prompt template by ID

    Returns:
        Template details if accessible (public or owned by client)
    """
    template = db.query(PromptTemplate).filter(
        PromptTemplate.template_id == template_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check access: must be public or owned by client
    if not template.is_public and template.owner_client_id != client.client_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: template is private"
        )

    return template


@router.post("/templates", response_model=PromptTemplateResponse, status_code=201)
async def create_template(
    request: PromptTemplateCreate,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Create a new prompt template

    The template will be owned by the current API client.
    Can be made public or kept private.
    """
    try:
        # Create template
        template = PromptTemplate(
            template_name=request.template_name,
            template_type=request.template_type.value,
            description=request.description,
            system_prompt=request.system_prompt,
            user_prompt_template=request.user_prompt_template,
            variables=request.variables,
            output_config=request.output_config,
            is_public=request.is_public,
            owner_client_id=client.client_id,
            is_active=True,
            usage_count=0
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        # Create initial version
        version = PromptVersion(
            template_id=template.template_id,
            version_number=1,
            system_prompt=request.system_prompt,
            user_prompt_template=request.user_prompt_template,
            variables=request.variables,
            output_config=request.output_config,
            status="production",
            created_by_client_id=client.client_id,
            change_notes="Initial version"
        )

        db.add(version)
        db.commit()

        logger.info(
            "template_created",
            client=client.client_name,
            template_id=str(template.template_id),
            template_name=template.template_name
        )

        return template

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create template: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create template: {str(e)}"
        )


@router.put("/templates/{template_id}", response_model=PromptTemplateResponse)
async def update_template(
    template_id: UUID,
    request: PromptTemplateUpdate,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Update an existing prompt template

    Only the owner can update a template.
    Creates a new version if system_prompt or user_prompt_template changes.
    """
    # Get template
    template = db.query(PromptTemplate).filter(
        PromptTemplate.template_id == template_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check ownership
    if template.owner_client_id != client.client_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: you can only update your own templates"
        )

    try:
        # Track if prompts changed (requires new version)
        prompts_changed = False

        # Update fields
        if request.template_name is not None:
            template.template_name = request.template_name

        if request.description is not None:
            template.description = request.description

        if request.system_prompt is not None:
            template.system_prompt = request.system_prompt
            prompts_changed = True

        if request.user_prompt_template is not None:
            template.user_prompt_template = request.user_prompt_template
            prompts_changed = True

        if request.variables is not None:
            template.variables = request.variables
            prompts_changed = True

        if request.is_active is not None:
            template.is_active = request.is_active

        template.updated_at = datetime.now()

        # Create new version if prompts changed
        if prompts_changed:
            # Get latest version number
            latest_version = db.query(PromptVersion).filter(
                PromptVersion.template_id == template_id
            ).order_by(PromptVersion.version_number.desc()).first()

            new_version_number = (latest_version.version_number + 1) if latest_version else 1

            # Create new version
            new_version = PromptVersion(
                template_id=template.template_id,
                version_number=new_version_number,
                system_prompt=template.system_prompt,
                user_prompt_template=template.user_prompt_template,
                variables=template.variables,
                status="production",
                created_by_client_id=client.client_id,
                change_notes="Updated via API"
            )

            db.add(new_version)

        db.commit()
        db.refresh(template)

        logger.info(
            "template_updated",
            client=client.client_name,
            template_id=str(template_id),
            prompts_changed=prompts_changed
        )

        return template

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update template: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update template: {str(e)}"
        )


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Delete (soft delete) a prompt template

    Only the owner can delete a template.
    Sets is_active=false instead of actual deletion.
    """
    # Get template
    template = db.query(PromptTemplate).filter(
        PromptTemplate.template_id == template_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check ownership
    if template.owner_client_id != client.client_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: you can only delete your own templates"
        )

    try:
        # Soft delete
        template.is_active = False
        template.updated_at = datetime.now()

        db.commit()

        logger.info(
            "template_deleted",
            client=client.client_name,
            template_id=str(template_id)
        )

        return None  # 204 No Content

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete template: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete template: {str(e)}"
        )


@router.get("/templates/{template_id}/versions")
async def list_template_versions(
    template_id: UUID,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    List all versions of a prompt template

    Only accessible to template owner.
    """
    # Get template
    template = db.query(PromptTemplate).filter(
        PromptTemplate.template_id == template_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check access
    if not template.is_public and template.owner_client_id != client.client_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: template is private"
        )

    # Get versions
    versions = db.query(PromptVersion).filter(
        PromptVersion.template_id == template_id
    ).order_by(PromptVersion.version_number.desc()).all()

    return {
        "template_id": str(template_id),
        "template_name": template.template_name,
        "versions": [
            {
                "version_id": str(v.version_id),
                "version_number": v.version_number,
                "status": v.status,
                "created_at": v.created_at.isoformat(),
                "change_notes": v.change_notes,
                "usage_count": v.usage_count,
                "success_rate": float(v.success_rate) if v.success_rate else None
            }
            for v in versions
        ]
    }


@router.post("/templates/{template_id}/test")
async def test_template(
    template_id: UUID,
    variables: dict,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Test a prompt template with sample variables

    Returns the rendered prompt without calling the LLM.
    Useful for testing variable substitution.
    """
    # Get template
    template = db.query(PromptTemplate).filter(
        PromptTemplate.template_id == template_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check access
    if not template.is_public and template.owner_client_id != client.client_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: template is private"
        )

    try:
        # Simple variable substitution
        rendered_system = template.system_prompt
        rendered_user = template.user_prompt_template

        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"  # {{variable_name}}
            rendered_system = rendered_system.replace(placeholder, str(value))
            rendered_user = rendered_user.replace(placeholder, str(value))

        return {
            "success": True,
            "template_id": str(template_id),
            "template_name": template.template_name,
            "rendered_prompts": {
                "system_prompt": rendered_system,
                "user_prompt": rendered_user
            },
            "variables_used": variables
        }

    except Exception as e:
        logger.error(f"Failed to test template: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test template: {str(e)}"
        )
