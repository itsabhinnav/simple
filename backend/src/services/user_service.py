from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
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
    def create_user(self, user_data: UserCreateSchema) -> Dict[str, Any]:
        """Create user with business logic validation"""
        pass
    
    @abstractmethod
    def update_user(self, user_id: int, user_data: UserUpdateSchema) -> Optional[Dict[str, Any]]:
        """Update user with business logic validation"""
        pass
    
    @abstractmethod
    def delete_user(self, user_id: int) -> bool:
        """Delete user with business logic validation"""
        pass


class UserService(IUserService):
    """Concrete implementation of user service with business logic"""
    
    def __init__(self, user_repository: IUserRepository, git_database_service=None):
        self.user_repository = user_repository
        self.git_database_service = git_database_service
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users with business logic"""
        try:
            users = self.user_repository.find_all()
            
            # Apply business logic transformations
            for user in users:
                # Mask sensitive information if needed
                if 'email' in user:
                    user['email_masked'] = self._mask_email(user['email'])
                
                # Add computed fields
                user['full_name'] = self._get_full_name(user)
                user['is_active'] = user.get('role') != 'inactive'
            
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
                # Apply business logic transformations
                user['email_masked'] = self._mask_email(user['email'])
                user['full_name'] = self._get_full_name(user)
                user['is_active'] = user.get('role') != 'inactive'
            
            return user
        except Exception as e:
            raise Exception(f"Service error: Failed to get user {user_id} - {str(e)}")
    
    def create_user(self, user_data: UserCreateSchema) -> Dict[str, Any]:
        """Create user with business logic validation"""
        try:
            # Business logic validation
            self._validate_user_creation(user_data)
            
            # Check if username already exists
            existing_user = self.user_repository.find_by_username(user_data.username)
            if existing_user:
                raise ValueError(f"Username '{user_data.username}' already exists")
            
            # Create user
            user = self.user_repository.create(user_data)
            
            # Apply business logic transformations
            if user:
                user['email_masked'] = self._mask_email(user['email'])
                user['full_name'] = self._get_full_name(user)
                user['is_active'] = user.get('role') != 'inactive'
                
                # Commit changes to git if service is available
                if self.git_database_service:
                    try:
                        self.git_database_service.commit_changes(f"Create user: {user_data.username}")
                    except Exception as e:
                        logger.warning(f"Failed to commit user creation to git: {e}")
            
            return user
        except ValueError as e:
            # Re-raise validation errors as-is
            raise e
        except Exception as e:
            logger.error(f"Service error creating user: {str(e)}")
            raise Exception(f"Failed to create user: {str(e)}")
    
    def update_user(self, user_id: int, user_data: UserUpdateSchema) -> Optional[Dict[str, Any]]:
        """Update user with business logic validation"""
        try:
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError("Invalid user ID")
            
            # Check if user exists
            existing_user = self.user_repository.find_by_id(user_id)
            if not existing_user:
                raise ValueError(f"User with ID {user_id} not found")
            
            # Business logic validation
            self._validate_user_update(user_data)
            
            # Check username uniqueness if username is being updated
            if user_data.username and user_data.username != existing_user['username']:
                username_exists = self.user_repository.find_by_username(user_data.username)
                if username_exists:
                    raise ValueError(f"Username '{user_data.username}' already exists")
            
            # Update user
            user = self.user_repository.update(user_id, user_data)
            
            # Apply business logic transformations
            if user:
                user['email_masked'] = self._mask_email(user['email'])
                user['full_name'] = self._get_full_name(user)
                user['is_active'] = user.get('role') != 'inactive'
                
                # Commit changes to git if service is available
                if self.git_database_service:
                    try:
                        self.git_database_service.commit_changes(f"Update user: {user.get('username', user_id)}")
                    except Exception as e:
                        logger.warning(f"Failed to commit user update to git: {e}")
            
            return user
        except ValueError as e:
            # Re-raise validation errors as-is
            raise e
        except Exception as e:
            logger.error(f"Service error updating user {user_id}: {str(e)}")
            raise Exception(f"Failed to update user {user_id}: {str(e)}")
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user with business logic validation"""
        try:
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError("Invalid user ID")
            
            # Check if user exists
            existing_user = self.user_repository.find_by_id(user_id)
            if not existing_user:
                raise ValueError(f"User with ID {user_id} not found")
            
            # Business logic: Prevent deletion of admin users
            if existing_user.get('role') == 'admin':
                raise ValueError("Cannot delete admin users")
            
            # Delete user
            success = self.user_repository.delete(user_id)
            
            # Commit changes to git if service is available and deletion was successful
            if success and self.git_database_service:
                try:
                    self.git_database_service.commit_changes(f"Delete user: {existing_user.get('username', user_id)}")
                except Exception as e:
                    logger.warning(f"Failed to commit user deletion to git: {e}")
            
            return success
        except ValueError as e:
            # Re-raise validation errors as-is
            raise e
        except Exception as e:
            logger.error(f"Service error deleting user {user_id}: {str(e)}")
            raise Exception(f"Failed to delete user {user_id}: {str(e)}")
    
    def _validate_user_creation(self, user_data: UserCreateSchema) -> None:
        """Validate user creation business rules"""
        # Add any business-specific validation rules here
        if user_data.username.lower() in ['admin', 'root', 'system']:
            raise ValueError("Reserved usernames are not allowed")
    
    def _validate_user_update(self, user_data: UserUpdateSchema) -> None:
        """Validate user update business rules"""
        # Add any business-specific validation rules here
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
