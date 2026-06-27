"""Admin-specific endpoints"""
import os
import ipaddress
from urllib.parse import urlparse

from flask import Blueprint, request, jsonify
from typing import Dict, Any
from src.middleware.admin_middleware import is_admin, get_current_user_role, require_admin
from src.services.bulk_import_service import (
    BulkImportService,
    TARGET_CONFIG,
    HEADER_ALIASES,
    get_effective_target_config,
)
from src.services.schema_service import SchemaError
from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.dependency_injection import get_schema_service, get_database_backup_service
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


def _is_loopback_url(value: str) -> bool:
    """Return True iff ``value`` is an http(s):// URL whose host is loopback.

    Used by SAK-038 to refuse Ollama base_url redirections to anything outside
    127.0.0.0/8 / ::1 / localhost. We deliberately do not resolve the hostname
    because (a) DNS may be poisoned and (b) the restrictor's allow-list will
    reject the lookup anyway when ENABLE_NETWORK_RESTRICTIONS=strict.
    """
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _validate_provider_config(name: str, cfg: dict) -> None:
    """Validate an admin-supplied provider config (raises ValueError).

    SAK-038 fix: refuse to persist an Ollama ``base_url`` that is not a
    loopback URL unless the operator explicitly opted out via
    ``SAKURA_LLM_ALLOW_REMOTE_OLLAMA=true`` at startup.
    """
    base_url = cfg.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        return
    if name in ("ollama", "ollama-lite"):
        allow_remote = (
            os.environ.get("SAKURA_LLM_ALLOW_REMOTE_OLLAMA", "false").lower() == "true"
            and os.environ.get("ENVIRONMENT", "production").lower() != "production"
        )
        if not allow_remote and not _is_loopback_url(base_url.strip()):
            raise ValueError(
                f"Ollama base_url must be a loopback URL (e.g. http://127.0.0.1:11434); "
                f"got {base_url!r}. Set SAKURA_LLM_ALLOW_REMOTE_OLLAMA=true to opt out."
            )
    if name in ("openai", "anthropic"):
        from src.interfaces.llm_provider import remote_providers_allowed

        if not remote_providers_allowed():
            raise ValueError(
                f"External LLM provider {name!r} is disabled. "
                "Set parsing.vlm.allow_remote_providers: true in config.yaml "
                "or SAKURA_LLM_ALLOW_EXTERNAL=true to enable."
            )


# Top-level config.yaml sections that the admin UI is allowed to read/write.
# Keep this allow-list narrow: secrets (JWT keys, DB passwords) live in env
# vars, and ``database`` paths must not be hot-swapped at runtime.
EDITABLE_CONFIG_SECTIONS = {
    "test_case_dropdowns",
    "features",
    "authentication",
    "server",
    "logging",
    "parsing",
    "bulk_import",
    "network",
}

# Sections we expose read-only for transparency (so the admin can audit
# what the backend is actually using) but refuse to mutate via the API.
READ_ONLY_SECTIONS = {
    "database",
    "environment",
}


