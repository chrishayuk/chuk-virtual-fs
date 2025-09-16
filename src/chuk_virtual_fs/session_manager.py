"""
chuk_virtual_fs/session_manager.py - Session-based access control and management
"""

import asyncio
import contextlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session states"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class AccessLevel(Enum):
    """Access levels for sessions"""

    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"


@dataclass
class Session:
    """Represents a user session"""

    session_id: str
    sandbox_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    state: SessionState = SessionState.ACTIVE
    access_level: AccessLevel = AccessLevel.READ_WRITE

    # Access control
    allowed_paths: set[str] = field(default_factory=set)
    denied_paths: set[str] = field(default_factory=set)

    # Metadata
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Statistics
    operations_count: int = 0
    bytes_written: int = 0
    bytes_read: int = 0
    files_created: int = 0
    files_deleted: int = 0

    def is_expired(self) -> bool:
        """Check if session has expired"""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            self.state = SessionState.EXPIRED
            return True
        return False

    def is_active(self) -> bool:
        """Check if session is active"""
        return self.state == SessionState.ACTIVE and not self.is_expired()

    def can_read(self, path: str) -> bool:
        """Check if session can read from path"""
        if not self.is_active():
            return False

        # Check denied paths first
        for denied in self.denied_paths:
            if path.startswith(denied):
                return False

        # If allowed paths are specified, path must be in allowed list
        if self.allowed_paths:
            return any(path.startswith(allowed) for allowed in self.allowed_paths)

        # Default allow if no restrictions
        return True

    def can_write(self, path: str) -> bool:
        """Check if session can write to path"""
        if self.access_level == AccessLevel.READ_ONLY:
            return False
        return self.can_read(path)

    def can_delete(self, path: str) -> bool:
        """Check if session can delete path"""
        return self.can_write(path)

    def update_stats(self, operation: str, bytes_count: int = 0) -> None:
        """Update session statistics"""
        self.operations_count += 1

        if operation == "read":
            self.bytes_read += bytes_count
        elif operation == "write":
            self.bytes_written += bytes_count
        elif operation == "create":
            self.files_created += 1
        elif operation == "delete":
            self.files_deleted += 1


