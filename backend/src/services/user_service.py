from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from src.schemas.user_schema import UserSchema, UserCreateSchema, UserUpdateSchema
from src.repositories.user_repository import IUserRepository
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class IUserService(ABC):
    """Interface for user business logic operations"""
    
    @abstractmethod
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users with business logic"""
        pass
    
    @abstractmethod
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID with business logic"""
        pass

    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username with business logic"""
        pass
    
    @abstractmethod
    def create_user(self, user_data: Union[UserCreateSchema, Dict[str, Any]]) -> Dict[str, Any]:
        """Create user with business logic validation"""
        pass
    
    @abstractmethod
    def update_user(self, user_id: int, user_data: Union[UserUpdateSchema, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Update user with business logic validation"""
        pass
    
    @abstractmethod
    def delete_user(self, user_id: int) -> bool:
        """Delete user with business logic validation"""
        pass


class UserService(IUserService):
    """Concrete implementation of user service with business logic"""
    
    def __init__(self, user_repository: IUserRepository):
        self.user_repository = user_repository

    def _enrich_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        if not user:
            return user
        if 'email' in user:
            user['email_masked'] = self._mask_email(user['email'])
        user['full_name'] = self._get_full_name(user)
        user['display_name'] = self._get_display_name(user)
        user['is_admin'] = (user.get('role') or '').lower() == 'admin'
        user['is_active'] = user.get('role') != 'inactive'
        return user
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users with business logic"""
        try:
            users = self.user_repository.find_all()
            for user in users:
                self._enrich_user(user)
            return users
        except Exception as e:
            raise Exception(f"Service error: Failed to get users - {str(e)}")
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID with business logic"""
        try:
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError("Invalid user ID")
            
            user = self.user_repository.find_by_id(user_id)
            if user:
                self._enrich_user(user)
            return user
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Service error: Failed to get user {user_id} - {str(e)}")

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username with business logic"""
        try:
            user = self.user_repository.find_by_username(username)
            if user:
                self._enrich_user(user)
            return user
        except Exception as e:
            raise Exception(f"Service error: Failed to get user by username - {str(e)}")
    
    def create_user(self, user_data: Union[UserCreateSchema, Dict[str, Any]]) -> Dict[str, Any]:
        """Create user with business logic validation"""
        try:
            if isinstance(user_data, dict):
                payload = user_data
                username = payload.get("username", "")
                if username.lower() in ['admin', 'root', 'system']:
                    raise ValueError("Reserved usernames are not allowed")
                existing_user = self.user_repository.find_by_username(username)
                if isinstance(existing_user, dict):
                    raise ValueError(f"Username '{username}' already exists")
            else:
                if hasattr(user_data, "model_dump"):
                    payload = user_data.model_dump()
                else:
                    payload = user_data.dict()
                schema = UserCreateSchema.model_validate(payload)
                self._validate_user_creation(schema)
                existing_user = self.user_repository.find_by_username(schema.username)
                if isinstance(existing_user, dict):
                    raise ValueError(f"Username '{schema.username}' already exists")

            user = self.user_repository.create(payload)
            if user:
                self._enrich_user(user)
            return user
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Service error creating user: {str(e)}")
            raise Exception(f"Service error: Failed to create user - {str(e)}")
    
    def update_user(self, user_id: int, user_data: Union[UserUpdateSchema, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Update user with business logic validation"""
        try:
            if isinstance(user_data, dict):
                payload = user_data
            elif hasattr(user_data, "model_dump"):
                payload = user_data.model_dump(exclude_unset=True)
            else:
                payload = user_data.dict(exclude_unset=True)

            user = self.user_repository.update(user_id, payload)
            if user:
                self._enrich_user(user)
            return user
        except Exception as e:
            logger.error(f"Service error updating user {user_id}: {str(e)}")
            raise Exception(f"Service error: Failed to update user {user_id} - {str(e)}")
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user with business logic validation"""
        try:
            return self.user_repository.delete(user_id)
        except Exception as e:
            logger.error(f"Service error deleting user {user_id}: {str(e)}")
            raise Exception(f"Service error: Failed to delete user {user_id} - {str(e)}")
    
    def _validate_user_creation(self, user_data: UserCreateSchema) -> None:
        """Validate user creation business rules"""
        if user_data.username.lower() in ['admin', 'root', 'system']:
            raise ValueError("Reserved usernames are not allowed")
    
    def _validate_user_update(self, user_data: UserUpdateSchema) -> None:
        """Validate user update business rules"""
        if user_data.username and user_data.username.lower() in ['admin', 'root', 'system']:
            raise ValueError("Reserved usernames are not allowed")
    
    def _mask_email(self, email: str) -> str:
        """Mask email for privacy"""
        if '@' not in email:
            return email
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            return f"{local[0]}*@{domain}"
        return f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}@{domain}"
    
    def _get_full_name(self, user: Dict[str, Any]) -> str:
        """Get full name from user data"""
        first_name = user.get('first_name', '')
        last_name = user.get('last_name', '')
        if first_name and last_name:
            return f"{first_name} {last_name}"
        elif first_name:
            return first_name
        elif last_name:
            return last_name
        else:
            return user.get('username', 'Unknown')

    def _get_display_name(self, user: Dict[str, Any]) -> str:
        """Display name for API responses (tests expect this field)."""
        first_name = user.get('first_name') or ''
        last_name = user.get('last_name') or ''
        if first_name and last_name:
            return f"{first_name} {last_name}"
        if first_name:
            return first_name
        if last_name:
            return last_name
        return user.get('username', 'Unknown')
