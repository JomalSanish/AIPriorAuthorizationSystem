"""
Secrets-management abstraction layer.

Constitution Principle P9: Secrets Abstraction Day One.
All credential access MUST go through SecretsProvider — never os.environ or
hard-coded strings at call sites. This lets a Vault/HSM backend be swapped in
without touching any other file.

Audit logging: every call to `get()` records the KEY NAME ONLY (never the
resolved value) to the operational security log, satisfying FR-040f.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Protocol, runtime_checkable

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Security-only logger — distinct from the case audit_log table (FR-040f).
# In production, route this logger to a separate handler/file.
# ---------------------------------------------------------------------------
_security_logger = logging.getLogger("pa.security.secrets")


def _log_secret_access(key: str) -> None:
    """Record that credential *key* was read. Value is NEVER logged."""
    _security_logger.info("secret_access key=%s", key)


# ---------------------------------------------------------------------------
# Protocol — swap-ready interface
# ---------------------------------------------------------------------------

@runtime_checkable
class SecretsProvider(Protocol):
    """
    Minimal interface for credential retrieval.

    Implementations must be stateless and thread-safe.
    Future providers (Vault, AWS SSM, HSM) only need to satisfy this protocol.
    """

    @abstractmethod
    def get(self, key: str) -> str:
        """
        Return the secret value for *key*.

        Raises
        ------
        KeyError
            If *key* is not found and no default was configured.
        """
        ...


# ---------------------------------------------------------------------------
# Environment-variable / .env implementation
# ---------------------------------------------------------------------------

class EnvSecretsProvider:
    """
    Secrets provider backed by environment variables (and an optional .env
    file loaded at construction time).

    This is the **only** implementation used in Phase 1. A future
    VaultSecretsProvider can be dropped in at the single injection point in
    ``config.py`` without changing any call site.
    """

    def __init__(self, dotenv_path: str | None = None) -> None:
        """
        Parameters
        ----------
        dotenv_path
            Path to a .env file to load. When *None*, python-dotenv will
            search for a .env file in the current directory and its parents
            (the default dotenv behaviour). Pass an empty string to skip
            .env loading entirely.
        """
        if dotenv_path != "":
            load_dotenv(dotenv_path=dotenv_path, override=False)

    # ------------------------------------------------------------------
    # Core access
    # ------------------------------------------------------------------

    def get(self, key: str) -> str:
        """
        Return the environment variable named *key*.

        Side-effects
        ------------
        - Logs ``key`` (never the value) to the security logger (FR-040f).

        Raises
        ------
        KeyError
            If the variable is not set.
        """
        import os  # local import — avoids module-level coupling

        _log_secret_access(key)
        value = os.environ.get(key)
        if value is None:
            raise KeyError(
                f"Required secret '{key}' is not set. "
                "Check your .env file or environment."
            )
        return value

    def get_with_default(self, key: str, default: str) -> str:
        """
        Like :meth:`get` but returns *default* when *key* is absent instead
        of raising.  Also logs access (FR-040f).
        """
        import os

        _log_secret_access(key)
        return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Module-level singleton — used by config.py
# ---------------------------------------------------------------------------

#: Default provider instance. Replace this reference to swap backends:
#:
#:   from app.core.secrets import secrets_provider
#:   secrets_provider = VaultSecretsProvider(addr=...)
secrets_provider: EnvSecretsProvider = EnvSecretsProvider()
