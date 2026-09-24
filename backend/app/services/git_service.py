"""Read-only Git repository service.

All operations are strictly read-only. This service never modifies
the user's repository — no writes, no index changes, no pushes.
It only reads Git metadata, commit information, and file contents.
"""

import difflib
import logging
from datetime import datetime, timezone
from pathlib import Path

import git
from git import InvalidGitRepositoryError, BadName

from app.models.change_models import (
    ChangeType,
    CommitInfo,
    FileChange,
)

logger = logging.getLogger(__name__)


class GitService:
    """Read-only Git repository service.

    Provides safe access to Git repository metadata, commit information,
    and diff data without ever modifying the repository.
    """

    def validate_repo(self, path: Path) -> bool:
        """Check whether a path is a valid Git repository."""
        try:
            git.Repo(str(path))
            return True
        except (InvalidGitRepositoryError, git.NoSuchPathError):
            return False

    def open_repo(self, path: Path) -> git.Repo:
        """Open a Git repository (read-only).

        Args:
            path: Path to the repository root.

        Returns:
            An open git.Repo object.

        Raises:
            FileNotFoundError: If path does not exist.
            NotADirectoryError: If path is not a directory.
            ValueError: If path is not a Git repository.
        """
        if not path.exists():
            raise FileNotFoundError(f'Path does not exist: {path}')
        if not path.is_dir():
            raise NotADirectoryError(f'Path is not a directory: {path}')
        try:
            return git.Repo(str(path))
        except InvalidGitRepositoryError:
            raise ValueError(f'Not a Git repository: {path}')

    def get_commit_info(self, repo: git.Repo, commit_hash: str) -> CommitInfo:
        """Extract structured information from a commit.

        Args:
            repo: Open Git repository.
            commit_hash: Full or short hash, or a ref like HEAD.

        Returns:
            CommitInfo with commit metadata.

        Raises:
            ValueError: If the commit hash is invalid or not found.
        """
        commit = self._resolve_commit(repo, commit_hash)

        parent_hash = commit.parents[0].hexsha if commit.parents else None

        timestamp = datetime.fromtimestamp(
            commit.committed_date, tz=timezone.utc,
        ).isoformat()

        # Get file change count
        file_changes = self.get_file_changes(repo, commit.hexsha)

        return CommitInfo(
            commit_hash=commit.hexsha,
            short_hash=commit.hexsha[:7],
            author=str(commit.author),
            author_email=str(commit.author.email),
            message=commit.message.strip(),
            timestamp=timestamp,
            parent_hash=parent_hash,
            changed_file_count=len(file_changes),
        )

    def get_file_changes(
        self, repo: git.Repo, commit_hash: str,
    ) -> list[FileChange]:
        """Get the list of files changed in a commit.

        Compares the commit with its first parent. For initial commits
        (no parent), all tracked files are reported as ADDED.

        Args:
            repo: Open Git repository.
            commit_hash: Commit hash to analyze.

        Returns:
            List of FileChange objects.
        """
        commit = self._resolve_commit(repo, commit_hash)
        changes: list[FileChange] = []
        
        # Pre-compute stats using Git's native engine to avoid O(N^2) Python difflib
        stats = commit.stats.files

        if not commit.parents:
            # Initial commit — every file is an addition
            for item in commit.tree.traverse():
                if item.type == 'blob':
                    # Use stats if available, else 0
                    file_stats = stats.get(item.path, {})
                    additions = file_stats.get('insertions', 0)
                    if additions == 0 and item.path.endswith('.py'):
                        additions = self._count_blob_lines(item)
                        
                    changes.append(FileChange(
                        path=item.path,
                        change_type=ChangeType.ADDED,
                        additions=additions,
                        deletions=0,
                    ))
            return changes

        parent = commit.parents[0]
        diff_index = parent.diff(commit)

        for d in diff_index:
            change_type = self._classify_diff(d)
            
            path = d.b_path or d.a_path
            old_path = None
            if change_type == ChangeType.RENAMED:
                old_path = d.a_path
                path = d.b_path
            elif change_type == ChangeType.DELETED:
                path = d.a_path
                
            # Get fast stats
            file_stats = stats.get(path, {})
            if not file_stats and old_path:
                file_stats = stats.get(old_path, {})
                
            additions = file_stats.get('insertions', 0)
            deletions = file_stats.get('deletions', 0)

            # Fallback for empty stats (e.g. renamed without changes)
            if additions == 0 and deletions == 0 and change_type == ChangeType.MODIFIED:
                if path.endswith('.py'):
                    additions, deletions = self._count_diff_lines(d)

            changes.append(FileChange(
                path=path,
                change_type=change_type,
                old_path=old_path,
                additions=additions,
                deletions=deletions,
            ))

        return changes

    def get_file_at_commit(
        self, repo: git.Repo, commit_hash: str, file_path: str,
    ) -> str | None:
        """Retrieve the content of a file at a specific commit.

        Returns None if the file does not exist in the commit's tree.
        """
        try:
            commit = self._resolve_commit(repo, commit_hash)
            blob = commit.tree / file_path
            return blob.data_stream.read().decode('utf-8', errors='replace')
        except (KeyError, BadName, ValueError, git.GitCommandError):
            return None

    def get_commit_history(
        self, repo: git.Repo, limit: int = 20,
    ) -> list[git.objects.Commit]:
        """Retrieve recent commit history (read-only).

        Args:
            repo: Open Git repository.
            limit: Maximum commits to retrieve (1-100). Default 20.

        Returns:
            List of Commit objects, most recent first.
        """
        limit = max(1, min(limit, 100))
        commits: list[git.objects.Commit] = []
        try:
            for commit in repo.iter_commits(max_count=limit):
                commits.append(commit)
        except (ValueError, git.GitCommandError):
            # Repository might be completely empty (no HEAD)
            pass
        return commits

    def get_commits_between(
        self, repo: git.Repo, base_hash: str, head_hash: str,
    ) -> list[git.objects.Commit]:
        """Get commits between base (exclusive) and head (inclusive).

        Args:
            repo: Open Git repository.
            base_hash: Base commit hash (exclusive).
            head_hash: Head commit hash (inclusive).

        Returns:
            List of commits from base to head, most recent first.
        """
        base = self._resolve_commit(repo, base_hash)
        head = self._resolve_commit(repo, head_hash)

        commits: list[git.objects.Commit] = []
        try:
            for commit in repo.iter_commits(f'{base.hexsha}..{head.hexsha}'):
                commits.append(commit)
        except (ValueError, git.GitCommandError):
            pass
        return commits

    def get_file_changes_between(
        self, repo: git.Repo, base_hash: str, head_hash: str,
    ) -> list[FileChange]:
        """Get cumulative file changes between two commits.

        Compares the tree at base_hash with the tree at head_hash.

        Args:
            repo: Open Git repository.
            base_hash: Base commit hash.
            head_hash: Head commit hash.

        Returns:
            List of FileChange objects representing the diff.
        """
        base = self._resolve_commit(repo, base_hash)
        head = self._resolve_commit(repo, head_hash)

        changes: list[FileChange] = []
        diff_index = base.diff(head)

        # Get stats from the cumulative diff
        try:
            stats = head.stats.files
        except Exception:
            stats = {}

        for d in diff_index:
            change_type = self._classify_diff(d)
            path = d.b_path or d.a_path
            old_path = None
            if change_type == ChangeType.RENAMED:
                old_path = d.a_path
                path = d.b_path
            elif change_type == ChangeType.DELETED:
                path = d.a_path

            file_stats = stats.get(path, {})
            if not file_stats and old_path:
                file_stats = stats.get(old_path, {})

            additions = file_stats.get('insertions', 0)
            deletions = file_stats.get('deletions', 0)

            changes.append(FileChange(
                path=path,
                change_type=change_type,
                old_path=old_path,
                additions=additions,
                deletions=deletions,
            ))

        return changes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_commit(
        self, repo: git.Repo, commit_hash: str,
    ) -> git.objects.Commit:
        """Resolve a commit hash to a Commit object."""
        try:
            return repo.commit(commit_hash)
        except (BadName, ValueError, git.GitCommandError) as e:
            raise ValueError(f'Invalid commit: {commit_hash} ({e})')

    def _classify_diff(self, d: git.Diff) -> ChangeType:
        """Classify a git.Diff item into a ChangeType."""
        if d.renamed_file:
            return ChangeType.RENAMED
        if d.new_file:
            return ChangeType.ADDED
        if d.deleted_file:
            return ChangeType.DELETED
        return ChangeType.MODIFIED

    def _count_blob_lines(self, blob: git.objects.Blob) -> int:
        """Count lines in a blob."""
        try:
            content = blob.data_stream.read().decode('utf-8', errors='replace')
            return len(content.splitlines())
        except Exception:
            return 0

    def _count_diff_lines(self, d: git.Diff) -> tuple[int, int]:
        """Count added and deleted lines for a diff item using unified diff."""
        try:
            old_content = ''
            new_content = ''

            if d.a_blob:
                old_content = d.a_blob.data_stream.read().decode(
                    'utf-8', errors='replace',
                )
            if d.b_blob:
                new_content = d.b_blob.data_stream.read().decode(
                    'utf-8', errors='replace',
                )

            old_lines = old_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)

            additions = 0
            deletions = 0
            for line in difflib.unified_diff(old_lines, new_lines):
                if line.startswith('+') and not line.startswith('+++'):
                    additions += 1
                elif line.startswith('-') and not line.startswith('---'):
                    deletions += 1

            return additions, deletions
        except Exception:
            return 0, 0
