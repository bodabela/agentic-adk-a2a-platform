from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API
    app_name: str = "Agent Platform"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # LLM config (provider/model/pricing defined in YAML, API keys in .env)
    llm_config_path: str = "../config/llm_providers.yaml"

    # Modules (legacy — kept for backward compatibility during migration)
    modules_dir: str = "../modules"
    flows_dir: str = "../flows"
    workspace_dir: str = "../workspace"

    # Declarative agent & root-agent definitions
    agents_dir: str = "../agents"
    root_agents_dir: str = "../root_agents"

    # Cost
    cost_tracking_enabled: bool = True

    # CORS (for frontend)
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env", "env_prefix": "APP_", "extra": "ignore"}
