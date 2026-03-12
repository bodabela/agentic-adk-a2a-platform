from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API
    app_name: str = "Agent Platform"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Project selection (e.g. "personal_assistant")
    # When set, agents_dir / root_agents_dir / flows_dir default to
    # ../projects/{project}/agents  etc.
    project: str = "personal_assistant"

    # LLM config (provider/model/pricing defined in YAML, API keys in .env)
    llm_config_path: str = "../config/llm_providers.yaml"

    # Directories (auto-derived from `project` if not explicitly overridden)
    flows_dir: str = ""
    workspace_dir: str = "../workspace"

    # Declarative agent & root-agent definitions
    agents_dir: str = ""
    root_agents_dir: str = ""

    @model_validator(mode="after")
    def _resolve_project_dirs(self) -> "Settings":
        """Fill in blank directory paths from the active project name."""
        base = f"../projects/{self.project}"
        if not self.agents_dir:
            self.agents_dir = f"{base}/agents"
        if not self.root_agents_dir:
            self.root_agents_dir = f"{base}/root_agents"
        if not self.flows_dir:
            self.flows_dir = f"{base}/flows"
        return self

    # ADK session persistence
    adk_sessions_db: str = "/data/adk/sessions.db"

    # Interactions / channels
    interactions_db: str = "interactions.db"
    channels_config_path: str = "../config/channels.yaml"

    # Channel: Teams
    teams_enabled: bool = False
    teams_app_id: str = ""
    teams_app_password: str = ""
    teams_service_url: str = "https://smba.trafficmanager.net/emea/"
    teams_default_conversation_id: str = ""

    # Channel: WhatsApp (Twilio)
    whatsapp_enabled: bool = False
    whatsapp_account_sid: str = ""
    whatsapp_auth_token: str = ""
    whatsapp_from_number: str = ""
    whatsapp_allowed_numbers: list[str] = []

    # Cost
    cost_tracking_enabled: bool = True

    # Tracing / Observability
    tracing_enabled: bool = True
    otlp_endpoint: str = "http://tempo:4317"

    # Langfuse
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://langfuse:3000"

    # Dashboard URLs (for frontend deep-links)
    grafana_base_url: str = "http://localhost:3000"
    langfuse_base_url: str = "http://localhost:3001"

    # CORS (for frontend)
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env", "env_prefix": "APP_", "extra": "ignore"}
