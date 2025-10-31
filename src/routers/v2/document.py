"""
API v2 Document Operations Router
Provider and model agnostic document processing endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import time

from src.config.database import get_db
from src.config.settings import settings
from src.models.database import APIClient
from src.models.schemas import (
    V2DocumentParseRequest,
    V2DocumentExtractRequest,
    V2DocumentStructureRequest,
    V2DocumentClassifyRequest,
    V2DocumentCompareRequest,
    V2DocumentGenerateRequest,
    V2BaseResponse
)
from src.services.auth import get_current_client
from src.services.llm_core import llm_core
from src.services.billing import billing_service
from src.utils.logger import logger

# Import helper from text router
from src.routers.v2.text import _select_provider_and_model, _call_llm_with_prompt

router = APIRouter()


@router.post("/parse", response_model=V2BaseResponse)
async def parse_document(
    request: V2DocumentParseRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Parse document structure (headings, sections, tables)"""
    provider, model = _select_provider_and_model(request.provider, request.model, "analysis")

    elements_str = ", ".join(request.parse_elements)

    prompt = f"""Parse the following document and extract its structure.
Identify and extract: {elements_str}

Return the results in JSON format with clear hierarchy.

Document:
{request.document}"""

    system_prompt = "You are an expert at analyzing and parsing document structure."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/document/parse",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.3,
        request_metadata={
            "parse_elements": request.parse_elements,
            "document_length": len(request.document)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/extract", response_model=V2BaseResponse)
async def extract_from_document(
    request: V2DocumentExtractRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Extract specific data from documents (invoices, contracts, etc.)"""
    provider, model = _select_provider_and_model(request.provider, request.model, "analysis")

    fields_str = ", ".join(request.extract_fields)

    prompt = f"""Extract the following fields from the document: {fields_str}

Return the extracted data in JSON format with the field names as keys.
If a field is not found, use null as the value.

Document:
{request.document}"""

    system_prompt = "You are an expert at extracting structured data from unstructured documents like invoices, receipts, and contracts."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/document/extract",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.2,  # Low temperature for extraction
        request_metadata={
            "extract_fields": request.extract_fields,
            "document_length": len(request.document)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/structure", response_model=V2BaseResponse)
async def structure_document(
    request: V2DocumentStructureRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Convert unstructured documents to structured format"""
    provider, model = _select_provider_and_model(request.provider, request.model, "quality")

    format_instructions = {
        "json": "Convert the document to a structured JSON format with appropriate keys and values.",
        "markdown": "Convert the document to well-formatted Markdown with proper headings and sections.",
        "html": "Convert the document to semantic HTML with appropriate tags."
    }

    prompt = f"""{format_instructions.get(request.target_format, format_instructions["json"])}

Document to structure:
{request.document}"""

    system_prompt = f"You are an expert at converting unstructured text into structured {request.target_format} format."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/document/structure",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.3,
        request_metadata={
            "target_format": request.target_format,
            "document_length": len(request.document)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/classify", response_model=V2BaseResponse)
async def classify_document(
    request: V2DocumentClassifyRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Classify document type/category"""
    provider, model = _select_provider_and_model(request.provider, request.model, "analysis")

    if request.possible_types:
        types_str = "\n- ".join(request.possible_types)
        classification_instruction = f"""Classify this document into one of the following types:
- {types_str}

Respond with ONLY the type name, nothing else."""
    else:
        classification_instruction = """Identify what type of document this is (e.g., invoice, contract, email, report, receipt, etc.).

Respond with the document type and a brief explanation."""

    prompt = f"""{classification_instruction}

Document:
{request.document}"""

    system_prompt = "You are an expert at classifying and categorizing different types of documents."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/document/classify",
        max_tokens=request.max_tokens or 200,
        temperature=request.temperature or 0.1,  # Very low temperature for classification
        request_metadata={
            "possible_types": request.possible_types,
            "document_length": len(request.document)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/compare", response_model=V2BaseResponse)
async def compare_documents(
    request: V2DocumentCompareRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Compare multiple documents"""
    provider, model = _select_provider_and_model(request.provider, request.model, "quality")

    # Format documents for comparison
    docs_formatted = "\n\n".join([f"Document {i+1}:\n{doc}" for i, doc in enumerate(request.documents)])

    comparison_instructions = {
        "differences": "Identify and list all significant differences between these documents.",
        "similarities": "Identify and list all significant similarities between these documents.",
        "summary": "Provide a comprehensive comparison highlighting both differences and similarities."
    }

    prompt = f"""{comparison_instructions.get(request.comparison_type, comparison_instructions["differences"])}

{docs_formatted}

Provide a structured comparison with specific examples."""

    system_prompt = "You are an expert at comparing documents to identify changes, similarities, and differences."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/document/compare",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.4,
        request_metadata={
            "num_documents": len(request.documents),
            "comparison_type": request.comparison_type
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/generate", response_model=V2BaseResponse)
async def generate_document(
    request: V2DocumentGenerateRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Generate complete documents (reports, contracts, whitepapers, etc.)"""
    provider, model = _select_provider_and_model(request.provider, request.model, "quality")

    # Convert specifications to readable format
    specs_formatted = "\n".join([f"- {key}: {value}" for key, value in request.specifications.items()])

    prompt = f"""Generate a complete {request.document_type} with the following specifications:

{specs_formatted}

Create a well-structured, professional document that meets all the requirements."""

    system_prompt = f"You are an expert technical writer specializing in creating high-quality {request.document_type} documents."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/document/generate",
        max_tokens=request.max_tokens or 8000,  # Longer default for document generation
        temperature=request.temperature or 0.7,
        request_metadata={
            "document_type": request.document_type,
            "specifications": request.specifications
        }
    )

    return V2BaseResponse(success=True, **result)
