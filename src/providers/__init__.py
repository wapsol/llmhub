"""
Provider Registry
Auto-discovers and manages all LLM providers
"""

from typing import Dict, Type, Optional, List
from src.providers.base import BaseProvider, ProviderConfig
from src.utils.logger import logger


class ProviderRegistry:
    """
    Central registry for all LLM providers

    Providers auto-register themselves via register() function
    """
    _providers: Dict[str, Type[BaseProvider]] = {}
    _instances: Dict[str, BaseProvider] = {}

    @classmethod
    def register(cls, provider_class: Type[BaseProvider]):
        """Register a provider class"""
        # Create temporary instance to get provider name
        temp_config = ProviderConfig(name="temp", api_key=None)
        instance = provider_class(temp_config)
        provider_name = instance.provider_name

        cls._providers[provider_name] = provider_class
        logger.info(f"Registered provider: {provider_name}")

    @classmethod
    def initialize_provider(
        cls,
        provider_name: str,
        config: ProviderConfig
    ) -> Optional[BaseProvider]:
        """Initialize a provider with config"""
        if provider_name not in cls._providers:
            logger.warning(f"Provider not found: {provider_name}")
            return None

        provider_class = cls._providers[provider_name]
        instance = provider_class(config)

        if instance.is_available():
            cls._instances[provider_name] = instance
            logger.info(f"Initialized provider: {provider_name}")
            return instance
        else:
            logger.warning(f"Provider not available (missing config): {provider_name}")
            return None

    @classmethod
    def get_provider(cls, provider_name: str) -> Optional[BaseProvider]:
        """Get initialized provider instance"""
        return cls._instances.get(provider_name)

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """List all available (initialized) providers"""
        return list(cls._instances.keys())

    @classmethod
    def list_all_providers(cls) -> List[str]:
        """List all registered provider classes"""
        return list(cls._providers.keys())


# Auto-discover and register all providers
def _auto_register_providers():
    """Import all provider modules to trigger registration"""
    import importlib
    from pathlib import Path

    providers_dir = Path(__file__).parent

    for file in providers_dir.glob("*_provider.py"):
        module_name = file.stem
        try:
            module = importlib.import_module(f"src.providers.{module_name}")
            if hasattr(module, 'register'):
                module.register()
        except Exception as e:
            logger.error(f"Failed to register provider {module_name}: {e}")


# Auto-register on import
_auto_register_providers()