class AdminController:
    """Controller for admin-specific endpoints"""

    def __init__(self):
        self.bulk_import_service = BulkImportService()
    
    def check_admin_status(self) -> Dict[str, Any]:
        """Check if current user is admin"""
        try:
            is_user_admin = is_admin()
            role = get_current_user_role()
            
            return jsonify({
                "success": True,
                "data": {
                    "is_admin": is_user_admin,
                    "role": role or "user"
                }
            }), 200
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to check admin status",
                "message": str(e)
            }), 500

    @require_admin
    def bulk_import(self) -> Dict[str, Any]:
        """Import entity records from one or more Excel workbooks."""
        try:
            files = request.files.getlist('files') or request.files.getlist('file')
            if not files:
                return jsonify({
                    "success": False,
                    "error": "No files uploaded",
                    "message": "Upload at least one Excel workbook"
                }), 400

            target = (request.form.get('target') or 'auto').strip()
            created_by = getattr(request, "current_username", None)
            try:
                from flask import g
                created_by = g.get('current_username') or created_by or 'system'
            except Exception:
                created_by = created_by or 'system'

            result = self.bulk_import_service.import_files(files, target, created_by)
            totals = result["totals"]
            return jsonify({
                "success": totals["failed"] == 0 or totals["created"] > 0 or totals["skipped"] > 0,
                "message": "Bulk import completed",
                "data": result
            }), 200
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid import request",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.error(f"Bulk import failed: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Bulk import failed",
                "message": str(e)
            }), 500


    # ------------------------------------------------------------------
    # Settings / Configuration management (visual editor for config.yaml)
    # ------------------------------------------------------------------
    @require_admin
    def get_settings(self) -> Dict[str, Any]:
        """GET /api/admin/settings — return editable + read-only config sections.

        Shape::

            {
              "file_path": "<absolute path to config.yaml>",
              "editable_sections": [...],
              "read_only_sections": [...],
              "sections": {
                  "<section_name>": <current value (deep-copied)>,
                  ...
              }
            }
        """
        try:
            mgr = get_config_manager()
            sections: Dict[str, Any] = {}
            for name in EDITABLE_CONFIG_SECTIONS | READ_ONLY_SECTIONS:
                value = mgr.get_config(name, None)
                sections[name] = value if value is not None else {}
            return jsonify({
                "success": True,
                "data": {
                    "file_path": mgr.get_file_config_path(),
                    "editable_sections": sorted(EDITABLE_CONFIG_SECTIONS),
                    "read_only_sections": sorted(READ_ONLY_SECTIONS),
                    "sections": sections,
                },
            }), 200
        except Exception as e:
            logger.error(f"Failed to load admin settings: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to load settings",
                "message": str(e),
            }), 500

    @require_admin
    def update_section(self, section: str) -> Dict[str, Any]:
        """PUT /api/admin/settings/<section> — overwrite a single top-level
        section in ``config.yaml``. Body: ``{"value": <new section value>}``.
        """
        try:
            if section not in EDITABLE_CONFIG_SECTIONS:
                return jsonify({
                    "success": False,
                    "error": "Section not editable",
                    "message": f"'{section}' cannot be edited via the admin API",
                }), 400
            payload = request.get_json(silent=True) or {}
            if "value" not in payload:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Body must include a 'value' field",
                }), 400
            value = payload["value"]
            ok = get_config_manager().set_section(section, value)
            if not ok:
                return jsonify({
                    "success": False,
                    "error": "Save failed",
                    "message": "Could not persist changes to config.yaml",
                }), 500
            updated = get_config_manager().get_config(section, value)
            return jsonify({
                "success": True,
                "message": f"Section '{section}' updated",
                "data": {"section": section, "value": updated},
            }), 200
        except Exception as e:
            logger.error(f"Failed to update section {section}: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to update section",
                "message": str(e),
            }), 500

    @require_admin
    def get_llm_config(self) -> Dict[str, Any]:
        """GET /api/admin/llm — current VLM/LLM provider configuration.

        Aggregates three views so the admin UI can render a single page:
          * ``providers``: per-provider connection settings sourced from
            ``parsing.vlm.providers.*`` in config.yaml.
          * ``registered``: providers that registered themselves at boot
            (``get_vlm_registry().list_providers()``) — these are the
            valid choices for ``default``.
          * ``default``: currently active default provider.
          * ``api_keys``: which API key env vars are populated (boolean
            only — values are never sent to the client).
        """
        try:
            from src.interfaces.llm_provider import get_vlm_registry
            import os
            mgr = get_config_manager()
            providers_cfg = mgr.get_config("parsing.vlm.providers", {}) or {}
            registry = get_vlm_registry()
            api_key_envs = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
            }
            api_keys: Dict[str, Dict[str, Any]] = {}
            for prov, env in api_key_envs.items():
                api_keys[prov] = {"env": env, "set": bool(os.environ.get(env))}
            return jsonify({
                "success": True,
                "data": {
                    "default": mgr.get_config("parsing.vlm.default_provider", "ollama"),
                    "registered": registry.list_providers(),
                    "providers": providers_cfg,
                    "api_keys": api_keys,
                    "schema": {
                        "ollama": ["base_url", "model", "lite_model"],
                        "openai": ["base_url", "model"],
                        "anthropic": ["base_url", "model"],
                    },
                },
            }), 200
        except Exception:
            logger.exception("Failed to load LLM config")
            return jsonify({
                "success": False,
                "error": "Failed to load LLM config",
                "message": "An internal error occurred",
            }), 500

    @require_admin
    def update_llm_config(self) -> Dict[str, Any]:
        """PUT /api/admin/llm — update default + per-provider settings.

        Body shape::

            {
              "default": "ollama",
              "providers": {
                 "ollama": {"base_url": "...", "model": "...", "lite_model": "..."},
                 "openai": {"base_url": "...", "model": "..."},
                 "anthropic": {"base_url": "...", "model": "..."}
              }
            }

        Any provider entry omitted from the body is left untouched in
        config.yaml (the deep-merge writer in ConfigurationManager will
        leave sibling keys alone). The running VLM registry's default is
        also swapped in-process so the next parsing request picks up the
        change without a server restart.
        """
        try:
            payload = request.get_json(silent=True) or {}
            mgr = get_config_manager()
            parsing = dict(mgr.get_config("parsing", {}) or {})
            vlm = dict(parsing.get("vlm") or {})
            providers = dict(vlm.get("providers") or {})

            new_default = payload.get("default")
            if isinstance(new_default, str) and new_default.strip():
                vlm["default_provider"] = new_default.strip().lower()

            incoming_providers = payload.get("providers") or {}
            if isinstance(incoming_providers, dict):
                for name, cfg in incoming_providers.items():
                    if not isinstance(cfg, dict):
                        continue
                    # SAK-038: refuse non-loopback Ollama URLs and reject
                    # external providers unless explicitly enabled.
                    _validate_provider_config(name.lower(), cfg)
                    existing = dict(providers.get(name) or {})
                    for key, value in cfg.items():
                        if value is None:
                            continue
                        existing[key] = value
                    providers[name] = existing

            vlm["providers"] = providers
            parsing["vlm"] = vlm
            ok = mgr.set_section("parsing", parsing)
            if not ok:
                return jsonify({
                    "success": False,
                    "error": "Save failed",
                    "message": "Could not persist LLM config to config.yaml",
                }), 500

            # Apply the new default to the live registry singleton so the
            # next parsing call uses it without requiring a restart.
            try:
                from src.interfaces.llm_provider import get_vlm_registry, VLMProviderError
                registry = get_vlm_registry()
                desired_default = vlm.get("default_provider")
                if desired_default and registry.has(desired_default):
                    registry.set_default(desired_default)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Could not apply new default VLM in-process: {exc}")

            return jsonify({
                "success": True,
                "message": "LLM configuration saved",
                "data": {
                    "default": vlm.get("default_provider"),
                    "providers": vlm.get("providers"),
                },
            }), 200
        except ValueError as exc:
            # Validation error from _validate_provider_config — safe to echo
            # to the admin client because it does not contain stack data.
            return jsonify({
                "success": False,
                "error": "Invalid LLM configuration",
                "message": str(exc),
            }), 400
        except Exception:
            logger.exception("Failed to save LLM config")
            return jsonify({
                "success": False,
                "error": "Failed to save LLM config",
                "message": "An internal error occurred",
            }), 500

    @require_admin
    def test_llm_provider(self, name: str) -> Dict[str, Any]:
        """POST /api/admin/llm/test/<name> — best-effort connectivity check.

        For Ollama we hit ``GET /api/tags`` on the configured ``base_url``.
        For OpenAI / Anthropic we only verify the API-key env var is set
        (no outbound call) since the production network restrictor blocks
        external hosts by design.
        """
        try:
            name_key = (name or "").lower().strip()
            mgr = get_config_manager()
            providers_cfg = mgr.get_config("parsing.vlm.providers", {}) or {}
            cfg = providers_cfg.get(name_key) or {}
            if name_key == "ollama" or name_key == "ollama-lite":
                import httpx
                base = cfg.get("base_url") or "http://localhost:11434"
                try:
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.get(f"{base.rstrip('/')}/api/tags")
                    if resp.status_code != 200:
                        return jsonify({
                            "success": False,
                            "error": "Provider unreachable",
                            "message": f"GET /api/tags returned HTTP {resp.status_code}",
                        }), 200
                    body = resp.json() if resp.text else {}
                    models = [m.get("name") for m in (body.get("models") or []) if isinstance(m, dict)]
                    return jsonify({
                        "success": True,
                        "message": f"Ollama reachable at {base}",
                        "data": {"models": models, "configured_model": cfg.get("model")},
                    }), 200
                except Exception as exc:
                    return jsonify({
                        "success": False,
                        "error": "Provider unreachable",
                        "message": str(exc),
                    }), 200
            elif name_key in ("openai", "anthropic"):
                import os
                env_var = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}[name_key]
                set_ok = bool(os.environ.get(env_var))
                return jsonify({
                    "success": set_ok,
                    "message": f"{env_var} {'is set' if set_ok else 'is NOT set'}",
                    "data": {"env_var": env_var, "set": set_ok, "model": cfg.get("model")},
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Unknown provider",
                    "message": f"No connectivity check implemented for '{name}'",
                }), 400
        except Exception:
            logger.exception(f"LLM test failed for {name}")
            return jsonify({
                "success": False,
                "error": "LLM test failed",
                "message": "An internal error occurred",
            }), 500

    # ------------------------------------------------------------------
    # Schema management — runtime DDL on the local SQLite database.
    # ------------------------------------------------------------------
    def _current_admin_username(self) -> str:
        try:
            from flask import g
            return g.get('current_username') or 'admin'
        except Exception:
            return 'admin'

    @require_admin
    def list_schema_tables(self) -> Dict[str, Any]:
        try:
            tables = get_schema_service().list_tables()
            return jsonify({"success": True, "data": {"tables": tables}}), 200
        except Exception as e:
            logger.exception("Failed to list tables")
            return jsonify({"success": False, "error": "Failed to list tables", "message": str(e)}), 500

    @require_admin
    def get_schema_table(self, name: str) -> Dict[str, Any]:
        try:
            info = get_schema_service().get_table(name)
            return jsonify({"success": True, "data": info}), 200
        except SchemaError as e:
            return jsonify({"success": False, "error": "Invalid table", "message": str(e)}), 400
        except Exception as e:
            logger.exception("Failed to inspect table %s", name)
            return jsonify({"success": False, "error": "Failed to inspect table", "message": str(e)}), 500

    @require_admin
    def create_schema_table(self) -> Dict[str, Any]:
        try:
            payload = request.get_json(silent=True) or {}
            name = payload.get("name")
            columns = payload.get("columns") or []
            if not name:
                raise SchemaError("Body must include a 'name' field")
            info = get_schema_service().create_table(
                name, columns, applied_by=self._current_admin_username(),
            )
            return jsonify({
                "success": True,
                "message": f"Table '{name}' created",
                "data": info,
                "requires_reload": True,
            }), 201
        except SchemaError as e:
            return jsonify({"success": False, "error": "Invalid request", "message": str(e)}), 400
        except Exception as e:
            logger.exception("create_table failed")
            return jsonify({"success": False, "error": "Failed to create table", "message": str(e)}), 500

    @require_admin
    def drop_schema_table(self, name: str) -> Dict[str, Any]:
        try:
            result = get_schema_service().drop_table(
                name, applied_by=self._current_admin_username(),
            )
            return jsonify({
                "success": True,
                "message": f"Table '{name}' dropped",
                "data": result,
                "requires_reload": True,
            }), 200
        except SchemaError as e:
            return jsonify({"success": False, "error": "Invalid request", "message": str(e)}), 400
        except Exception as e:
            logger.exception("drop_table failed")
            return jsonify({"success": False, "error": "Failed to drop table", "message": str(e)}), 500

    @require_admin
    def add_schema_column(self, table: str) -> Dict[str, Any]:
        try:
            payload = request.get_json(silent=True) or {}
            info = get_schema_service().add_column(
                table, payload, applied_by=self._current_admin_username(),
            )
            return jsonify({
                "success": True,
                "message": f"Column '{payload.get('name')}' added to '{table}'",
                "data": info,
                "requires_reload": True,
            }), 201
        except SchemaError as e:
            return jsonify({"success": False, "error": "Invalid request", "message": str(e)}), 400
        except Exception as e:
            logger.exception("add_column failed")
            return jsonify({"success": False, "error": "Failed to add column", "message": str(e)}), 500

    @require_admin
    def update_schema_column(self, table: str, column: str) -> Dict[str, Any]:
        try:
            payload = request.get_json(silent=True) or {}
            info = get_schema_service().change_column(
                table=table,
                column=column,
                new_name=payload.get("new_name"),
                new_type=payload.get("new_type"),
                nullable=payload.get("nullable"),
                default=payload.get("default"),
                applied_by=self._current_admin_username(),
            )
            return jsonify({
                "success": True,
                "message": f"Column '{column}' on '{table}' updated",
                "data": info,
                "requires_reload": True,
            }), 200
        except SchemaError as e:
            return jsonify({"success": False, "error": "Invalid request", "message": str(e)}), 400
        except Exception as e:
            logger.exception("change_column failed")
            return jsonify({"success": False, "error": "Failed to update column", "message": str(e)}), 500

    @require_admin
    def drop_schema_column(self, table: str, column: str) -> Dict[str, Any]:
        try:
            info = get_schema_service().drop_column(
                table, column, applied_by=self._current_admin_username(),
            )
            return jsonify({
                "success": True,
                "message": f"Column '{column}' dropped from '{table}'",
                "data": info,
                "requires_reload": True,
            }), 200
        except SchemaError as e:
            return jsonify({"success": False, "error": "Invalid request", "message": str(e)}), 400
        except Exception as e:
            logger.exception("drop_column failed")
            return jsonify({"success": False, "error": "Failed to drop column", "message": str(e)}), 500

    @require_admin
    def list_schema_migrations(self) -> Dict[str, Any]:
        try:
            migrations = get_schema_service().list_migrations()
            backups = get_schema_service().list_backups()
            return jsonify({"success": True, "data": {
                "migrations": migrations,
                "backups": backups,
            }}), 200
        except Exception as e:
            logger.exception("Failed to list migrations")
            return jsonify({"success": False, "error": "Failed to list migrations", "message": str(e)}), 500

    @require_admin
    def create_schema_backup(self) -> Dict[str, Any]:
        try:
            result = get_schema_service().create_backup()
            return jsonify({
                "success": True,
                "message": "Backup created",
                "data": result,
            }), 201
        except SchemaError as e:
            return jsonify({"success": False, "error": "Backup failed", "message": str(e)}), 400
        except Exception as e:
            logger.exception("create_backup failed")
            return jsonify({"success": False, "error": "Backup failed", "message": str(e)}), 500

    @require_admin
    def get_db_status(self) -> Dict[str, Any]:
        try:
            status = get_database_backup_service().get_status()
            try:
                from src.infrastructure.dependency_injection import get_hybrid_database_service
                db = get_hybrid_database_service().local_db.execute_query(
                    "SELECT version, name, applied_at FROM app_migrations ORDER BY version",
                    "default",
                )
                if db.get("success"):
                    status["app_migrations"] = db.get("data") or []
                else:
                    status["app_migrations"] = []
            except Exception:
                status["app_migrations"] = []
            return jsonify({"success": True, "data": status}), 200
        except Exception as e:
            logger.exception("get_db_status failed")
            return jsonify({"success": False, "error": "Failed to load database status", "message": str(e)}), 500

    @require_admin
    def restore_schema_backup(self) -> Dict[str, Any]:
        try:
            data = request.get_json() or {}
            if not data.get("confirm"):
                return jsonify({
                    "success": False,
                    "error": "Confirmation required",
                    "message": "Set confirm=true in the request body to restore",
                }), 400

            backup_name = data.get("backup_name") or data.get("name")
            if not backup_name:
                return jsonify({
                    "success": False,
                    "error": "Missing backup_name",
                }), 400

            svc = get_database_backup_service()
            path = svc.resolve_backup_path(str(backup_name))
            if path is None:
                return jsonify({
                    "success": False,
                    "error": "Backup not found",
                    "message": f"No verified backup named {backup_name!r}",
                }), 404

            pre = svc.create_backup(reason="pre_admin_restore")
            if not svc.restore_from(path):
                return jsonify({
                    "success": False,
                    "error": "Restore failed",
                }), 500

            return jsonify({
                "success": True,
                "message": f"Database restored from {backup_name}",
                "data": {
                    "restored_from": str(path),
                    "pre_restore_snapshot": str(pre) if pre else None,
                },
            }), 200
        except Exception as e:
            logger.exception("restore_schema_backup failed")
            return jsonify({"success": False, "error": "Restore failed", "message": str(e)}), 500

    @require_admin
    def get_import_schema(self) -> Dict[str, Any]:
        """GET /api/admin/import-schema — expose the bulk import contract
        (canonical fields per entity + alias dictionary) so the admin UI
        can render mapping configuration."""
        try:
            targets: Dict[str, Any] = {}
            for name, base in TARGET_CONFIG.items():
                effective = get_effective_target_config(name) or base
                targets[name] = {
                    "table": base.get("table"),
                    "id_field": base.get("id_field"),
                    "prefix": base.get("prefix"),
                    "required": effective.get("required", []),
                    "fields": effective.get("fields", []),
                    "default_required": base.get("required", []),
                    "default_fields": base.get("fields", []),
                }
            return jsonify({
                "success": True,
                "data": {
                    "targets": targets,
                    "header_aliases": HEADER_ALIASES,
                },
            }), 200
        except Exception as e:
            logger.error(f"Failed to load import schema: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to load import schema",
                "message": str(e),
            }), 500

    @require_admin
    def get_observability_summary(self) -> Dict[str, Any]:
        """GET /api/admin/observability — local request metrics (no external telemetry)."""
        try:
            from src.services.observability_service import (
                get_observability_service,
                observability_enabled,
            )

            if not observability_enabled():
                return jsonify({
                    "success": False,
                    "error": "Observability disabled",
                    "message": "Set SAKURA_ENABLE_OBSERVABILITY=true to enable",
                }), 503

            return jsonify({
                "success": True,
                "data": get_observability_service().summary(),
            }), 200
        except Exception as e:
            logger.exception("get_observability_summary failed")
            return jsonify({"success": False, "error": "Failed to load observability", "message": str(e)}), 500

    @require_admin
    def get_egress_log(self) -> Dict[str, Any]:
        """GET /api/admin/network/egress-log — socket-level connection audit trail."""
        try:
            from src.infrastructure.network_restrictor import get_connection_log

            return jsonify({
                "success": True,
                "data": get_connection_log()[-500:],
            }), 200
        except Exception as e:
            logger.exception("get_egress_log failed")
            return jsonify({"success": False, "error": "Failed to load egress log", "message": str(e)}), 500


