"""Service for securely interacting with GitHub repositories."""

import logging
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse

import git

logger = logging.getLogger(__name__)


class GitHubIntegrationError(Exception):
    """Base exception for GitHub integration errors."""
    pass


class InvalidGitHubURLError(GitHubIntegrationError):
    """Raised when the provided GitHub URL is invalid or unsupported."""
    pass


class RepositoryAcquisitionError(GitHubIntegrationError):
    """Raised when repository cloning or fetching fails."""
    pass


class GitHubService:
    """Service for securely acquiring and managing transient GitHub repositories."""

    def __init__(self):
        self._token_env_var = 'SCOPEGUARD_GITHUB_TOKEN'

    def validate_url(self, url: str) -> str:
        """Validate and normalize a GitHub URL.
        
        Args:
            url: The user-provided repository URL.
            
        Returns:
            A normalized URL safe for cloning.
            
        Raises:
            InvalidGitHubURLError: If the URL is malformed or not a GitHub URL.
        """
        if not url:
            raise InvalidGitHubURLError("URL cannot be empty")

        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise InvalidGitHubURLError(f"Unsupported scheme: {parsed.scheme}")

        if parsed.netloc.lower() != 'github.com':
            raise InvalidGitHubURLError("Only github.com repositories are supported")

        # Path should be /owner/repo (with optional .git)
        path = parsed.path.strip('/')
        if not path:
            raise InvalidGitHubURLError("Invalid repository path")

        # Validate owner/repo format against typical GitHub restrictions
        # (alphanumerics and hyphens, generally)
        # Avoid shell syntax or weird injections
        if not re.match(r'^[\w.-]+/[\w.-]+$', path):
            raise InvalidGitHubURLError("Malformed repository path format")

        if path.endswith('.git'):
            path = path[:-4]

        return f"https://github.com/{path}.git"

    def _inject_token(self, url: str, token: str) -> str:
        """Inject an authentication token into the URL securely."""
        parsed = urlparse(url)
        # Reconstruct with token
        return f"{parsed.scheme}://{token}@{parsed.netloc}{parsed.path}"

    def _scrub_token_from_error(self, error_msg: str, token: str) -> str:
        """Remove the token from error messages to prevent exposure."""
        if token and token in error_msg:
            return error_msg.replace(token, '***TOKEN***')
        return error_msg

    @contextmanager
    def acquire_repository(self, url: str) -> Generator[Path, None, None]:
        """Clone a remote repository securely into a transient directory.
        
        This is a context manager that ensures the repository is cleaned up
        after the block exits, regardless of success or failure.
        
        Args:
            url: The GitHub repository URL.
            
        Yields:
            Path: The path to the isolated temporary repository.
            
        Raises:
            InvalidGitHubURLError: If the URL is invalid.
            RepositoryAcquisitionError: If cloning fails (e.g., auth, network).
        """
        normalized_url = self.validate_url(url)
        token = os.environ.get(self._token_env_var)
        
        clone_url = normalized_url
        if token:
            clone_url = self._inject_token(normalized_url, token)

        temp_dir = tempfile.mkdtemp(prefix='scopeguard_gh_')
        temp_path = Path(temp_dir)
        
        logger.info(f"Acquiring repository {normalized_url} into {temp_path}")

        try:
            try:
                # depth=2 for shallow clone to save time, but ensuring HEAD's parent exists for impact analysis
                git.Repo.clone_from(clone_url, temp_dir, depth=2)
            except git.GitCommandError as e:
                # Carefully scrub any tokens from the Git error message
                safe_msg = self._scrub_token_from_error(str(e), token) if token else str(e)
                logger.error(f"Failed to clone repository: {safe_msg}")
                raise RepositoryAcquisitionError(f"Failed to acquire repository: {safe_msg}")
            except Exception as e:
                safe_msg = self._scrub_token_from_error(str(e), token) if token else str(e)
                logger.error(f"Unexpected error acquiring repository: {safe_msg}")
                raise RepositoryAcquisitionError(f"Unexpected error: {safe_msg}")
            
            yield temp_path
            
        finally:
            # Always clean up the temporary directory
            self._cleanup_directory(temp_path)

    def _cleanup_directory(self, path: Path) -> None:
        """Safely delete the temporary directory and its contents."""
        import shutil
        
        def on_rm_error(func, path, exc_info):
            # Try to fix permissions for read-only files (common on Windows with .git)
            import stat
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {path}: {e}")

        if path.exists() and path.is_dir():
            logger.debug(f"Cleaning up transient repository at {path}")
            shutil.rmtree(path, onerror=on_rm_error)
