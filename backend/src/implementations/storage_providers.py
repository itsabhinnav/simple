"""
Extensible Storage Provider Implementations

This module provides concrete implementations of storage providers,
making the system easily extensible to support different storage backends.
"""

import subprocess
import os
import shutil
import requests
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, BinaryIO
from src.interfaces.providers import (
    IStorageProvider, IGitProvider, IArtifactoryProvider, 
    ICloudStorageProvider, StorageProviderType
)
from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class GitStorageProvider(IGitProvider):
    """Git-based storage provider implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.repo_url = config.get("base_url", "")
        self.local_repo_path = Path(config.get("local_repo_path", "remote"))
        self.data_path = Path(config.get("data_path", "data"))
        self.branch = config.get("branch", "main")
        self.git_username = config.get("git_username")
        self.git_token = config.get("git_token")
        self.git_path = self.local_repo_path / ".git"
        
        # Ensure data directory exists
        self.data_path.mkdir(exist_ok=True)
        
        logger.info(f"Git storage provider initialized with repo: {self.repo_url}")
    
    def authenticate(self, username: str, password: str) -> bool:
        """Git authentication is handled via tokens or SSH keys"""
        return True  # Git authentication is typically handled via tokens/SSH
    
    def health_check(self) -> bool:
        """Check if git repository is accessible"""
        try:
            if self.git_path.exists():
                result = subprocess.run(
                    ["git", "status"],
                    cwd=self.local_repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.returncode == 0
            else:
                # Try to clone the repository
                return self.clone_or_fetch_repo()
        except Exception as e:
            logger.error(f"Git health check failed: {e}")
            return False
    
    def clone_or_fetch_repo(self) -> bool:
        """Clone repository if not exists, or fetch latest changes if exists"""
        try:
            if self.git_path.exists():
                # Repository exists, fetch latest changes
                logger.info("Repository exists, fetching latest changes...")
                try:
                    result = subprocess.run(
                        ["git", "fetch", "origin"],
                        cwd=self.local_repo_path,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    # Reset to latest main/master branch
                    branch_result = subprocess.run(
                        ["git", "branch", "-r"],
                        cwd=self.local_repo_path,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    # Determine main branch (main or master)
                    branches = branch_result.stdout.strip().split('\n')
                    main_branch = None
                    for branch in branches:
                        if f'origin/{self.branch}' in branch:
                            main_branch = self.branch
                            break
                        elif 'origin/main' in branch:
                            main_branch = 'main'
                            break
                        elif 'origin/master' in branch:
                            main_branch = 'master'
                            break
                    
                    if main_branch:
                        subprocess.run(
                            ["git", "reset", "--hard", f"origin/{main_branch}"],
                            cwd=self.local_repo_path,
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        logger.info(f"Reset to latest {main_branch} branch")
                    else:
                        logger.warning("No main/master branch found")
                        
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Git fetch failed, but repository exists: {e.stderr}")
                    # Repository exists, continue anyway
                
            else:
                # Check if directory exists but is not a git repo
                if self.local_repo_path.exists() and not self.local_repo_path.is_dir():
                    # Remove file if it exists
                    self.local_repo_path.unlink()
                elif self.local_repo_path.exists() and self.local_repo_path.is_dir():
                    # Directory exists but not a git repo, remove it
                    try:
                        shutil.rmtree(self.local_repo_path)
                    except PermissionError:
                        # If we can't remove it, try to use it as is
                        logger.warning(f"Could not remove existing directory {self.local_repo_path}, trying to use as is")
                        return True
                
                # Clone repository
                logger.info("Cloning repository...")
                clone_url = self.repo_url
                if self.git_token:
                    # Use token for authentication
                    clone_url = self.repo_url.replace("https://", f"https://{self.git_token}@")
                
                result = subprocess.run(
                    ["git", "clone", clone_url, str(self.local_repo_path)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info("Repository cloned successfully")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git operation failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during git operation: {e}")
            return False
    
    def push_changes(self, commit_message: str = "Update files") -> bool:
        """Push local changes to remote repository"""
        try:
            # Add all changes
            subprocess.run(
                ["git", "add", "."],
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Check if there are changes to commit
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            if not status_result.stdout.strip():
                logger.info("No changes to commit")
                return True
            
            # Commit changes
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Push to remote
            subprocess.run(
                ["git", "push", "origin"],
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("Changes pushed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git push failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during git push: {e}")
            return False
    
    def list_files(self, pattern: str = "*") -> List[str]:
        """List files in the repository"""
        try:
            files = []
            for file_path in self.local_repo_path.rglob(pattern):
                if file_path.is_file():
                    # Get relative path from repo root
                    rel_path = file_path.relative_to(self.local_repo_path)
                    files.append(str(rel_path))
            return files
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in repository"""
        full_path = self.local_repo_path / file_path
        return full_path.exists()
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file information"""
        full_path = self.local_repo_path / file_path
        if full_path.exists():
            stat = full_path.stat()
            return {
                "path": file_path,
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "is_file": full_path.is_file(),
                "is_directory": full_path.is_dir()
            }
        return None
    
    def download_file(self, file_path: str, local_path: str) -> bool:
        """Download file to local path"""
        try:
            source_path = self.local_repo_path / file_path
            dest_path = Path(local_path)
            
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            logger.info(f"Downloaded {file_path} to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download file {file_path} to {local_path}: {e}")
            return False
    
    def upload_file(self, local_path: str, file_path: str) -> bool:
        """Upload file from local path"""
        try:
            source_path = Path(local_path)
            dest_path = self.local_repo_path / file_path
            
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            logger.info(f"Uploaded {local_path} to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload file {local_path} to {file_path}: {e}")
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Delete file"""
        try:
            full_path = self.local_repo_path / file_path
            if full_path.exists():
                full_path.unlink()
                logger.info(f"Deleted file: {file_path}")
                return True
            else:
                logger.warning(f"File not found: {file_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    def get_repo_status(self) -> Dict[str, Any]:
        """Get repository status information"""
        try:
            # Get current branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            current_branch = branch_result.stdout.strip()
            
            # Get last commit info
            commit_result = subprocess.run(
                ["git", "log", "-1", "--format=%H|%s|%an|%ad", "--date=iso"],
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            last_commit = None
            if commit_result.stdout.strip():
                parts = commit_result.stdout.strip().split('|')
                if len(parts) >= 4:
                    last_commit = {
                        "hash": parts[0],
                        "message": parts[1],
                        "author": parts[2],
                        "date": parts[3]
                    }
            
            # Get status
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            has_changes = bool(status_result.stdout.strip())
            
            return {
                "current_branch": current_branch,
                "last_commit": last_commit,
                "has_changes": has_changes,
                "repo_path": str(self.local_repo_path),
                "data_path": str(self.data_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to get repo status: {e}")
            return {
                "error": str(e),
                "repo_path": str(self.local_repo_path),
                "data_path": str(self.data_path)
            }
    
    def create_branch(self, branch_name: str) -> bool:
        """Create a new branch"""
        try:
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Created branch: {branch_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create branch {branch_name}: {e.stderr}")
            return False
    
    def switch_branch(self, branch_name: str) -> bool:
        """Switch to a different branch"""
        try:
            subprocess.run(
                ["git", "checkout", branch_name],
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Switched to branch: {branch_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to switch to branch {branch_name}: {e.stderr}")
            return False
    
    def merge_branch(self, source_branch: str, target_branch: str) -> bool:
        """Merge branches"""
        try:
            # Switch to target branch
            if not self.switch_branch(target_branch):
                return False
            
            # Merge source branch
            subprocess.run(
                ["git", "merge", source_branch],
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Merged {source_branch} into {target_branch}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to merge {source_branch} into {target_branch}: {e.stderr}")
            return False
    
    def get_provider_type(self) -> StorageProviderType:
        """Get the provider type"""
        return StorageProviderType.GIT


class ArtifactoryStorageProvider(IArtifactoryProvider):
    """Artifactory storage provider implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get("base_url", "")
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.repository = config.get("repository", "")
        self.timeout = config.get("timeout", 30)
        self.retry_attempts = config.get("retry_attempts", 3)
        self.retry_delay = config.get("retry_delay", 1.0)
        self.verify_ssl = config.get("verify_ssl", True)
        self.api_version = config.get("api_version", "v1")
        self.repo_type = config.get("artifactory_repo_type", "generic-local")
        
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.verify = self.verify_ssl
        
        logger.info(f"Artifactory storage provider initialized with base URL: {self.base_url}")
    
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with Artifactory"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/system/ping",
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Artifactory authentication failed: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check if Artifactory is healthy"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/system/ping",
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Artifactory health check failed: {e}")
            return False
    
    def list_files(self, pattern: str = "*") -> List[str]:
        """List files in Artifactory repository"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/storage/{self.repository}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                files = []
                for item in data.get("children", []):
                    if item.get("folder", False):
                        # Recursively get files from subdirectories
                        sub_files = self._list_files_recursive(f"{self.repository}/{item['uri']}")
                        files.extend(sub_files)
                    else:
                        files.append(item["uri"].lstrip("/"))
                return files
            else:
                logger.error(f"Failed to list files: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def _list_files_recursive(self, path: str) -> List[str]:
        """Recursively list files in a directory"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/storage/{path}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                files = []
                for item in data.get("children", []):
                    if item.get("folder", False):
                        sub_files = self._list_files_recursive(f"{path}/{item['uri']}")
                        files.extend(sub_files)
                    else:
                        files.append(f"{path}/{item['uri']}".lstrip("/"))
                return files
            return []
        except Exception as e:
            logger.error(f"Failed to list files recursively: {e}")
            return []
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in Artifactory"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/storage/{self.repository}/{file_path}",
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to check file existence: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file information from Artifactory"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/storage/{self.repository}/{file_path}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "path": file_path,
                    "size": data.get("size", 0),
                    "created": data.get("created", ""),
                    "modified": data.get("modified", ""),
                    "download_uri": data.get("downloadUri", ""),
                    "repo": data.get("repo", ""),
                    "checksums": data.get("checksums", {})
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            return None
    
    def download_file(self, file_path: str, local_path: str) -> bool:
        """Download file from Artifactory"""
        try:
            response = self.session.get(
                f"{self.base_url}/{self.repository}/{file_path}",
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code == 200:
                local_file_path = Path(local_path)
                local_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(local_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.info(f"Downloaded {file_path} to {local_path}")
                return True
            else:
                logger.error(f"Failed to download file: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to download file {file_path}: {e}")
            return False
    
    def upload_file(self, local_path: str, file_path: str) -> bool:
        """Upload file to Artifactory"""
        try:
            local_file_path = Path(local_path)
            if not local_file_path.exists():
                logger.error(f"Local file not found: {local_path}")
                return False
            
            with open(local_file_path, 'rb') as f:
                response = self.session.put(
                    f"{self.base_url}/{self.repository}/{file_path}",
                    data=f,
                    timeout=self.timeout
                )
            
            if response.status_code in [200, 201]:
                logger.info(f"Uploaded {local_path} to {file_path}")
                return True
            else:
                logger.error(f"Failed to upload file: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to upload file {local_path}: {e}")
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Delete file from Artifactory"""
        try:
            response = self.session.delete(
                f"{self.base_url}/{self.repository}/{file_path}",
                timeout=self.timeout
            )
            
            if response.status_code == 204:
                logger.info(f"Deleted file: {file_path}")
                return True
            else:
                logger.error(f"Failed to delete file: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    def get_repository_info(self) -> Dict[str, Any]:
        """Get repository information"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/repositories/{self.repository}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get repository info: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Failed to get repository info: {e}")
            return {}
    
    def search_artifacts(self, query: str) -> List[Dict[str, Any]]:
        """Search for artifacts"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/search/aql",
                timeout=self.timeout,
                json={"query": query}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            else:
                logger.error(f"Failed to search artifacts: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Failed to search artifacts: {e}")
            return []
    
    def get_artifact_properties(self, file_path: str) -> Dict[str, Any]:
        """Get artifact properties"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/storage/{self.repository}/{file_path}?properties",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("properties", {})
            else:
                logger.error(f"Failed to get artifact properties: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Failed to get artifact properties: {e}")
            return {}
    
    def set_artifact_properties(self, file_path: str, properties: Dict[str, str]) -> bool:
        """Set artifact properties"""
        try:
            # Convert properties to query string format
            props = []
            for key, value in properties.items():
                props.append(f"{key}={value}")
            
            response = self.session.put(
                f"{self.base_url}/api/storage/{self.repository}/{file_path}?properties={';'.join(props)}",
                timeout=self.timeout
            )
            
            if response.status_code == 204:
                logger.info(f"Set properties for {file_path}")
                return True
            else:
                logger.error(f"Failed to set artifact properties: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to set artifact properties: {e}")
            return False
    
    def promote_artifact(self, file_path: str, target_repo: str) -> bool:
        """Promote artifact to target repository"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/plugins/build/promote/{self.repository}",
                timeout=self.timeout,
                json={
                    "targetRepo": target_repo,
                    "path": file_path
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Promoted {file_path} to {target_repo}")
                return True
            else:
                logger.error(f"Failed to promote artifact: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to promote artifact: {e}")
            return False
    
    def get_provider_type(self) -> StorageProviderType:
        """Get the provider type"""
        return StorageProviderType.ARTIFACTORY


class LocalStorageProvider(IStorageProvider):
    """Local file system storage provider implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_path = Path(config.get("base_url", "file:///tmp/sakura").replace("file://", ""))
        self.data_path = Path(config.get("data_path", "data"))
        
        # Ensure directories exist
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Local storage provider initialized with base path: {self.base_path}")
    
    def authenticate(self, username: str, password: str) -> bool:
        """Local storage doesn't require authentication"""
        return True
    
    def health_check(self) -> bool:
        """Check if local storage is accessible"""
        try:
            return self.base_path.exists() and self.base_path.is_dir()
        except Exception as e:
            logger.error(f"Local storage health check failed: {e}")
            return False
    
    def list_files(self, pattern: str = "*") -> List[str]:
        """List files in local storage"""
        try:
            files = []
            for file_path in self.base_path.rglob(pattern):
                if file_path.is_file():
                    rel_path = file_path.relative_to(self.base_path)
                    files.append(str(rel_path))
            return files
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        full_path = self.base_path / file_path
        return full_path.exists()
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file information"""
        full_path = self.base_path / file_path
        if full_path.exists():
            stat = full_path.stat()
            return {
                "path": file_path,
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "is_file": full_path.is_file(),
                "is_directory": full_path.is_dir()
            }
        return None
    
    def download_file(self, file_path: str, local_path: str) -> bool:
        """Copy file to local path"""
        try:
            source_path = self.base_path / file_path
            dest_path = Path(local_path)
            
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied {file_path} to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy file {file_path} to {local_path}: {e}")
            return False
    
    def upload_file(self, local_path: str, file_path: str) -> bool:
        """Copy file from local path to storage"""
        try:
            source_path = Path(local_path)
            dest_path = self.base_path / file_path
            
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied {local_path} to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy file {local_path} to {file_path}: {e}")
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Delete file"""
        try:
            full_path = self.base_path / file_path
            if full_path.exists():
                full_path.unlink()
                logger.info(f"Deleted file: {file_path}")
                return True
            else:
                logger.warning(f"File not found: {file_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    def get_provider_type(self) -> StorageProviderType:
        """Get the provider type"""
        return StorageProviderType.LOCAL


def create_storage_provider(config: Dict[str, Any]) -> IStorageProvider:
    """Factory function to create storage provider based on configuration"""
    provider_type = config.get("provider", "git")
    
    if provider_type == "git":
        return GitStorageProvider(config)
    elif provider_type == "artifactory":
        return ArtifactoryStorageProvider(config)
    elif provider_type == "local":
        return LocalStorageProvider(config)
    else:
        raise ValueError(f"Unsupported storage provider: {provider_type}")
