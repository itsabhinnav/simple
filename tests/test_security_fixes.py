import unittest
import json
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from src.infrastructure.dependency_injection import get_user_service, get_hybrid_database_service
from src.controllers.auth_controller import AuthController
from flask import Flask

class TestSecurityFixes(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.user_service = get_user_service()
        self.auth_controller = AuthController(self.user_service)
        
        # Initialize DB with mocked Git service
        from unittest.mock import MagicMock
        from src.services.git_database_service import GitDatabaseService
        
        mock_git_service = MagicMock(spec=GitDatabaseService)
        mock_git_service.initialize.return_value = True
        
        # Get hybrid service and replace remote_db
        hybrid_service = get_hybrid_database_service()
        hybrid_service.remote_db = mock_git_service
        hybrid_service.initialize()

    def test_sql_injection_signup(self):
        """Test that SQL injection attempts in signup are treated as literal strings"""
        
        # Attempt a username that would cause issues if not escaped
        # e.g. "testuser' OR '1'='1"
        malicious_username = "testuser' OR '1'='1"
        
        with self.app.test_request_context(
            '/api/auth/signup',
            method='POST',
            json={
                "username": malicious_username,
                "email": "test@example.com",
                "password": "password123",
                "secret_key": "secret123",
                "git_token": "token1234567890"
            }
        ):
            # This should succeed (create a user with that weird name) 
            # OR fail with validation error, but NOT crash with SQL syntax error
            try:
                response = self.auth_controller.signup()
                
                # If it returns a tuple (response, status), unpack it
                if isinstance(response, tuple):
                    response_obj, status = response
                else:
                    response_obj = response
                    status = 200 # assumption
                
                # If it was successful, check that the username is literally what we sent
                if status == 201:
                    data = response_obj.get_json()
                    created_username = data['data']['user']['username']
                    self.assertEqual(created_username, malicious_username)
                    print(f"\n[SUCCESS] User created with literal username: {created_username}")
                else:
                    # If it failed, it should be a validation error or similar, not 500 SQL error
                    print(f"\n[INFO] Signup returned status {status}")
                    print(f"[INFO] Response: {response_obj.get_json()}")
                    if status == 500:
                        self.fail("Signup returned 500, possible SQL injection error")
                        
            except Exception as e:
                self.fail(f"Signup raised exception: {e}")

if __name__ == '__main__':
    unittest.main()
