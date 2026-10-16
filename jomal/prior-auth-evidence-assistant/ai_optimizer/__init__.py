"""Token Optimizer runtime package exported into user workspaces by the Implement flow.

Key exports: ``optimize_text``, ``optimize_messages``, ``optimize_request`` (prompt optimizer
techniques), ``route``, ``get_model``, ``RouteDecision`` (rule-based model router), and the
LangChain v1 middlewares ``PromptOptimizationMiddleware`` / ``ModelRouterMiddleware`` (loaded
lazily, so importing this package never requires LangChain).
Feature: prompt optimizer + model router (Python runtime).
"""

from __future__ import annotations

from typing import Any

from .router import RouteDecision, get_model, load_router_config, route
from .techniques import load_techniques, optimize_messages, optimize_request, optimize_text

__all__ = [
    "ModelRouterMiddleware",
    "PromptOptimizationMiddleware",
    "RouteDecision",
    "get_model",
    "load_router_config",
    "load_techniques",
    "optimize_messages",
    "optimize_request",
    "optimize_text",
    "route",
]

__version__ = "0.1.0"

_LAZY_MIDDLEWARE = {"PromptOptimizationMiddleware", "ModelRouterMiddleware"}


def __getattr__(name: str) -> Any:
    """Import the LangChain middlewares on first access only."""
    if name in _LAZY_MIDDLEWARE:
        from . import middleware

        return getattr(middleware, name)
    raise AttributeError(f"module 'ai_optimizer' has no attribute {name!r}")
