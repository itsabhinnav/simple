import json
from flask import Blueprint, request, jsonify
from typing import Dict, Any
from src.services.test_case_service import ITestCaseService
from src.services.bulk_import_service import BulkImportService
from src.services.test_automation_service import TestAutomationService
from src.services.test_suite_preset_service import TestSuitePresetService
from src.infrastructure.dependency_injection import get_hybrid_database_service
from src.schemas.test_case_schema import TestCaseCreateSchema
from src.schemas.api_schema import ErrorResponseSchema, SuccessResponseSchema
from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class TestCaseController:
    """Controller for test case-related API endpoints"""
    
    def __init__(self, test_case_service: ITestCaseService):
        self.test_case_service = test_case_service
        # Reused for Excel preview + bulk import. BulkImportService is cheap
        # to instantiate (just resolves the hybrid DB service).
        self.bulk_import_service = BulkImportService()
        self.test_automation_service = TestAutomationService()
        self.test_suite_preset_service = TestSuitePresetService(get_hybrid_database_service())
    
    def get_all_test_cases(self) -> Dict[str, Any]:
        """GET /api/test-cases - Get all test cases"""
        try:
            test_cases = self.test_case_service.get_all_test_cases()
            return jsonify({
                "success": True,
                "message": "Test cases retrieved successfully",
                "data": test_cases,
                "count": len(test_cases)
            }), 200
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to retrieve test cases",
                "message": str(e)
            }), 500
    
    def get_test_case_by_id(self, test_case_id: str) -> Dict[str, Any]:
        """GET /api/test-cases/<test_case_id> - Get test case by ID"""
        try:
            test_case = self.test_case_service.get_test_case_by_id(test_case_id)
            if test_case:
                return jsonify({
                    "success": True,
                    "message": "Test case retrieved successfully",
                    "data": test_case
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Test case not found",
                    "message": f"Test case with ID {test_case_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to retrieve test case",
                "message": str(e)
            }), 500
    
    def get_test_cases_by_feature(self) -> Dict[str, Any]:
        """GET /api/test-cases/feature/<feature> - Get test cases by feature"""
        try:
            feature = request.args.get('feature')
            if not feature:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Feature parameter is required"
                }), 400
            
            test_cases = self.test_case_service.get_test_cases_by_feature(feature)
            return jsonify({
                "success": True,
                "message": f"Test cases for feature '{feature}' retrieved successfully",
                "data": test_cases,
                "count": len(test_cases)
            }), 200
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to retrieve test cases",
                "message": str(e)
            }), 500
    
    def create_test_case(self) -> Dict[str, Any]:
        """POST /api/test-cases - Create a new test case"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            # Validate data using schema
            test_case_data = TestCaseCreateSchema(**data)
            test_case = self.test_case_service.create_test_case(test_case_data)
            
            return jsonify({
                "success": True,
                "message": "Test case created successfully",
                "data": test_case
            }), 201
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to create test case",
                "message": str(e)
            }), 500
    
    def update_test_case(self, test_case_id: str) -> Dict[str, Any]:
        """PUT /api/test-cases/<test_case_id> - Update test case"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            test_case = self.test_case_service.update_test_case(test_case_id, data)
            
            if test_case:
                return jsonify({
                    "success": True,
                    "message": "Test case updated successfully",
                    "data": test_case
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Test case not found",
                    "message": f"Test case with ID {test_case_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to update test case",
                "message": str(e)
            }), 500
    
    # ------------------------------------------------------------------
    # Excel bulk-import endpoints. Open to any authenticated caller (auth is
    # globally bypassed in workspace mode) — this is intentionally NOT
    # @require_admin so testers can drag-and-drop their AAOS spreadsheets.
    # ------------------------------------------------------------------
    def get_dropdowns(self) -> Dict[str, Any]:
        """GET /api/test-cases/dropdowns — return configurable picker options.

        The frontend calls this once on page load to populate every
        single-select / multi-select on the create + detail screens. All
        option lists come from ``config.yaml > test_case_dropdowns``;
        change values there to extend the pickers without redeploying the
        client.
        """
        try:
            data = get_config_manager().get_test_case_dropdowns()
            return jsonify({
                "success": True,
                "message": "Dropdown configuration retrieved",
                "data": data,
            }), 200
        except Exception as e:
            logger.error(f"Failed to load test-case dropdowns: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to load dropdowns",
                "message": str(e),
            }), 500

    def get_import_fields(self) -> Dict[str, Any]:
        """GET /api/test-cases/import/fields - list canonical fields for mapping UI."""
        try:
            data = self.bulk_import_service.get_target_fields("test_cases")
            return jsonify({"success": True, "data": data}), 200
        except Exception as e:
            logger.error(f"Failed to get import fields: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to get import fields",
                "message": str(e),
            }), 500

    def preview_import(self) -> Dict[str, Any]:
        """POST /api/test-cases/import/preview - parse one xlsx and return headers + samples without inserting."""
        try:
            file_storage = request.files.get("file") or (request.files.getlist("files") or [None])[0]
            if not file_storage:
                return jsonify({
                    "success": False,
                    "error": "No file uploaded",
                    "message": "Upload an Excel workbook (.xlsx or .xlsm)",
                }), 400
            sample_rows = int(request.form.get("sample_rows", 5))
            data = self.bulk_import_service.preview_file(file_storage, "test_cases", sample_rows=sample_rows)
            return jsonify({"success": True, "data": data}), 200
        except ValueError as e:
            return jsonify({"success": False, "error": "Invalid request", "message": str(e)}), 400
        except Exception as e:
            logger.error(f"Test-case import preview failed: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Preview failed",
                "message": str(e),
            }), 500

    def import_test_cases(self) -> Dict[str, Any]:
        """POST /api/test-cases/import - bulk-import one or more xlsx workbooks.

        Accepts multipart/form-data with `files` (or `file`) parts and an
        optional `mapping` form field containing a JSON object
        {raw_header: canonical_field}. Auto-detection runs for any headers
        not in the mapping.
        """
        try:
            files = request.files.getlist("files") or request.files.getlist("file")
            if not files:
                return jsonify({
                    "success": False,
                    "error": "No files uploaded",
                    "message": "Upload at least one Excel workbook",
                }), 400

            created_by = "system"
            try:
                from flask import g
                created_by = g.get("current_username") or created_by
            except Exception:
                pass

            mapping_raw = request.form.get("mapping")
            mapping = {}
            if mapping_raw:
                try:
                    parsed = json.loads(mapping_raw)
                    if isinstance(parsed, dict):
                        mapping = {str(k): str(v) for k, v in parsed.items() if v}
                except json.JSONDecodeError:
                    return jsonify({
                        "success": False,
                        "error": "Invalid mapping",
                        "message": "`mapping` must be a JSON object {raw_header: field_name}",
                    }), 400

            # `duplicate_strategy` controls what happens when a row's primary
            # ID is already in the DB. Accepts `skip` (default) or `replace`.
            duplicate_strategy = (request.form.get("duplicate_strategy") or "skip").strip().lower()

            if mapping:
                result = self.bulk_import_service.import_files_with_mapping(
                    files, "test_cases", mapping, created_by,
                    duplicate_strategy=duplicate_strategy,
                )
            else:
                result = self.bulk_import_service.import_files(
                    files, "test_cases", created_by,
                    duplicate_strategy=duplicate_strategy,
                )

            totals = result["totals"]
            return jsonify({
                "success": (
                    totals["created"] > 0
                    or totals.get("updated", 0) > 0
                    or totals["skipped"] > 0
                    or totals["failed"] == 0
                ),
                "message": (
                    f"Imported {totals['created']} created, "
                    f"{totals.get('updated', 0)} updated, "
                    f"{totals['skipped']} skipped, "
                    f"{totals['failed']} failed."
                ),
                "data": result,
            }), 200
        except ValueError as e:
            return jsonify({"success": False, "error": "Invalid import request", "message": str(e)}), 400
        except Exception as e:
            logger.error(f"Test-case bulk import failed: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Bulk import failed",
                "message": str(e),
            }), 500

    def get_automation_status(self) -> Dict[str, Any]:
        """GET /api/test-cases/automation/status"""
        try:
            return jsonify({
                "success": True,
                "data": self.test_automation_service.get_status(),
            }), 200
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to read automation status",
                "message": str(e),
            }), 500

    def list_test_suites(self) -> Dict[str, Any]:
        """GET /api/test-cases/suites"""
        try:
            suites = self.test_suite_preset_service.list_presets()
            return jsonify({
                "success": True,
                "data": suites,
                "count": len(suites),
            }), 200
        except Exception as e:
            logger.error("list_test_suites failed: %s", e, exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to list test suites",
                "message": str(e),
            }), 500

    def create_test_suite(self) -> Dict[str, Any]:
        """POST /api/test-cases/suites"""
        try:
            from flask import g
            data = request.get_json() or {}
            name = data.get("name")
            filters = data.get("filters")
            if not isinstance(filters, dict):
                return jsonify({
                    "success": False,
                    "error": "Validation error",
                    "message": "filters object is required",
                }), 400
            description = data.get("description", "")
            user = getattr(g, "current_user", None) or {}
            created_by = user.get("username") or user.get("email")
            suite = self.test_suite_preset_service.create_preset(
                name,
                filters,
                description=description,
                created_by=created_by,
            )
            return jsonify({
                "success": True,
                "message": "Test suite saved",
                "data": suite,
            }), 201
        except ValueError as e:
            return jsonify({"success": False, "error": "Validation error", "message": str(e)}), 400
        except Exception as e:
            logger.error("create_test_suite failed: %s", e, exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to create test suite",
                "message": str(e),
            }), 500

    def update_test_suite(self, suite_id: int) -> Dict[str, Any]:
        """PUT /api/test-cases/suites/<suite_id>"""
        try:
            data = request.get_json() or {}
            suite = self.test_suite_preset_service.update_preset(
                suite_id,
                name=data.get("name"),
                description=data.get("description"),
                filters=data.get("filters"),
            )
            if not suite:
                return jsonify({
                    "success": False,
                    "error": "Not found",
                    "message": f"Test suite {suite_id} not found",
                }), 404
            return jsonify({
                "success": True,
                "message": "Test suite updated",
                "data": suite,
            }), 200
        except ValueError as e:
            return jsonify({"success": False, "error": "Validation error", "message": str(e)}), 400
        except Exception as e:
            logger.error("update_test_suite failed: %s", e, exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to update test suite",
                "message": str(e),
            }), 500

    def delete_test_suite(self, suite_id: int) -> Dict[str, Any]:
        """DELETE /api/test-cases/suites/<suite_id>"""
        try:
            deleted = self.test_suite_preset_service.delete_preset(suite_id)
            if not deleted:
                return jsonify({
                    "success": False,
                    "error": "Not found",
                    "message": f"Test suite {suite_id} not found",
                }), 404
            return jsonify({"success": True, "message": "Test suite deleted"}), 200
        except Exception as e:
            logger.error("delete_test_suite failed: %s", e, exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to delete test suite",
                "message": str(e),
            }), 500

    def execute_test_cases(self) -> Dict[str, Any]:
        """POST /api/test-cases/execute — run one or more test cases."""
        try:
            data = request.get_json() or {}
            ids = data.get("test_case_ids") or []
            if not isinstance(ids, list):
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "test_case_ids must be an array",
                }), 400
            from flask import g
            user = getattr(g, "current_user", None) or {}
            result = self.test_automation_service.execute(
                [str(i) for i in ids],
                suite_name=data.get("suite_name"),
                triggered_by=user.get("username") or user.get("email"),
                extra=data.get("extra") if isinstance(data.get("extra"), dict) else None,
            )
            status = 200 if result.get("success") else 502
            return jsonify({
                "success": bool(result.get("success")),
                "message": result.get("message") or "Execution finished",
                "data": result,
            }), status
        except ValueError as e:
            return jsonify({"success": False, "error": "Invalid request", "message": str(e)}), 400
        except TimeoutError as e:
            return jsonify({"success": False, "error": "Timeout", "message": str(e)}), 504
        except Exception as e:
            logger.error("execute_test_cases failed: %s", e, exc_info=True)
            return jsonify({
                "success": False,
                "error": "Execution failed",
                "message": str(e),
            }), 500

    def execute_single_test_case(self, test_case_id: str) -> Dict[str, Any]:
        """POST /api/test-cases/<test_case_id>/execute"""
        try:
            existing = self.test_case_service.get_test_case_by_id(test_case_id)
            if not existing:
                return jsonify({
                    "success": False,
                    "error": "Not found",
                    "message": f"Test case {test_case_id} not found",
                }), 404
            from flask import g
            user = getattr(g, "current_user", None) or {}
            result = self.test_automation_service.execute(
                [test_case_id],
                triggered_by=user.get("username") or user.get("email"),
            )
            status = 200 if result.get("success") else 502
            return jsonify({
                "success": bool(result.get("success")),
                "message": result.get("message") or "Execution finished",
                "data": result,
            }), status
        except ValueError as e:
            return jsonify({"success": False, "error": "Invalid request", "message": str(e)}), 400
        except TimeoutError as e:
            return jsonify({"success": False, "error": "Timeout", "message": str(e)}), 504
        except Exception as e:
            logger.error("execute_single_test_case failed: %s", e, exc_info=True)
            return jsonify({
                "success": False,
                "error": "Execution failed",
                "message": str(e),
            }), 500

    def delete_test_case(self, test_case_id: str) -> Dict[str, Any]:
        """DELETE /api/test-cases/<test_case_id> - Delete test case"""
        try:
            success = self.test_case_service.delete_test_case(test_case_id)
            if success:
                return jsonify({
                    "success": True,
                    "message": "Test case deleted successfully"
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Test case not found",
                    "message": f"Test case with ID {test_case_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to delete test case",
                "message": str(e)
            }), 500


