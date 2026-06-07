from flask import Blueprint, request, jsonify
from typing import Dict, Any
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import jwt
from datetime import datetime, timedelta
from src.services.user_service import IUserService
from src.schemas.user_schema import LoginSchema, UserCreateSchema
from src.infrastructure.logging_config import get_logger
from src.middleware.error_handlers import limiter

logger = get_logger(__name__)

import os
from cryptography.fernet import Fernet

# SAK-007 fix: JWT_SECRET_KEY and ENCRYPTION_KEY are required in every
# environment. The previous code shipped predictable defaults whenever
# ENVIRONMENT was anything other than the literal string "production"
# (so 'prod', 'staging', or 'corp' all matched the fallback). The fallback
# is gone — the app refuses to start without explicit secrets.
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
if not JWT_SECRET_KEY or len(JWT_SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY must be set to at least 32 bytes of entropy. Generate one with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )

ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    raise RuntimeError(
        "ENCRYPTION_KEY must be set. Generate one with: "
        "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

try:
    fernet = Fernet(ENCRYPTION_KEY)
except Exception as e:
    raise RuntimeError(
        "ENCRYPTION_KEY is not a valid Fernet key (must be a url-safe base64-encoded 32-byte value). "
        "Regenerate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    ) from e

JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24


class AuthController:
    """Controller for authentication-related API endpoints"""
    
    def __init__(self, user_service: IUserService):
        self.user_service = user_service
    
    def signup(self) -> Dict[str, Any]:
        """POST /api/auth/signup - Create a new user account"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            # Validate data using schema
            user_data = UserCreateSchema(**data)
            
            # Check if username already exists
            existing_user = self.user_service.user_repository.find_by_username(user_data.username)
            if existing_user:
                return jsonify({
                    "success": False,
                    "error": "Username already exists",
                    "message": f"Username '{user_data.username}' is already taken"
                }), 400
            
            # Hash the password
            password_hash = generate_password_hash(user_data.password)
            
            # Hash the secret key
            secret_key_hash = generate_password_hash(user_data.secret_key)
            
            # Encrypt the Git token using Fernet (if provided)
            git_token_encrypted = None
            if user_data.git_token:
                git_token_encrypted = fernet.encrypt(user_data.git_token.encode('utf-8')).decode('utf-8')
            
            # Create user dict
            user_dict = user_data.dict()
            user_dict['password_hash'] = password_hash
            user_dict['secret_key_hash'] = secret_key_hash
            user_dict.pop('password', None)  # Remove plain password
            user_dict.pop('secret_key', None)  # Remove plain secret key
            user_dict.pop('git_token', None)  # Remove plain git token
            
            # Manually insert the user since we need password_hash
            # Use the hybrid database service for version tracking and sync
            from src.infrastructure.dependency_injection import get_hybrid_database_service
            database_service = get_hybrid_database_service()
            
            # Use parameterized query to prevent SQL injection
            query = """
                INSERT INTO users (username, email, password_hash, secret_key_hash, git_token_encrypted, first_name, last_name, role)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                user_dict['username'],
                user_dict['email'],
                password_hash,
                secret_key_hash,
                git_token_encrypted,
                user_dict.get('first_name', ''),
                user_dict.get('last_name', ''),
                user_dict.get('role', 'user')
            )
            
            logger.info(f"Executing signup query for user: {user_data.username}")
            result = database_service.execute_query(query, "default", params=params)
            
            # Check if query was successful
            if result.get("success") is False:
                error_msg = result.get('error', 'Failed to create user')
                logger.error(f"Failed to create user: {error_msg}")
                raise Exception(error_msg)
            
            logger.info(f"Query executed successfully, row_id: {result.get('lastrowid')}")
            
            # Fetch the created user using the same database service to ensure consistency
            fetch_query = "SELECT * FROM users WHERE username = ?"
            logger.info(f"Fetching user with query: {fetch_query}")
            fetch_result = database_service.execute_query(fetch_query, "default", params=(user_dict['username'],))
            logger.info(f"Fetch result: success={fetch_result.get('success')}, data_count={len(fetch_result.get('data', []))}")
            
            if not fetch_result.get("success") or not fetch_result.get("data"):
                logger.error(f"Failed to fetch created user: {user_data.username}")
                logger.error(f"Fetch result details: {fetch_result}")
                raise Exception("Failed to fetch created user")
            
            user = fetch_result['data'][0]
            
            # Generate JWT token
            token = self._generate_token(user['id'], user['username'])

            return jsonify({
                "success": True,
                "message": "User created successfully",
                "data": {
                    "user": self._sanitize_user(user),
                    "token": token
                }
            }), 201
            
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception:
            logger.exception("Signup error")
            return jsonify({
                "success": False,
                "error": "Failed to create user",
                "message": "An internal error occurred"
            }), 500

    def login(self) -> Dict[str, Any]:
        """POST /api/auth/login - Authenticate a user"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            # Validate data using schema
            login_data = LoginSchema(**data)
            
            # Find user by username
            user = self.user_service.user_repository.find_by_username(login_data.username)
            
            if not user:
                return jsonify({
                    "success": False,
                    "error": "Invalid credentials",
                    "message": "Username or password is incorrect"
                }), 401
            
            # Check password
            if not user.get('password_hash'):
                return jsonify({
                    "success": False,
                    "error": "Invalid credentials",
                    "message": "User account is not properly configured"
                }), 401
            
            if not check_password_hash(user['password_hash'], login_data.password):
                return jsonify({
                    "success": False,
                    "error": "Invalid credentials",
                    "message": "Username or password is incorrect"
                }), 401
            
            # Generate JWT token
            token = self._generate_token(user['id'], user['username'])

            return jsonify({
                "success": True,
                "message": "Login successful",
                "data": {
                    "user": self._sanitize_user(user),
                    "token": token
                }
            }), 200
            
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception:
            logger.exception("Login error")
            return jsonify({
                "success": False,
                "error": "Failed to login",
                "message": "An internal error occurred"
            }), 500
    
    def verify_token(self) -> Dict[str, Any]:
        """GET /api/auth/verify - Verify JWT token"""
        try:
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({
                    "success": False,
                    "error": "Invalid authorization header"
                }), 401
            
            token = auth_header.split(' ')[1]
            decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            user_id = decoded['user_id']
            user = self.user_service.user_repository.find_by_id(user_id)
            
            if not user:
                return jsonify({
                    "success": False,
                    "error": "User not found"
                }), 401
            
            return jsonify({
                "success": True,
                "data": self._sanitize_user(user)
            }), 200
            
        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "error": "Token has expired"
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "error": "Invalid token"
            }), 401
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            return jsonify({
                "success": False,
                "error": "Token verification failed"
            }), 500
    
    def _generate_token(self, user_id: int, username: str) -> str:
        """Generate a JWT token for the user"""
        payload = {
            'user_id': user_id,
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    def verify_secret_key(self) -> Dict[str, Any]:
        """POST /api/auth/verify-secret - Verify secret key for password reset"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            username = data.get('username')
            secret_key = data.get('secret_key')
            
            if not username or not secret_key:
                return jsonify({
                    "success": False,
                    "error": "Missing fields",
                    "message": "Username and secret_key are required"
                }), 400
            
            user = self.user_service.user_repository.find_by_username(username)
            
            if not user or not user.get('secret_key_hash'):
                return jsonify({
                    "success": False,
                    "error": "Invalid credentials",
                    "message": "Invalid username or secret key"
                }), 401
            
            if check_password_hash(user['secret_key_hash'], secret_key):
                return jsonify({
                    "success": True,
                    "message": "Secret key verified successfully"
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Invalid credentials",
                    "message": "Invalid username or secret key"
                }), 401
                
        except Exception:
            logger.exception("Secret key verification error")
            return jsonify({
                "success": False,
                "error": "Verification failed",
                "message": "An internal error occurred"
            }), 500

    def reset_password(self) -> Dict[str, Any]:
        """POST /api/auth/reset-password - Reset user password"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            username = data.get('username')
            new_password = data.get('new_password')

            if not username or not new_password:
                return jsonify({
                    "success": False,
                    "error": "Missing fields",
                    "message": "Username and new_password are required"
                }), 400

            from src.schemas.user_schema import PASSWORD_MIN_LENGTH
            if len(new_password) < PASSWORD_MIN_LENGTH:
                return jsonify({
                    "success": False,
                    "error": "Validation error",
                    "message": f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
                }), 400
            
            user = self.user_service.user_repository.find_by_username(username)
            
            if not user:
                return jsonify({
                    "success": False,
                    "error": "User not found",
                    "message": "Invalid username"
                }), 404
            
            # Hash the new password
            password_hash = generate_password_hash(new_password)
            
            # Update the password
            # Use local database service for password updates
            from src.infrastructure.dependency_injection import get_local_database_service
            local_database_service = get_local_database_service()
            database_service = local_database_service
            
            query = """
                UPDATE users 
                SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE username = ?
            """
            
            result = database_service.execute_query(query, "default", params=(password_hash, username))
            
            if not result.get("success"):
                raise Exception(result.get('error', 'Failed to reset password'))
            
            return jsonify({
                "success": True,
                "message": "Password reset successfully"
            }), 200
                
        except Exception:
            logger.exception("Password reset error")
            return jsonify({
                "success": False,
                "error": "Reset failed",
                "message": "An internal error occurred"
            }), 500
    
    def _sanitize_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from user data"""
        sanitized = user.copy()
        sanitized.pop('password_hash', None)
        sanitized.pop('password', None)
        sanitized.pop('secret_key_hash', None)
        sanitized.pop('secret_key', None)
        sanitized.pop('git_token_encrypted', None)  # Never expose Git token
        sanitized.pop('git_token', None)
        return sanitized


def create_auth_blueprint(user_service: IUserService) -> Blueprint:
    """Create and configure auth blueprint.

    SAK-023 fix: per-route rate limits on every credential-checking endpoint.
    Tighter than the global default (1000/day, 200/hour) which would allow
    credential stuffing within the global budget. Verify-secret and reset are
    coupled because they form the recovery flow.
    """
    auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
    controller = AuthController(user_service)

    # Each endpoint gets a strict per-IP limit. The limiter is configured at
    # app-create time via setup_rate_limiting() in main.py.
    auth_bp.route('/signup', methods=['POST'])(
        limiter.limit("5 per minute; 20 per hour")(controller.signup)
    )
    auth_bp.route('/login', methods=['POST'])(
        limiter.limit("10 per minute; 60 per hour")(controller.login)
    )
    auth_bp.route('/verify', methods=['GET'])(
        limiter.limit("60 per minute")(controller.verify_token)
    )
    auth_bp.route('/verify-secret', methods=['POST'])(
        limiter.limit("5 per minute; 20 per hour")(controller.verify_secret_key)
    )
    auth_bp.route('/reset-password', methods=['POST'])(
        limiter.limit("3 per minute; 10 per hour")(controller.reset_password)
    )

    return auth_bp
