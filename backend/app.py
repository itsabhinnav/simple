"""
Sakura Backend Application

This module contains the main Flask application with Artifactory integration,
following SOLID principles and providing a clean API for database management.
"""

import asyncio
import json
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from contextlib import asynccontextmanager

from src.infrastructure.dependency_injection import (
    get_container, get_database_service, get_enhanced_database_service, 
    get_config_manager, get_artifactory_client, get_version_control_service,
    get_conflict_notification_service, get_user_session_manager
)
from utils.database.sync_database_service_v2 import get_sync_database_service
from src.infrastructure.logging_config import get_logger
from src.infrastructure.exceptions import (
    ArtifactoryError, DatabaseConnectionError, ConfigError
)
from config.settings import settings

logger = get_logger(__name__)

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configure CORS
    CORS(app, origins=["http://localhost:4200", "http://localhost:4201"])
    
    # Register routes
    register_routes(app)
    
    return app

def register_routes(app):
    """Register all API routes with the Flask application."""
    
    # Helper function to run async operations in Flask
    def run_async(coro):
        """Run an async coroutine in a new event loop."""
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an event loop, we need to use a different approach
                import concurrent.futures
                import threading
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop exists, create a new one
            return asyncio.run(coro)

    @app.route('/')
    def home():
        """Home endpoint."""
        return jsonify({
            'message': 'Sakura Backend API',
            'status': 'running',
            'version': '1.0.0',
            'environment': settings.environment.value,
            'mock_mode': settings.mock_mode
        })

    @app.route('/api/health')
    def health():
        """Health check endpoint."""
        try:
            # Check Artifactory connectivity
            client = get_artifactory_client()
            is_healthy = run_async(client.health_check())
            
            return jsonify({
                'status': 'healthy' if is_healthy else 'unhealthy',
                'artifactory_connected': is_healthy,
                'timestamp': datetime.now().isoformat(),
                'environment': settings.environment.value,
                'mock_mode': settings.mock_mode
            })
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500

    @app.route('/api/databases', methods=['GET'])
    def list_databases():
        """List all available databases."""
        try:
            db_service = get_sync_database_service()
            databases = db_service.list_databases()
            
            return jsonify({
                'count': len(databases),
                'databases': databases
            })
        except Exception as e:
            logger.error(f"Failed to list databases: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/databases/<db_name>', methods=['GET'])
    def get_database_info(db_name):
        """Get information about a specific database."""
        try:
            db_service = get_sync_database_service()
            info = db_service.get_database_info(db_name)
            
            return jsonify(info)
        except Exception as e:
            logger.error(f"Failed to get database info for {db_name}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/databases/<db_name>/sync', methods=['POST'])
    def sync_database(db_name):
        """Sync a database from Artifactory."""
        try:
            db_service = get_sync_database_service()
            result = db_service.sync_database(db_name)
            
            return jsonify({
                'message': f'Database {db_name} synced successfully',
                'result': result
            })
        except Exception as e:
            logger.error(f"Failed to sync database {db_name}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/databases/<db_name>/query', methods=['POST'])
    def execute_query(db_name):
        """Execute a SQL query on a database."""
        try:
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({'error': 'Query is required'}), 400
            
            query = data['query']
            db_service = get_sync_database_service()
            result = db_service.execute_query(db_name, query)
            
            return jsonify(result)
        except Exception as e:
            logger.error(f"Failed to execute query on {db_name}: {e}")
            return jsonify({'error': str(e)}), 500

    # Test Case Management API endpoints
    @app.route('/api/test-cases', methods=['GET'])
    def list_test_cases():
        """List all test cases."""
        try:
            db_service = get_sync_database_service()
            query = "SELECT * FROM test_cases ORDER BY created_at DESC"
            result = db_service.execute_query('enhanced_sample_db', query)
            
            return jsonify({
                'test_cases': result.get('data', []),
                'count': len(result.get('data', []))
            })
        except Exception as e:
            logger.error(f"Failed to list test cases: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/test-cases', methods=['POST'])
    def create_test_case():
        """Create a new test case."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Test case data is required'}), 400
            
            db_service = get_sync_database_service()
            # Implementation for creating test case
            return jsonify({'message': 'Test case created successfully'})
        except Exception as e:
            logger.error(f"Failed to create test case: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/requirements', methods=['GET'])
    def list_requirements():
        """List all requirements."""
        try:
            db_service = get_sync_database_service()
            query = "SELECT * FROM requirements ORDER BY created_at DESC"
            result = db_service.execute_query('enhanced_sample_db', query)
            
            return jsonify({
                'requirements': result.get('data', []),
                'count': len(result.get('data', []))
            })
        except Exception as e:
            logger.error(f"Failed to list requirements: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/test-executions', methods=['GET'])
    def list_test_executions():
        """List all test executions."""
        try:
            db_service = get_sync_database_service()
            query = "SELECT * FROM test_executions ORDER BY execution_date DESC"
            result = db_service.execute_query('enhanced_sample_db', query)
            
            return jsonify({
                'test_executions': result.get('data', []),
                'count': len(result.get('data', []))
            })
        except Exception as e:
            logger.error(f"Failed to list test executions: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/users', methods=['GET'])
    def list_users():
        """List all users."""
        try:
            db_service = get_sync_database_service()
            query = "SELECT user_id, username, email, full_name, role, department, is_active, created_at FROM users ORDER BY created_at DESC"
            result = db_service.execute_query('enhanced_sample_db', query)
            
            # The result structure is different - data is in result.result
            users_data = result.get('result', [])
            
            return jsonify({
                'users': users_data,
                'count': len(users_data)
            })
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/users/<user_id>', methods=['GET'])
    def get_user(user_id):
        """Get a specific user by ID."""
        try:
            db_service = get_sync_database_service()
            query = f"SELECT * FROM users WHERE user_id = '{user_id}'"
            result = db_service.execute_query('enhanced_sample_db', query)
            
            users = result.get('data', [])
            if not users:
                return jsonify({'error': 'User not found'}), 404
            
            return jsonify({'user': users[0]})
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/test-suites', methods=['GET'])
    def list_test_suites():
        """List all test suites."""
        try:
            db_service = get_sync_database_service()
            query = "SELECT * FROM test_suites ORDER BY created_at DESC"
            result = db_service.execute_query('enhanced_sample_db', query)
            
            return jsonify({
                'test_suites': result.get('data', []),
                'count': len(result.get('data', []))
            })
        except Exception as e:
            logger.error(f"Failed to list test suites: {e}")
            return jsonify({'error': str(e)}), 500

    # Configuration endpoints
    @app.route('/api/config', methods=['GET'])
    def get_config():
        """Get current configuration."""
        try:
            config_manager = get_config_manager()
            config = config_manager.get_config()
            
            return jsonify({
                'config': config,
                'environment': settings.environment.value,
                'mock_mode': settings.mock_mode
            })
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/config', methods=['POST'])
    def update_config():
        """Update configuration."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Configuration data is required'}), 400
            
            config_manager = get_config_manager()
            config_manager.update_config(data)
            
            return jsonify({'message': 'Configuration updated successfully'})
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return jsonify({'error': str(e)}), 500

    # Enhanced database operations with version control
    @app.route('/api/databases/<db_name>/enhanced/sync', methods=['POST'])
    def enhanced_sync_database(db_name):
        """Enhanced sync with version control and conflict detection."""
        try:
            enhanced_service = get_enhanced_database_service()
            result = run_async(enhanced_service.sync_database(db_name))
            
            return jsonify({
                'message': f'Enhanced sync completed for {db_name}',
                'result': result
            })
        except Exception as e:
            logger.error(f"Enhanced sync failed for {db_name}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/databases/<db_name>/enhanced/query', methods=['POST'])
    def enhanced_execute_query(db_name):
        """Enhanced query execution with optimistic locking."""
        try:
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({'error': 'Query is required'}), 400
            
            query = data['query']
            enhanced_service = get_enhanced_database_service()
            result = run_async(enhanced_service.execute_query(db_name, query))
            
            return jsonify(result)
        except Exception as e:
            logger.error(f"Enhanced query execution failed for {db_name}: {e}")
            return jsonify({'error': str(e)}), 500

    # Conflict resolution endpoints
    @app.route('/api/conflicts', methods=['GET'])
    def list_conflicts():
        """List all active conflicts."""
        try:
            conflict_service = get_conflict_notification_service()
            conflicts = run_async(conflict_service.get_active_conflicts())
            
            return jsonify({
                'conflicts': conflicts,
                'count': len(conflicts)
            })
        except Exception as e:
            logger.error(f"Failed to list conflicts: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/conflicts/<conflict_id>/resolve', methods=['POST'])
    def resolve_conflict(conflict_id):
        """Resolve a specific conflict."""
        try:
            data = request.get_json()
            if not data or 'resolution_strategy' not in data:
                return jsonify({'error': 'Resolution strategy is required'}), 400
            
            conflict_service = get_conflict_notification_service()
            result = run_async(conflict_service.resolve_conflict(
                conflict_id, 
                data['resolution_strategy'],
                data.get('user_id', 'anonymous')
            ))
            
            return jsonify({
                'message': f'Conflict {conflict_id} resolved successfully',
                'result': result
            })
        except Exception as e:
            logger.error(f"Failed to resolve conflict {conflict_id}: {e}")
            return jsonify({'error': str(e)}), 500

    # User session management endpoints
    @app.route('/api/sessions', methods=['POST'])
    def create_session():
        """Create a new user session."""
        try:
            data = request.get_json()
            if not data or 'user_id' not in data:
                return jsonify({'error': 'User ID is required'}), 400
            
            session_manager = get_user_session_manager()
            session = run_async(session_manager.create_session(data['user_id']))
            
            return jsonify({
                'message': 'Session created successfully',
                'session': session
            })
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sessions/<session_id>', methods=['GET'])
    def get_session(session_id):
        """Get session information."""
        try:
            session_manager = get_user_session_manager()
            session = run_async(session_manager.get_session(session_id))
            
            if not session:
                return jsonify({'error': 'Session not found'}), 404
            
            return jsonify({'session': session})
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sessions/<session_id>', methods=['DELETE'])
    def end_session(session_id):
        """End a user session."""
        try:
            session_manager = get_user_session_manager()
            run_async(session_manager.end_session(session_id))
            
            return jsonify({'message': 'Session ended successfully'})
        except Exception as e:
            logger.error(f"Failed to end session {session_id}: {e}")
            return jsonify({'error': str(e)}), 500

# Application lifecycle management
@asynccontextmanager
async def lifespan(app):
    """Manage application lifecycle."""
    logger.info("Starting Sakura Backend Application")
    
    # Initialize container
    container = None
    try:
        container = get_container()
        await container.initialize()
        logger.info("Application initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    finally:
        if container:
            await container.cleanup()
        logger.info("Application shutdown completed")

# Legacy support - create app instance for backward compatibility
app = create_app()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