def create_admin_blueprint() -> Blueprint:
    """Create and configure admin blueprint"""
    admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')
    controller = AdminController()
    
    # Register routes
    admin_bp.route('/status', methods=['GET'])(controller.check_admin_status)
    admin_bp.route('/bulk-import', methods=['POST'])(controller.bulk_import)
    admin_bp.route('/settings', methods=['GET'])(controller.get_settings)
    admin_bp.route('/settings/<section>', methods=['PUT'])(controller.update_section)
    admin_bp.route('/import-schema', methods=['GET'])(controller.get_import_schema)
    admin_bp.route('/llm', methods=['GET'])(controller.get_llm_config)
    admin_bp.route('/llm', methods=['PUT'])(controller.update_llm_config)
    admin_bp.route('/llm/test/<name>', methods=['POST'])(controller.test_llm_provider)

    # Database schema management (DDL on the local SQLite DB)
    admin_bp.route('/schema/tables', methods=['GET'])(controller.list_schema_tables)
    admin_bp.route('/schema/tables', methods=['POST'])(controller.create_schema_table)
    admin_bp.route('/schema/tables/<name>', methods=['GET'])(controller.get_schema_table)
    admin_bp.route('/schema/tables/<name>', methods=['DELETE'])(controller.drop_schema_table)
    admin_bp.route('/schema/tables/<table>/columns', methods=['POST'])(controller.add_schema_column)
    admin_bp.route('/schema/tables/<table>/columns/<column>', methods=['PUT'])(controller.update_schema_column)
    admin_bp.route('/schema/tables/<table>/columns/<column>', methods=['DELETE'])(controller.drop_schema_column)
    admin_bp.route('/schema/migrations', methods=['GET'])(controller.list_schema_migrations)
    admin_bp.route('/schema/backup', methods=['POST'])(controller.create_schema_backup)
    admin_bp.route('/schema/restore', methods=['POST'])(controller.restore_schema_backup)
    admin_bp.route('/db/status', methods=['GET'])(controller.get_db_status)
    admin_bp.route('/observability', methods=['GET'])(controller.get_observability_summary)
    admin_bp.route('/network/egress-log', methods=['GET'])(controller.get_egress_log)

    return admin_bp










