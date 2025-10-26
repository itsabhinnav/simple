import subprocess
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.interfaces.git_file_storage import IGitFileStorage
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class GitFileStorage(IGitFileStorage):
    """Git-based file storage implementation"""
    
    def __init__(self, repo_url: str = "https://gitlab.com/android-devops/sakura-db", 
                 local_repo_path: str = "remote", data_path: str = "data"):
        self.repo_url = repo_url
        self.local_repo_path = Path(local_repo_path)
        self.data_path = Path(data_path)
        self.git_path = self.local_repo_path / ".git"
        
        # Ensure data directory exists
        self.data_path.mkdir(exist_ok=True)
        
        logger.info(f"Git file storage initialized with repo: {repo_url}")
    
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
                        if 'origin/main' in branch:
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
                    import shutil
                    try:
                        shutil.rmtree(self.local_repo_path)
                    except PermissionError:
                        # If we can't remove it, try to use it as is
                        logger.warning(f"Could not remove existing directory {self.local_repo_path}, trying to use as is")
                        return True
                
                # Clone repository
                logger.info("Cloning repository...")
                result = subprocess.run(
                    ["git", "clone", self.repo_url, str(self.local_repo_path)],
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
    
    def push_changes(self, commit_message: str = "Update database files", git_token: str = None) -> bool:
        """Push local changes to remote repository using user's Git token"""
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
            
            # Push to remote with user's token
            if git_token:
                # Use token in URL for authentication
                remote_url = self.repo_url.replace("https://", f"https://oauth2:{git_token}@")
                subprocess.run(
                    ["git", "push", remote_url],
                    cwd=self.local_repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
            else:
                # Fallback to standard push
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
    
    def get_file(self, file_path: str) -> Optional[Path]:
        """Get local file path for a given file"""
        full_path = self.local_repo_path / file_path
        return full_path if full_path.exists() else None
    
    def copy_file_to_data(self, source_file: str, dest_file: str) -> bool:
        """Copy file from git repo to data folder"""
        try:
            source_path = self.local_repo_path / source_file
            dest_path = self.data_path / dest_file
            
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied {source_file} to {dest_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy file {source_file} to {dest_file}: {e}")
            return False
    
    def copy_file_from_data(self, source_file: str, dest_file: str) -> bool:
        """Copy file from data folder to git repo"""
        try:
            source_path = self.data_path / source_file
            dest_path = self.local_repo_path / dest_file
            
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied {source_file} to {dest_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy file {source_file} to {dest_file}: {e}")
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
