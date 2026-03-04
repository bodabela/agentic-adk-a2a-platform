"""LLM provider configuration loader."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ModelPricing(BaseModel):
    input_per_token: float = 0.0
    output_per_token: float = 0.0


class ModelConfig(BaseModel):
    display_name: str = ""
    pricing: ModelPricing = Field(default_factory=ModelPricing)
    max_tokens: int = 4096


class ProviderConfig(BaseModel):
    display_name: str = ""
    api_key_env: str = ""
    models: dict[str, ModelConfig] = Field(default_factory=dict)


class LLMDefaults(BaseModel):
    provider: str = "google"
    model: str = "gemini-2.0-flash"
    fallback_model: str = "gemini-1.5-pro"


class LLMProvidersConfig(BaseModel):
    defaults: LLMDefaults = Field(default_factory=LLMDefaults)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)

    def get_api_key(self, provider: str) -> str | None:
        """Resolve the API key for a provider from environment variables."""
        prov = self.providers.get(provider)
        if prov and prov.api_key_env:
            return os.environ.get(prov.api_key_env)
        return None

    def get_pricing(self, provider: str, model: str) -> ModelPricing:
        """Look up pricing for a provider/model pair."""
        prov = self.providers.get(provider)
        if prov:
            mdl = prov.models.get(model)
            if mdl:
                return mdl.pricing
        return ModelPricing()

    def validate_provider_model(self, provider: str, model: str) -> bool:
        """Check that a provider/model combination is defined in config."""
        prov = self.providers.get(provider)
        return prov is not None and model in prov.models

    def list_available(self) -> dict[str, Any]:
        """Return a serializable dict of providers and models for the API."""
        result = {}
        for prov_name, prov in self.providers.items():
            has_key = bool(self.get_api_key(prov_name))
            result[prov_name] = {
                "display_name": prov.display_name,
                "available": has_key,
                "models": {
                    m_name: {"display_name": m.display_name, "max_tokens": m.max_tokens}
                    for m_name, m in prov.models.items()
                },
            }
        return result


def load_llm_config(config_path: str | Path | None = None) -> LLMProvidersConfig:
    """Load llm_providers.yaml from disk."""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "llm_providers.yaml"
    config_path = Path(config_path)

    if not config_path.exists():
        return LLMProvidersConfig()

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return LLMProvidersConfig(**(raw or {}))
