"""
chuk_virtual_fs/providers/s3_clean.py - Clean S3 storage provider

This version stores files as regular S3 objects without special suffixes.
Directories are represented by zero-byte objects with trailing slashes.
"""

import logging
import posixpath
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from chuk_virtual_fs.node_info import EnhancedNodeInfo
from chuk_virtual_fs.provider_base import AsyncStorageProvider

# Configure logger
logger = logging.getLogger("s3-provider")


class S3StorageProvider(AsyncStorageProvider):
    """
    Clean S3 storage provider using aioboto3

    - Files are stored as regular S3 objects
    - Directories are zero-byte objects with trailing '/'
    - Metadata is stored in S3 object metadata/tags
    """

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "",
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        region_name: str = None,
        endpoint_url: str = None,
        signature_version: str = None,
    ):
        """
        Initialize the S3 storage provider

        Args:
            bucket_name: S3 bucket name
            prefix: Optional prefix for all objects (like a folder)
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            region_name: AWS region name
            endpoint_url: Custom endpoint URL for S3-compatible services
            signature_version: S3 signature version
        """
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip("/") if prefix else ""
        self.session = None

        # Save credentials for initialization
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name or "us-east-1"
        self.endpoint_url = endpoint_url
        self.signature_version = signature_version

        # Cache for performance
        self._cache = {}
        self._cache_ttl = 60  # 1 minute cache

        logger.info(
            f"Initialized S3 provider for bucket: {bucket_name}, prefix: {prefix}"
        )

    async def initialize(self):
        """Initialize the async S3 client"""
        try:
            import aioboto3
        except ImportError:
            raise ImportError(  # noqa: B904
                "aioboto3 is required. Install with: pip install aioboto3"
            )

        # Create session
        session_kwargs = {}
        if self.aws_access_key_id:
            session_kwargs["aws_access_key_id"] = self.aws_access_key_id
        if self.aws_secret_access_key:
            session_kwargs["aws_secret_access_key"] = self.aws_secret_access_key
        if self.region_name:
            session_kwargs["region_name"] = self.region_name

        self.session = aioboto3.Session(**session_kwargs)

        # Test connection
        async with self._get_client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"Successfully connected to S3 bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to connect to S3 bucket: {e}")
                raise

    @asynccontextmanager
    async def _get_client(self):
        """Get an async S3 client"""
        client_kwargs = {}
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        if self.signature_version:
            client_kwargs["config"] = {"signature_version": self.signature_version}

        async with self.session.client("s3", **client_kwargs) as client:
            yield client

    def _get_s3_key(self, path: str) -> str:
        """Convert virtual path to S3 key"""
        # Normalize path
        if not path.startswith("/"):
            path = "/" + path

        # Remove leading slash for S3
        path = path.lstrip("/")

        # Add prefix if configured
        if self.prefix:
            if path:
                return f"{self.prefix}/{path}"
            return self.prefix
        return path

    def _path_from_s3_key(self, s3_key: str) -> str:
        """Convert S3 key back to virtual path"""
        # Remove prefix if present
        if self.prefix:
            if s3_key.startswith(self.prefix + "/"):
                s3_key = s3_key[len(self.prefix) + 1 :]
            elif s3_key == self.prefix:
                return "/"

        # Ensure path starts with /
        if not s3_key.startswith("/"):
            s3_key = "/" + s3_key

        return s3_key

    def _is_directory_key(self, key: str) -> bool:
        """Check if an S3 key represents a directory"""
        return key.endswith("/")

    def _cache_get(self, key: str) -> Any | None:
        """Get from cache if not expired"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return value
            del self._cache[key]
        return None

    def _cache_set(self, key: str, value: Any):
        """Set in cache with timestamp"""
        self._cache[key] = (value, time.time())

    def _cache_clear(self, pattern: str = None):
        """Clear cache entries"""
        if pattern:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for k in keys_to_delete:
                del self._cache[k]
        else:
            self._cache.clear()

    async def create_directory(
        self, path: str, mode: int = 0o755, owner_id: int = 1000, group_id: int = 1000
    ) -> bool:
        """Create a directory"""
        # In S3, we create a zero-byte object with a trailing slash to represent a directory
        # This ensures the directory appears in listings even when empty
        try:
            # Ensure path ends with /
            if not path.endswith("/"):
                path = path + "/"

            # Create parent directories if needed
            path_parts = path.strip("/").split("/")
            async with self._get_client() as client:
                # Create all parent directories
                for i in range(len(path_parts)):
                    parent_path = "/".join(path_parts[: i + 1]) + "/"
                    parent_key = self._get_s3_key(parent_path)

                    # Check if parent already exists
                    try:
                        await client.head_object(
                            Bucket=self.bucket_name, Key=parent_key
                        )
                        # Already exists, skip
                        continue
                    except:  # noqa: E722
                        # Doesn't exist, create it
                        pass

                    # Create directory marker with metadata
                    await client.put_object(
                        Bucket=self.bucket_name,
                        Key=parent_key,
                        Body=b"",
                        ContentType="application/x-directory",
                        Metadata={
                            "type": "directory",
                            "mode": str(mode),
                            "owner": str(owner_id),
                            "group": str(group_id),
                        },
                    )
                    logger.debug(f"Created directory marker for {parent_path}")

            self._cache_clear(path)
            return True

        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            return False

    async def create_node(self, node_info: EnhancedNodeInfo) -> bool:
        """Create a new node"""
        path = node_info.get_path()

        if node_info.is_dir:
            return await self.create_directory(
                path,
                mode=int(node_info.permissions, 8) if node_info.permissions else 0o755,
                owner_id=int(node_info.owner) if node_info.owner else 1000,
                group_id=int(node_info.group) if node_info.group else 1000,
            )
        else:
            # For files, create with empty content
            return await self.write_file(path, b"")

    async def delete_node(self, path: str) -> bool:
        """Delete a node"""
        try:
            # Check if it's a directory
            is_dir = path.endswith("/") or await self._is_directory(path)

            if is_dir:
                # Ensure path ends with /
                if not path.endswith("/"):
                    path = path + "/"

                # Check if directory is empty
                contents = await self.list_directory(path)
                if contents:
                    logger.warning(f"Cannot delete non-empty directory: {path}")
                    return False

            s3_key = self._get_s3_key(path)

            async with self._get_client() as client:
                await client.delete_object(Bucket=self.bucket_name, Key=s3_key)

            self._cache_clear(path)
            return True

        except Exception as e:
            logger.error(f"Error deleting node: {e}")
            return False

    async def _is_directory(self, path: str) -> bool:
        """Check if a path is a directory"""
        # A path is a directory if:
        # 1. There are objects with this path as a prefix
        # 2. The path itself doesn't exist as a file

        # First check if it's a file
        s3_key = self._get_s3_key(path)
        try:
            async with self._get_client() as client:
                response = await client.head_object(Bucket=self.bucket_name, Key=s3_key)
                # If it exists as an object and is not marked as directory, it's a file
                metadata = response.get("Metadata", {})
                if metadata.get("type") != "directory":
                    return False
        except:  # noqa: E722
            pass

        # Check if there are any objects with this prefix
        if not path.endswith("/"):
            path = path + "/"

        dir_prefix = self._get_s3_key(path)

        try:
            async with self._get_client() as client:
                response = await client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix=dir_prefix, MaxKeys=1
                )
                return response.get("KeyCount", 0) > 0
        except:  # noqa: E722
            return False

    async def get_node_info(self, path: str) -> EnhancedNodeInfo | None:
        """Get information about a node"""
        # Check cache
        cached = self._cache_get(f"info:{path}")
        if cached:
            return cached

        try:
            # Try to get info as a file first
            s3_key = self._get_s3_key(path)

            try:
                async with self._get_client() as client:
                    response = await client.head_object(
                        Bucket=self.bucket_name, Key=s3_key
                    )

                    metadata = response.get("Metadata", {})

                    node_info = EnhancedNodeInfo(
                        name=posixpath.basename(path),
                        is_dir=False,
                        parent_path=posixpath.dirname(path),
                        size=response.get("ContentLength", 0),
                        permissions=metadata.get("permissions", "644"),
                        owner=metadata.get("owner", "1000"),
                        group=metadata.get("group", "1000"),
                        modified_at=(
                            response.get("LastModified", datetime.utcnow()).isoformat()
                            if hasattr(response.get("LastModified"), "isoformat")
                            else str(response.get("LastModified"))
                        ),
                        mime_type=response.get(
                            "ContentType", "application/octet-stream"
                        ),
                    )

                    self._cache_set(f"info:{path}", node_info)
                    return node_info
            except:  # noqa: E722
                pass

            # Check if it's a directory (by checking for objects with this prefix)
            if await self._is_directory(path):
                node_info = EnhancedNodeInfo(
                    name=posixpath.basename(path.rstrip("/")),
                    is_dir=True,
                    parent_path=posixpath.dirname(path.rstrip("/")),
                    size=0,
                    permissions="755",
                    owner="1000",
                    group="1000",
                    modified_at=datetime.utcnow().isoformat(),
                    mime_type="application/x-directory",
                )

                self._cache_set(f"info:{path}", node_info)
                return node_info

        except Exception as e:
            logger.debug(f"Error getting node info for {path}: {e}")

        return None

    async def list_directory(self, path: str) -> list[str]:
        """List contents of a directory"""
        # Normalize path
        if not path.endswith("/"):
            path = path + "/"

        # Check cache
        cached = self._cache_get(f"list:{path}")
        if cached is not None:
            return cached

        try:
            # Special handling for root path
            if path == "/":
                s3_prefix = self.prefix + "/" if self.prefix else ""
            else:
                s3_prefix = self._get_s3_key(path)

            # Use delimiter to get only direct children
            items = []

            async with self._get_client() as client:
                paginator = client.get_paginator("list_objects_v2")

                paginator_kwargs = {"Bucket": self.bucket_name, "Delimiter": "/"}

                # Only add Prefix if it's not empty
                if s3_prefix:
                    paginator_kwargs["Prefix"] = s3_prefix

                async for page in paginator.paginate(**paginator_kwargs):
                    # Process files (objects)
                    for obj in page.get("Contents", []):
                        key = obj["Key"]

                        # Skip the directory marker itself
                        if key == s3_prefix:
                            continue

                        # Extract the name
                        name = key[len(s3_prefix) :] if s3_prefix else key

                        # Skip if not a direct child
                        if "/" in name.rstrip("/"):
                            continue

                        # Remove trailing slash for display
                        name = name.rstrip("/")

                        if name:
                            items.append(name)

                    # Process subdirectories (common prefixes)
                    for prefix_info in page.get("CommonPrefixes", []):
                        prefix = prefix_info["Prefix"]

                        # Extract directory name
                        name = prefix[len(s3_prefix) :] if s3_prefix else prefix

                        # Remove trailing slash
                        name = name.rstrip("/")

                        if name:
                            items.append(name)

            result = sorted(set(items))
            self._cache_set(f"list:{path}", result)
            return result

        except Exception as e:
            logger.error(f"Error listing directory: {e}")
            return []

    async def read_file(self, path: str) -> bytes:
        """Read file content"""
        try:
            s3_key = self._get_s3_key(path)

            async with self._get_client() as client:
                response = await client.get_object(Bucket=self.bucket_name, Key=s3_key)

                content = await response["Body"].read()
                return content

        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            raise FileNotFoundError(f"File not found: {path}")  # noqa: B904

    async def write_file(
        self,
        path: str,
        content: bytes,
        mode: int = 0o644,
        owner_id: int = 1000,
        group_id: int = 1000,
    ) -> bool:
        """Write file content"""
        try:
            s3_key = self._get_s3_key(path)

            # Determine content type
            content_type = "application/octet-stream"
            if path.endswith(".json"):
                content_type = "application/json"
            elif path.endswith(".txt"):
                content_type = "text/plain"
            elif path.endswith(".html"):
                content_type = "text/html"
            elif path.endswith(".csv"):
                content_type = "text/csv"
            elif path.endswith(".log"):
                content_type = "text/plain"

            async with self._get_client() as client:
                await client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=content,
                    ContentType=content_type,
                    Metadata={
                        "type": "file",
                        "permissions": oct(mode)[2:],
                        "owner": str(owner_id),
                        "group": str(group_id),
                        "modified": datetime.utcnow().isoformat(),
                    },
                )

            # Clear cache for the file and its parent directory listing
            self._cache_clear(path)
            parent_dir = posixpath.dirname(path)
            if parent_dir and parent_dir != "/":
                self._cache_clear(f"list:{parent_dir}/")
            else:
                self._cache_clear("list:/")
            return True

        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return False

    async def copy_node(self, src_path: str, dst_path: str) -> bool:
        """Copy a node to a new location"""
        try:
            # Check if source is a directory
            is_dir = await self._is_directory(src_path)

            if is_dir:
                # Create destination directory
                if not await self.create_directory(dst_path):
                    return False

                # Copy contents recursively
                contents = await self.list_directory(src_path)
                for item in contents:
                    src_child = posixpath.join(src_path, item)
                    dst_child = posixpath.join(dst_path, item)
                    if not await self.copy_node(src_child, dst_child):
                        return False
            else:
                # Copy file
                src_key = self._get_s3_key(src_path)
                dst_key = self._get_s3_key(dst_path)

                copy_source = {"Bucket": self.bucket_name, "Key": src_key}

                async with self._get_client() as client:
                    await client.copy_object(
                        CopySource=copy_source, Bucket=self.bucket_name, Key=dst_key
                    )

            self._cache_clear(dst_path)
            return True

        except Exception as e:
            logger.error(f"Error copying node: {e}")
            return False

    async def move_node(self, src_path: str, dst_path: str) -> bool:
        """Move a node to a new location"""
        if await self.copy_node(src_path, dst_path):
            return await self.delete_node(src_path)
        return False

    async def exists(self, path: str) -> bool:
        """Check if a path exists"""
        # Try as file first
        s3_key = self._get_s3_key(path)

        try:
            async with self._get_client() as client:
                await client.head_object(Bucket=self.bucket_name, Key=s3_key)
                return True
        except:  # noqa: E722
            pass

        # Check if it's a directory by looking for objects with this prefix
        if not path.endswith("/"):
            path = path + "/"

        dir_prefix = self._get_s3_key(path)

        try:
            async with self._get_client() as client:
                response = await client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix=dir_prefix, MaxKeys=1
                )
                # Directory exists if there are any objects with this prefix
                return response.get("KeyCount", 0) > 0
        except:  # noqa: E722
            pass

        return False

    async def get_metadata(self, path: str) -> dict[str, Any] | None:
        """Get S3 object metadata"""
        try:
            s3_key = self._get_s3_key(path)

            async with self._get_client() as client:
                response = await client.head_object(Bucket=self.bucket_name, Key=s3_key)

                return {
                    "ContentType": response.get("ContentType"),
                    "ContentLength": response.get("ContentLength"),
                    "LastModified": str(response.get("LastModified")),
                    "ETag": response.get("ETag"),
                    "Metadata": response.get("Metadata", {}),
                }

        except Exception as e:
            logger.error(f"Error getting metadata: {e}")
            return None

    async def set_metadata(self, path: str, metadata: dict[str, str]) -> bool:
        """Set S3 object metadata"""
        try:
            s3_key = self._get_s3_key(path)

            # Get current object
            async with self._get_client() as client:
                response = await client.get_object(Bucket=self.bucket_name, Key=s3_key)

                body = await response["Body"].read()
                content_type = response.get("ContentType", "application/octet-stream")

                # Re-upload with new metadata
                await client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=body,
                    ContentType=content_type,
                    Metadata=metadata,
                )

                return True

        except Exception as e:
            logger.error(f"Error setting metadata: {e}")
            return False

    async def generate_presigned_url(
        self, path: str, expires_in: int = 3600
    ) -> str | None:
        """Generate a presigned URL for an S3 object"""
        try:
            s3_key = self._get_s3_key(path)

            async with self._get_client() as client:
                url = await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": s3_key},
                    ExpiresIn=expires_in,
                )

                return url

        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None

    async def get_storage_stats(self) -> dict:
        """Get storage statistics"""
        try:
            total_size = 0
            file_count = 0
            dir_count = 0

            prefix = self._get_s3_key("/")

            async with self._get_client() as client:
                paginator = client.get_paginator("list_objects_v2")

                async for page in paginator.paginate(
                    Bucket=self.bucket_name, Prefix=prefix if prefix else None
                ):
                    for obj in page.get("Contents", []):
                        key = obj["Key"]
                        size = obj.get("Size", 0)

                        if key.endswith("/"):
                            dir_count += 1
                        else:
                            file_count += 1
                            total_size += size

            return {
                "total_size": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "total_size_bytes": total_size,
                "file_count": file_count,
                "directory_count": dir_count,
                "bucket": self.bucket_name,
                "prefix": self.prefix or "/",
            }

        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {
                "total_size": 0,
                "file_count": 0,
                "directory_count": 0,
                "error": str(e),
            }

    async def cleanup(self) -> dict:
        """Perform cleanup operations"""
        stats = {"cache_entries_cleared": len(self._cache), "status": "success"}
        self._cache.clear()
        return stats

    async def close(self):
        """Close the S3 connection"""
        self._cache.clear()
        logger.info("S3 provider closed")

    # === Batch Operations ===

    async def batch_write(self, operations: list[tuple[str, bytes]]) -> list[bool]:
        """Write multiple files in parallel"""
        import asyncio

        tasks = []
        for path, content in operations:
            tasks.append(self.write_file(path, content))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to False
        return [result if isinstance(result, bool) else False for result in results]

    async def batch_read(self, paths: list[str]) -> list[bytes | None]:
        """Read multiple files in parallel"""
        import asyncio

        tasks = []
        for path in paths:
            tasks.append(self.read_file(path))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to None
        return [result if isinstance(result, bytes) else None for result in results]

    async def batch_delete(self, paths: list[str]) -> list[bool]:
        """Delete multiple nodes in parallel"""
        import asyncio

        tasks = []
        for path in paths:
            tasks.append(self.delete_node(path))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to False
        return [result if isinstance(result, bool) else False for result in results]

    async def batch_create(self, nodes: list[EnhancedNodeInfo]) -> list[bool]:
        """Create multiple nodes in parallel"""
        import asyncio

        tasks = []
        for node in nodes:
            tasks.append(self.create_node(node))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to False
        return [result if isinstance(result, bool) else False for result in results]

    # === Additional Features ===

    async def calculate_checksum(
        self, content: bytes, algorithm: str = "sha256"
    ) -> str:
        """Calculate checksum of content"""
        import hashlib

        if algorithm == "md5":
            return hashlib.md5(content, usedforsecurity=False).hexdigest()  # nosec B324
        elif algorithm == "sha1":
            return hashlib.sha1(content, usedforsecurity=False).hexdigest()  # nosec B324
        elif algorithm == "sha256":
            return hashlib.sha256(content).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    async def generate_presigned_upload_url(
        self, path: str, expires_in: int = 3600, content_type: str = None
    ) -> dict[str, Any] | None:
        """Generate presigned URL for direct upload"""
        try:
            s3_key = self._get_s3_key(path)

            params = {"Bucket": self.bucket_name, "Key": s3_key}

            if content_type:
                params["ContentType"] = content_type

            async with self._get_client() as client:
                # Generate presigned POST URL
                response = await client.generate_presigned_post(
                    Bucket=self.bucket_name, Key=s3_key, ExpiresIn=expires_in
                )

                return response

        except Exception as e:
            logger.error(f"Error generating presigned upload URL: {e}")
            return None

    async def list_versions(self, path: str) -> list[dict[str, Any]]:
        """List all versions of an S3 object (if versioning is enabled)"""
        try:
            s3_key = self._get_s3_key(path)
            versions = []

            async with self._get_client() as client:
                paginator = client.get_paginator("list_object_versions")

                async for page in paginator.paginate(
                    Bucket=self.bucket_name, Prefix=s3_key
                ):
                    for version in page.get("Versions", []):
                        if version["Key"] == s3_key:
                            versions.append(
                                {
                                    "version_id": version.get("VersionId"),
                                    "last_modified": str(version.get("LastModified")),
                                    "size": version.get("Size"),
                                    "is_latest": version.get("IsLatest", False),
                                }
                            )

            return versions

        except Exception as e:
            logger.error(f"Error listing versions: {e}")
            return []

    async def get_object_tags(self, path: str) -> dict[str, str]:
        """Get S3 object tags"""
        try:
            s3_key = self._get_s3_key(path)

            async with self._get_client() as client:
                response = await client.get_object_tagging(
                    Bucket=self.bucket_name, Key=s3_key
                )

                tags = {}
                for tag in response.get("TagSet", []):
                    tags[tag["Key"]] = tag["Value"]

                return tags

        except Exception as e:
            logger.error(f"Error getting object tags: {e}")
            return {}

    async def set_object_tags(self, path: str, tags: dict[str, str]) -> bool:
        """Set S3 object tags"""
        try:
            s3_key = self._get_s3_key(path)

            tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]

            async with self._get_client() as client:
                await client.put_object_tagging(
                    Bucket=self.bucket_name, Key=s3_key, Tagging={"TagSet": tag_set}
                )

                return True

        except Exception as e:
            logger.error(f"Error setting object tags: {e}")
            return False
