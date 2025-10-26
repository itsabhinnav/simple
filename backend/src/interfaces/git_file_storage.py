from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path


class IGitFileStorage(ABC):
    """Interface for Git-based file storage operations"""
    
    @abstractmethod
    def clone_or_fetch_repo(self) -> bool:
        """Clone repository if not exists, or fetch latest changes if exists"""
        pass
    
    @abstractmethod
    def push_changes(self, commit_message: str = "Update database files", git_token: str = None) -> bool:
        """Push local changes to remote repository using user's Git token"""
        pass
    
    @abstractmethod
    def get_file(self, file_path: str) -> Optional[Path]:
        """Get local file path for a given file"""
        pass
    
    @abstractmethod
    def copy_file_to_data(self, source_file: str, dest_file: str) -> bool:
        """Copy file from git repo to data folder"""
        pass
    
    @abstractmethod
    def copy_file_from_data(self, source_file: str, dest_file: str) -> bool:
        """Copy file from data folder to git repo"""
        pass
    
    @abstractmethod
    def list_files(self, pattern: str = "*") -> List[str]:
        """List files in the repository"""
        pass
    
    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in repository"""
        pass
    
    @abstractmethod
    def get_repo_status(self) -> Dict[str, Any]:
        """Get repository status information"""
        pass
