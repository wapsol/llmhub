"""
API v2 Routers
Provider and model agnostic endpoints with intelligent routing
"""

from src.routers.v2 import text, document, image, video, audio, moderation, embeddings

__all__ = [
    "text",
    "document",
    "image",
    "video",
    "audio",
    "moderation",
    "embeddings"
]
