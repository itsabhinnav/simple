"""
Master Admin Account Provisioning

Provisions the master admin account on first boot. The pre-audit version
hardcoded ``admin/admin``, base64-encoded an unused git_token, built the
INSERT via string concatenation, and logged the password at INFO. Every one
of those is fixed here:

  * SAK-008 — credentials are generated randomly on first boot (write-once
    to ``data/local/admin-credentials.txt`` with 0600 permissions) unless
    the operator supplies them via env (``SAKURA_MASTER_ADMIN_PASSWORD`` /
    ``SAKURA_MASTER_ADMIN_SECRET_KEY``).
  * SAK-010 — the INSERT now uses parameterized placeholders.
  * SAK-021 — git_token is no longer stored (remote/Git sync was removed
    per AGENTS.md). The column is set to NULL.
  * SAK-006/008 — credentials are never logged. The credentials file is the
    single source of truth for the operator on first boot.
"""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

from werkzeug.security import generate_password_hash

from src.infrastructure.logging_config import get_logger
from src.infrastructure.dependency_injection import get_user_service, get_local_database_service

logger = get_logger(__name__)


MASTER_ADMIN_USERNAME = "admin"
MASTER_ADMIN_EMAIL = "admin@sakura.local"
MASTER_ADMIN_FIRST_NAME = "System"
MASTER_ADMIN_LAST_NAME = "Administrator"
MASTER_ADMIN_ROLE = "admin"


def _credentials_path() -> Path:
    """Where to drop the generated credentials so a human operator can see
    them exactly once. Stored next to the local data directory so it travels
    with the install, never with the source tree.
    """
    base = Path(os.environ.get("SAKURA_APP_DATA") or Path(__file__).resolve().parents[2])
    return base / "data" / "admin-credentials.txt"


def _write_credentials_file(username: str, password: str, secret_key: str) -> Path:
    target = _credentials_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# Sakura master admin credentials (generated on first boot)\n"
        "# Treat this file as a one-time secret. Delete after you have\n"
        "# stored the values in your password manager.\n"
        f"username={username}\n"
        f"password={password}\n"
        f"secret_key={secret_key}\n"
    )
    target.write_text(body, encoding="utf-8")
    try:
        # Best-effort 0600 perms. Windows ignores chmod but the directory
        # ACL on %LOCALAPPDATA% is already user-private.
        target.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return target


def _generate_or_read_secret(env_var: str) -> str:
    """Honour the operator-supplied value if present, otherwise generate one."""
    supplied = os.environ.get(env_var)
    if supplied:
        return supplied
    return secrets.token_urlsafe(24)


def provision_master_admin() -> bool:
    """Provision the master admin account on first boot (idempotent)."""
    try:
        logger.info("Checking for master admin account...")

        user_service = get_user_service()
        existing_admin = user_service.user_repository.find_by_username(MASTER_ADMIN_USERNAME)

        if existing_admin:
            logger.info(f"Master admin account '{MASTER_ADMIN_USERNAME}' already exists")
            return True

        logger.info(f"Creating master admin account '{MASTER_ADMIN_USERNAME}'...")

        password = _generate_or_read_secret("SAKURA_MASTER_ADMIN_PASSWORD")
        secret_key = _generate_or_read_secret("SAKURA_MASTER_ADMIN_SECRET_KEY")

        password_hash = generate_password_hash(password)
        secret_key_hash = generate_password_hash(secret_key)

        # SAK-010 fix: parameterized query, no string interpolation.
        local_db_service = get_local_database_service()
        query = (
            "INSERT INTO users "
            "(username, email, password_hash, secret_key_hash, git_token_encrypted, "
            " first_name, last_name, role) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            MASTER_ADMIN_USERNAME,
            MASTER_ADMIN_EMAIL,
            password_hash,
            secret_key_hash,
            None,  # SAK-021: no git_token (remote sync removed)
            MASTER_ADMIN_FIRST_NAME,
            MASTER_ADMIN_LAST_NAME,
            MASTER_ADMIN_ROLE,
        )
        result = local_db_service.execute_query(query, "default", params=params)

        if result.get("success"):
            cred_path = _write_credentials_file(MASTER_ADMIN_USERNAME, password, secret_key)
            # SAK-006/008: never log the credentials themselves. Log only the
            # path so the operator knows where to look.
            logger.info(
                f"Master admin account '{MASTER_ADMIN_USERNAME}' created. "
                f"Credentials written to {cred_path} (delete after recording)."
            )
            return True

        error_msg = result.get("error", "Unknown error")
        if "no such table" in str(error_msg).lower() or "does not exist" in str(error_msg).lower():
            logger.warning("Users table not yet created; master admin will be provisioned on next boot.")
            return False
        logger.error(f"Failed to create master admin account: {error_msg}")
        return False

    except Exception:
        logger.exception("Error provisioning master admin account")
        return False
