# -*- coding: utf-8 -*-
"""Configuration Manager for Antigravity OpenAI Gateway."""

import os
from dataclasses import dataclass, field
from pathlib import Path
import shutil
from typing import Dict, List, Optional
import yaml


def find_agy_binary() -> str:
    """Find installed agy.exe path."""
    which_path = shutil.which("agy")
    if which_path:
        return which_path

    # Check common user local app data paths
    user_home = Path.home()
    candidates = [
        user_home / "AppData" / "Local" / "agy" / "bin" / "agy.exe",
        user_home / "AppData" / "Local" / "antigravity" / "bin" / "agy.exe",
        user_home / ".gemini" / "bin" / "agy.exe",
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)

    return "agy"


@dataclass
class GatewayConfig:
    host: str = "127.0.0.1"
    port: int = 8045
    api_key: str = ""  # If set, requires Bearer <api_key>; if empty, allows any or no key
    cli_command: str = field(default_factory=find_agy_binary)
    proxy: str = field(default_factory=lambda: os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or "")
    default_model: str = "gemini-3.8-flash-low"
    timeout: float = 120.0
    max_concurrency: int = 4
    stream_chunk_size: int = 8

    # Model aliases mapped to official Antigravity CLI model identifiers
    model_aliases: Dict[str, str] = field(default_factory=lambda: {
        "default": "gemini-3.8-flash-low",
        "gpt-4": "claude-sonnet-4-6",
        "gpt-4o": "gemini-3.8-flash-medium",
        "gpt-4o-mini": "gemini-3.8-flash-low",
        "gpt-3.5-turbo": "gemini-3.8-flash-low",
        "claude-3-5-sonnet": "claude-sonnet-4-6",
        "claude-3-opus": "claude-opus-4-6-thinking",
        "gemini-pro": "gemini-3.8-flash-medium",
        "gemini-flash": "gemini-3.8-flash-low",
        "gemini-2.5-pro": "gemini-3.8-flash-medium",
        "gemini-3.8-flash": "gemini-3.8-flash-low",
        "gemini-3.8-flash-low": "gemini-3.8-flash-low",
        "gemini-3.8-flash-medium": "gemini-3.8-flash-medium",
        "gemini-3.8-flash-high": "gemini-3.8-flash-high",
        "claude-sonnet-4-6": "claude-sonnet-4-6",
        "claude-opus-4-6-thinking": "claude-opus-4-6-thinking",
        "gpt-oss-120b-medium": "gpt-oss-120b-medium",
    })

    # Available models list
    available_models: List[str] = field(default_factory=lambda: [
        "gemini-3.8-flash-low",
        "gemini-3.8-flash-medium",
        "gemini-3.8-flash-high",
        "claude-sonnet-4-6",
        "claude-opus-4-6-thinking",
        "gpt-oss-120b-medium",
    ])

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "GatewayConfig":
        """Load configuration from YAML file or environment variables."""
        cfg = cls()

        target = Path(config_path) if config_path else Path("config.yaml")
        if not target.exists():
            target = Path(__file__).resolve().parent.parent / "config.yaml"

        if target.exists():
            try:
                data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
                if "host" in data:
                    cfg.host = str(data["host"])
                if "port" in data:
                    cfg.port = int(data["port"])
                if "api_key" in data:
                    cfg.api_key = str(data["api_key"])
                if "cli_command" in data:
                    cfg.cli_command = str(data["cli_command"])
                if "proxy" in data:
                    cfg.proxy = str(data["proxy"])
                if "default_model" in data:
                    cfg.default_model = str(data["default_model"])
                if "timeout" in data:
                    cfg.timeout = float(data["timeout"])
                if "max_concurrency" in data:
                    cfg.max_concurrency = int(data["max_concurrency"])
                if "model_aliases" in data:
                    cfg.model_aliases.update(data["model_aliases"])
            except Exception as e:
                print(f"[GatewayConfig] Warning: failed to parse config.yaml: {e}")

        # Override via environment variables
        env_host = os.getenv("AGY_GATEWAY_HOST")
        if env_host:
            cfg.host = env_host
        env_port = os.getenv("AGY_GATEWAY_PORT")
        if env_port:
            cfg.port = int(env_port)
        env_key = os.getenv("AGY_GATEWAY_API_KEY")
        if env_key:
            cfg.api_key = env_key
        env_proxy = os.getenv("AGY_GATEWAY_PROXY") or os.getenv("AGY_PROXY")
        if env_proxy:
            cfg.proxy = env_proxy

        return cfg
