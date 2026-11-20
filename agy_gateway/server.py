# -*- coding: utf-8 -*-
"""FastAPI Server exposing OpenAI-compatible endpoints for Google Antigravity."""

import logging
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agy_gateway.agy_executor import AgyExecutor
from agy_gateway.config import GatewayConfig
from agy_gateway.protocol import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelCard,
    ModelListResponse,
)

logger = logging.getLogger("agy_gateway.server")

security = HTTPBearer(auto_error=False)


def create_app(config: Optional[GatewayConfig] = None) -> FastAPI:
    """Create and configure FastAPI application."""
    cfg = config or GatewayConfig.load()
    executor = AgyExecutor(cfg)

    app = FastAPI(
        title="Antigravity OpenAI Gateway",
        description="Legitimate OpenAI-compatible API Gateway powered by official Google Antigravity CLI",
        version="1.0.0",
    )

    # Enable CORS for browser-based WebUIs (NextChat, Chatbox, etc.)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def verify_auth(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)):
        """Check optional API key authentication."""
        if not cfg.api_key:
            return  # No API key required
        if not credentials or credentials.credentials != cfg.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "message": "Invalid or missing API key in Authorization header",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Internal server error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "message": str(exc),
                    "type": "server_error",
                    "param": None,
                    "code": "internal_error",
                }
            },
        )

    @app.get("/", tags=["Health"])
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {
            "status": "ok",
            "service": "antigravity-openai-gateway",
            "cli_command": cfg.cli_command,
            "default_model": cfg.default_model,
        }

    @app.get("/v1/models", response_model=ModelListResponse, tags=["Models"])
    @app.get("/models", response_model=ModelListResponse, tags=["Models"])
    async def list_models(auth: None = Depends(verify_auth)):
        models = []
        # Return both available models and configured aliases
        all_model_names = sorted(set(cfg.available_models + list(cfg.model_aliases.keys())))
        for m in all_model_names:
            models.append(ModelCard(id=m))
        return ModelListResponse(object="list", data=models)

    @app.get("/v1/models/{model_id}", response_model=ModelCard, tags=["Models"])
    @app.get("/models/{model_id}", response_model=ModelCard, tags=["Models"])
    async def get_model(model_id: str, auth: None = Depends(verify_auth)):
        return ModelCard(id=model_id)

    @app.post("/v1/chat/completions", tags=["Chat"])
    @app.post("/chat/completions", tags=["Chat"])
    async def chat_completions(
        request: ChatCompletionRequest, auth: None = Depends(verify_auth)
    ):
        logger.info(
            f"Received chat completion request: model={request.model}, stream={request.stream}, turns={len(request.messages)}"
        )

        if request.stream:
            return StreamingResponse(
                executor.execute_stream(request),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            resp: ChatCompletionResponse = await executor.execute_chat(request)
            return resp

    return app
