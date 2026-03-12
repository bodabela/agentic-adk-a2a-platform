"""Tests for LLM provider configuration loader."""

import os
from pathlib import Path

import pytest

from src.shared.llm.config import (
    LLMProvidersConfig,
    LLMDefaults,
    ProviderConfig,
    ModelConfig,
    ModelPricing,
    load_llm_config,
)


class TestLLMConfig:
    def test_load_from_project_config(self):
        """Load the actual config/llm_providers.yaml."""
        config_path = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"
        config = load_llm_config(config_path)
        assert "google" in config.providers
        assert "anthropic" in config.providers
        assert "openai" in config.providers

    def test_defaults(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"
        config = load_llm_config(config_path)
        assert config.defaults.provider == "google"
        assert config.defaults.model == "gemini-3.1-pro-preview"

    def test_get_pricing_known_model(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"
        config = load_llm_config(config_path)
        pricing = config.get_pricing("google", "gemini-2.0-flash")
        assert pricing.input_per_token > 0
        assert pricing.output_per_token > 0

    def test_get_pricing_unknown_model(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"
        config = load_llm_config(config_path)
        pricing = config.get_pricing("google", "nonexistent")
        assert pricing.input_per_token == 0.0
        assert pricing.output_per_token == 0.0

    def test_validate_provider_model(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"
        config = load_llm_config(config_path)
        assert config.validate_provider_model("google", "gemini-2.0-flash") is True
        assert config.validate_provider_model("anthropic", "claude-sonnet-4-20250514") is True
        assert config.validate_provider_model("openai", "gpt-4o") is True
        assert config.validate_provider_model("google", "nonexistent") is False
        assert config.validate_provider_model("nonexistent", "gpt-4o") is False

    def test_list_available(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"
        config = load_llm_config(config_path)
        available = config.list_available()
        assert "google" in available
        assert "display_name" in available["google"]
        assert "models" in available["google"]
        assert "available" in available["google"]

    def test_get_api_key_from_env(self, monkeypatch):
        config = LLMProvidersConfig(
            providers={
                "test": ProviderConfig(
                    display_name="Test",
                    api_key_env="TEST_LLM_KEY",
                    models={},
                )
            }
        )
        monkeypatch.setenv("TEST_LLM_KEY", "sk-test-123")
        assert config.get_api_key("test") == "sk-test-123"

    def test_get_api_key_missing(self):
        config = LLMProvidersConfig(
            providers={
                "test": ProviderConfig(
                    display_name="Test",
                    api_key_env="NONEXISTENT_KEY_12345",
                    models={},
                )
            }
        )
        assert config.get_api_key("test") is None

    def test_load_nonexistent_file(self):
        """Loading a non-existent file returns empty defaults."""
        config = load_llm_config("/nonexistent/path.yaml")
        assert config.defaults.provider == "google"
        assert len(config.providers) == 0

    def test_anthropic_models(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"
        config = load_llm_config(config_path)
        anthropic = config.providers["anthropic"]
        assert "claude-sonnet-4-20250514" in anthropic.models
        assert "claude-haiku-3-20250414" in anthropic.models

    def test_openai_models(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"
        config = load_llm_config(config_path)
        openai_prov = config.providers["openai"]
        assert "gpt-4o" in openai_prov.models
        assert "gpt-4o-mini" in openai_prov.models
