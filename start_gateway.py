# -*- coding: utf-8 -*-
"""Startup Script for Antigravity OpenAI Gateway.

Launches the FastAPI server exposing standard OpenAI v1 endpoints
backed by official Google Antigravity CLI.
"""

import argparse
import logging
import sys
from pathlib import Path
import uvicorn

from agy_gateway.config import GatewayConfig
from agy_gateway.server import create_app


def parse_args():
    parser = argparse.ArgumentParser(
        description="Antigravity OpenAI-Compatible Gateway"
    )
    parser.add_argument(
        "--host", type=str, default=None, help="Host to bind (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=None, help="Port to bind (default: 8045)"
    )
    parser.add_argument(
        "--api-key", type=str, default=None, help="Optional API key for Bearer auth"
    )
    parser.add_argument(
        "--model", type=str, default=None, help="Default model identifier"
    )
    parser.add_argument(
        "--cli-path", type=str, default=None, help="Path to agy.exe binary"
    )
    parser.add_argument(
        "--proxy", type=str, default=None, help="Proxy URL for agy (e.g. http://127.0.0.1:10809)"
    )
    parser.add_argument(
        "--config", type=str, default=None, help="Path to custom config.yaml"
    )
    return parser.parse_args()


def print_banner(cfg: GatewayConfig):
    url = f"http://{cfg.host}:{cfg.port}/v1"
    border = "=" * 62
    print(border)
    print("   🌌 Antigravity OpenAI API Gateway (Google Antigravity Pro)")
    print(border)
    print(f" • API Base URL   : {url}")
    print(f" • Endpoints      : {url}/chat/completions")
    print(f"                    {url}/models")
    print(f" • Default Model  : {cfg.default_model}")
    print(f" • Antigravity CLI: {cfg.cli_command}")
    print(f" • Outbound Proxy : {cfg.proxy or '(Direct / None)'}")
    print(f" • Max Concurrency: {cfg.max_concurrency}")
    print(f" • Auth Key       : {'(Enabled)' if cfg.api_key else '(None / Open)'}")
    print(border)
    print(" 💡 Client Configuration Example:")
    print("    - Base URL    : " + url)
    print("    - API Key     : " + (cfg.api_key or "sk-antigravity-local"))
    print("    - Model       : gpt-4o / gemini-3.8-flash-low / claude-sonnet-4-6")
    print(border)
    sys.stdout.flush()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    args = parse_args()
    cfg = GatewayConfig.load(args.config)

    if args.host:
        cfg.host = args.host
    if args.port:
        cfg.port = args.port
    if args.api_key is not None:
        cfg.api_key = args.api_key
    if args.model:
        cfg.default_model = args.model
    if args.cli_path:
        cfg.cli_command = args.cli_path
    if args.proxy:
        cfg.proxy = args.proxy

    print_banner(cfg)

    app = create_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