def create_test_case_blueprint(test_case_service: ITestCaseService) -> Blueprint:
    """Create and configure test case blueprint"""
    test_case_bp = Blueprint('test_cases', __name__, url_prefix='/api/test-cases')
    controller = TestCaseController(test_case_service)
    
    # Register routes. NOTE: import routes are registered BEFORE the
    # `/<test_case_id>` catch-all so Flask's routing doesn't treat
    # "import" or "feature" as a test_case_id.
    test_case_bp.route('/', methods=['GET'])(controller.get_all_test_cases)
    test_case_bp.route('/', methods=['POST'])(controller.create_test_case)
    test_case_bp.route('/feature', methods=['GET'])(controller.get_test_cases_by_feature)
    test_case_bp.route('/dropdowns', methods=['GET'])(controller.get_dropdowns)
    test_case_bp.route('/automation/status', methods=['GET'])(controller.get_automation_status)
    test_case_bp.route('/suites', methods=['GET'])(controller.list_test_suites)
    test_case_bp.route('/suites', methods=['POST'])(controller.create_test_suite)
    test_case_bp.route('/suites/<int:suite_id>', methods=['PUT'])(controller.update_test_suite)
    test_case_bp.route('/suites/<int:suite_id>', methods=['DELETE'])(controller.delete_test_suite)
    test_case_bp.route('/execute', methods=['POST'])(controller.execute_test_cases)
    test_case_bp.route('/import/fields', methods=['GET'])(controller.get_import_fields)
    test_case_bp.route('/import/preview', methods=['POST'])(controller.preview_import)
    test_case_bp.route('/import', methods=['POST'])(controller.import_test_cases)
    test_case_bp.route('/<test_case_id>/execute', methods=['POST'])(controller.execute_single_test_case)
    test_case_bp.route('/<test_case_id>', methods=['GET'])(controller.get_test_case_by_id)
    test_case_bp.route('/<test_case_id>', methods=['PUT'])(controller.update_test_case)
    test_case_bp.route('/<test_case_id>', methods=['DELETE'])(controller.delete_test_case)
    
    return test_case_bp