class SessionManager:
    """
    Manages sessions for the virtual filesystem
    """

    def __init__(
        self,
        default_ttl: int = 3600,
        max_sessions: int = 1000,
        cleanup_interval: int = 300,
    ):
        """
        Initialize session manager

        Args:
            default_ttl: Default session TTL in seconds
            max_sessions: Maximum number of concurrent sessions
            cleanup_interval: Interval for cleanup task in seconds
        """
        self.sessions: dict[str, Session] = {}
        self.default_ttl = default_ttl
        self.max_sessions = max_sessions
        self.cleanup_interval = cleanup_interval

        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

        # Statistics
        self.stats = {
            "total_sessions_created": 0,
            "total_sessions_expired": 0,
            "total_sessions_terminated": 0,
            "total_operations": 0,
            "access_denied_count": 0,
        }

    async def start(self) -> None:
        """Start the session manager"""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the session manager"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def allocate_session(
        self,
        session_id: str | None = None,
        sandbox_id: str = "default",
        ttl: int | None = None,
        access_level: AccessLevel = AccessLevel.READ_WRITE,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Allocate a new session or get existing one

        Args:
            session_id: Optional session ID (generated if not provided)
            sandbox_id: Sandbox identifier
            ttl: Time to live in seconds
            access_level: Access level for the session
            user_id: Optional user identifier
            metadata: Optional session metadata

        Returns:
            Session ID
        """
        async with self._lock:
            # Use provided session_id or generate new one
            if not session_id:
                session_id = (
                    f"sess-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:8]}"
                )

            # Return existing session if found
            if session_id in self.sessions:
                session = self.sessions[session_id]
                if session.is_active():
                    return session_id
                else:
                    # Remove expired session
                    del self.sessions[session_id]

            # Check max sessions limit
            if len(self.sessions) >= self.max_sessions:
                # Try to clean up expired sessions first
                await self.cleanup_expired_sessions()

                if len(self.sessions) >= self.max_sessions:
                    raise RuntimeError(
                        f"Maximum number of sessions ({self.max_sessions}) reached"
                    )

            # Calculate expiry
            ttl = ttl or self.default_ttl
            expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else None

            # Create new session
            session = Session(
                session_id=session_id,
                sandbox_id=sandbox_id,
                expires_at=expires_at,
                access_level=access_level,
                user_id=user_id,
                metadata=metadata or {},
            )

            self.sessions[session_id] = session
            self.stats["total_sessions_created"] += 1

            logger.info(f"Allocated session: {session_id} for sandbox: {sandbox_id}")

            return session_id

    async def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if session and session.is_active():
                return session
            return None

    async def terminate_session(self, session_id: str) -> bool:
        """Terminate a session"""
        async with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].state = SessionState.TERMINATED
                del self.sessions[session_id]
                self.stats["total_sessions_terminated"] += 1
                logger.info(f"Terminated session: {session_id}")
                return True
            return False

    async def suspend_session(self, session_id: str) -> bool:
        """Suspend a session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.state = SessionState.SUSPENDED
                logger.info(f"Suspended session: {session_id}")
                return True
            return False

    async def resume_session(self, session_id: str) -> bool:
        """Resume a suspended session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if session and session.state == SessionState.SUSPENDED:
                if not session.is_expired():
                    session.state = SessionState.ACTIVE
                    logger.info(f"Resumed session: {session_id}")
                    return True
            return False

    async def validate_access(
        self, session_id: str, path: str, operation: str = "read"
    ) -> bool:
        """
        Validate session access to a path

        Args:
            session_id: Session ID
            path: Path to validate
            operation: Operation type (read, write, delete)

        Returns:
            True if access is allowed
        """
        session = await self.get_session(session_id)
        if not session:
            self.stats["access_denied_count"] += 1
            return False

        # Check operation permissions
        if operation == "read":
            allowed = session.can_read(path)
        elif operation in ["write", "create"]:
            allowed = session.can_write(path)
        elif operation == "delete":
            allowed = session.can_delete(path)
        else:
            allowed = False

        if allowed:
            session.update_stats(operation)
            self.stats["total_operations"] += 1
        else:
            self.stats["access_denied_count"] += 1
            logger.warning(
                f"Access denied for session {session_id}: {operation} on {path}"
            )

        return allowed

    async def set_allowed_paths(self, session_id: str, paths: list[str]) -> bool:
        """Set allowed paths for a session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.allowed_paths = set(paths)
                return True
            return False

    async def add_allowed_path(self, session_id: str, path: str) -> bool:
        """Add an allowed path for a session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.allowed_paths.add(path)
                return True
            return False

    async def set_denied_paths(self, session_id: str, paths: list[str]) -> bool:
        """Set denied paths for a session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.denied_paths = set(paths)
                return True
            return False

    async def add_denied_path(self, session_id: str, path: str) -> bool:
        """Add a denied path for a session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.denied_paths.add(path)
                return True
            return False

    async def list_sessions(
        self,
        sandbox_id: str | None = None,
        user_id: str | None = None,
        active_only: bool = True,
    ) -> list[str]:
        """List sessions matching criteria"""
        async with self._lock:
            sessions = []

            for session_id, session in self.sessions.items():
                # Filter by active state
                if active_only and not session.is_active():
                    continue

                # Filter by sandbox
                if sandbox_id and session.sandbox_id != sandbox_id:
                    continue

                # Filter by user
                if user_id and session.user_id != user_id:
                    continue

                sessions.append(session_id)

            return sessions

    async def get_session_stats(self, session_id: str) -> dict[str, Any] | None:
        """Get statistics for a session"""
        session = await self.get_session(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "sandbox_id": session.sandbox_id,
            "state": session.state.value,
            "access_level": session.access_level.value,
            "created_at": session.created_at.isoformat(),
            "expires_at": (
                session.expires_at.isoformat() if session.expires_at else None
            ),
            "operations_count": session.operations_count,
            "bytes_read": session.bytes_read,
            "bytes_written": session.bytes_written,
            "files_created": session.files_created,
            "files_deleted": session.files_deleted,
        }

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        async with self._lock:
            expired = []

            for session_id, session in self.sessions.items():
                if session.is_expired():
                    expired.append(session_id)

            for session_id in expired:
                del self.sessions[session_id]
                self.stats["total_sessions_expired"] += 1

            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")

            return len(expired)

    def get_stats(self) -> dict[str, Any]:
        """Get session manager statistics"""
        return {
            **self.stats,
            "active_sessions": len(self.sessions),
            "max_sessions": self.max_sessions,
        }
