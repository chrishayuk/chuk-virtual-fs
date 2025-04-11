"""
chuk_virtual_fs/providers/s3.py - AWS S3 storage provider

This version includes fixes for directory listing with prefixes
"""
import json
import time
import posixpath
import logging
from typing import Dict, List, Optional, Any

from chuk_virtual_fs.provider_base import StorageProvider
from chuk_virtual_fs.node_info import FSNodeInfo

# Configure logger
logger = logging.getLogger("s3-provider")

class S3StorageProvider(StorageProvider):
    """
    AWS S3 storage provider
    
    Requires boto3 package: pip install boto3
    """
    
    def __init__(self, bucket_name: str, prefix: str = "", 
                 aws_access_key_id: str = None, 
                 aws_secret_access_key: str = None,
                 region_name: str = None,
                 endpoint_url: str = None):
        """
        Initialize the S3 storage provider
        
        Args:
            bucket_name: S3 bucket name
            prefix: Optional prefix for all objects (like a folder)
            aws_access_key_id: AWS access key ID (can use AWS environment variables instead)
            aws_secret_access_key: AWS secret access key (can use AWS environment variables instead)
            region_name: AWS region name
            endpoint_url: Custom endpoint URL for S3-compatible services
        """
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip('/') if prefix else ""
        self.client = None
        self.resource = None
        
        # Save credentials for initialization
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.endpoint_url = endpoint_url
        
        # Cache for node info to reduce S3 requests
        self.node_cache = {}
        self.cache_ttl = 60  # seconds
        self.cache_timestamps = {}
        
        # Debug flag - set to True for detailed logging
        self.debug = True
        
    def _get_s3_key(self, path: str) -> str:
        """Convert filesystem path to S3 key"""
        if path == '/':
            if self.debug:
                logger.debug(f"_get_s3_key: Converting root path '/' with prefix '{self.prefix}'")
            if self.prefix:
                return f"{self.prefix}" 
            return "" 
            
        # Remove leading slash and add prefix
        clean_path = path[1:] if path.startswith('/') else path
        if self.prefix:
            result = f"{self.prefix}/{clean_path}"
        else:
            result = clean_path

        if self.debug:
            logger.debug(f"_get_s3_key: Converting path '{path}' -> '{result}'")
        return result
        
    def _get_node_key(self, path: str) -> str:
        """Get S3 key for node metadata"""
        key = f"{self._get_s3_key(path)}.node.json"
        if self.debug:
            logger.debug(f"_get_node_key: For path '{path}' -> '{key}'")
        return key
        
    def _get_content_key(self, path: str) -> str:
        """Get S3 key for file content"""
        key = self._get_s3_key(path)
        if self.debug:
            logger.debug(f"_get_content_key: For path '{path}' -> '{key}'")
        return key
        
    def initialize(self) -> bool:
        """Initialize the storage provider and connect to S3"""
        try:
            import boto3
            
            # Create session with credentials if provided
            session_kwargs = {}
            if self.aws_access_key_id and self.aws_secret_access_key:
                session_kwargs['aws_access_key_id'] = self.aws_access_key_id
                session_kwargs['aws_secret_access_key'] = self.aws_secret_access_key
                
            if self.region_name:
                session_kwargs['region_name'] = self.region_name
                
            session = boto3.Session(**session_kwargs)
            
            # Create S3 client and resource
            client_kwargs = {}
            if self.endpoint_url:
                client_kwargs['endpoint_url'] = self.endpoint_url
                
            self.client = session.client('s3', **client_kwargs)
            self.resource = session.resource('s3', **client_kwargs)
            
            # Check if bucket exists, create if not
            try:
                self.client.head_bucket(Bucket=self.bucket_name)
            except self.client.exceptions.NoSuchBucket:
                logger.debug(f"Creating bucket: {self.bucket_name}")
                self.client.create_bucket(Bucket=self.bucket_name)
                
            # Create root node if it doesn't exist
            root_key = self._get_node_key('/')
            try:
                self.client.head_object(Bucket=self.bucket_name, Key=root_key)
            except self.client.exceptions.ClientError:
                # Root doesn't exist, create it
                logger.debug(f"Creating root node at {root_key}")
                root_info = FSNodeInfo("", True)
                root_data = json.dumps(root_info.to_dict())
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=root_key,
                    Body=root_data
                )
                
            return True
        except ImportError:
            logger.error("Error: boto3 package is required for S3 storage provider")
            return False
        except Exception as e:
            logger.error(f"Error initializing S3 storage: {e}")
            return False
            
    def _check_cache(self, path: str) -> Optional[FSNodeInfo]:
        """Check if node info is in cache and still valid"""
        now = time.time()
        if path in self.node_cache and now - self.cache_timestamps.get(path, 0) < self.cache_ttl:
            if self.debug:
                logger.debug(f"Cache hit for path: {path}")
            return self.node_cache[path]
        if self.debug:
            logger.debug(f"Cache miss for path: {path}")
        return None
        
    def _update_cache(self, path: str, node_info: FSNodeInfo) -> None:
        """Update node info in cache"""
        self.node_cache[path] = node_info
        self.cache_timestamps[path] = time.time()
        if self.debug:
            logger.debug(f"Updated cache for path: {path}")
            
    def create_node(self, node_info: FSNodeInfo) -> bool:
        """Create a new node"""
        if not self.client:
            return False
            
        try:
            path = node_info.get_path()
            
            # Check if node already exists
            if self.get_node_info(path):
                if self.debug:
                    logger.debug(f"Node already exists at path: {path}")
                return False
                
            # Ensure parent exists
            parent_path = posixpath.dirname(path)
            if parent_path != path and not self.get_node_info(parent_path):
                if self.debug:
                    logger.debug(f"Parent doesn't exist for path: {path} (parent: {parent_path})")
                return False
                
            # Save node info
            node_key = self._get_node_key(path)
            node_data = json.dumps(node_info.to_dict())
            
            if self.debug:
                logger.debug(f"Creating node at key: {node_key} for path: {path}")
                
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=node_key,
                Body=node_data
            )
            
            # Initialize empty content for files
            if not node_info.is_dir:
                content_key = self._get_content_key(path)
                if self.debug:
                    logger.debug(f"Initializing file content at key: {content_key}")
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=content_key,
                    Body=""
                )
                
            # Update cache
            self._update_cache(path, node_info)
                
            return True
        except Exception as e:
            logger.error(f"Error creating node: {e}")
            return False
            
    def delete_node(self, path: str) -> bool:
        """Delete a node"""
        if not self.client:
            return False
            
        try:
            # Check if node exists
            node_info = self.get_node_info(path)
            if not node_info:
                if self.debug:
                    logger.debug(f"Node doesn't exist at path: {path}")
                return False
                
            # Check if directory is empty
            if node_info.is_dir:
                # List objects with prefix to see if directory has children
                prefix = self._get_s3_key(path)
                if not prefix.endswith('/'):
                    prefix += '/'
                    
                if self.debug:
                    logger.debug(f"Checking if directory is empty at prefix: {prefix}")
                    
                response = self.client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=prefix,
                    MaxKeys=2  # We only need to know if there's at least one child
                )
                
                # If directory has children (other than its own metadata)
                if 'Contents' in response and len(response['Contents']) > 1:
                    if self.debug:
                        logger.debug(f"Directory not empty at path: {path}")
                    return False
                    
            # Delete node metadata
            node_key = self._get_node_key(path)
            if self.debug:
                logger.debug(f"Deleting node metadata at key: {node_key}")
                
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=node_key
            )
            
            # Delete content if it's a file
            if not node_info.is_dir:
                content_key = self._get_content_key(path)
                if self.debug:
                    logger.debug(f"Deleting file content at key: {content_key}")
                    
                self.client.delete_object(
                    Bucket=self.bucket_name,
                    Key=content_key
                )
                
            # Remove from cache
            if path in self.node_cache:
                del self.node_cache[path]
                del self.cache_timestamps[path]
                if self.debug:
                    logger.debug(f"Removed path from cache: {path}")
                
            return True
        except Exception as e:
            logger.error(f"Error deleting node: {e}")
            return False
            
    def get_node_info(self, path: str) -> Optional[FSNodeInfo]:
        """Get information about a node"""
        if not self.client:
            return None
            
        # Normalize path
        if not path:
            path = "/"
        elif path != "/" and path.endswith("/"):
            path = path[:-1]
            
        if self.debug:
            logger.debug(f"get_node_info: normalized path '{path}'")
            
        # Check cache first
        cached = self._check_cache(path)
        if cached:
            return cached
            
        try:
            # Get node metadata from S3
            node_key = self._get_node_key(path)
            
            if self.debug:
                logger.debug(f"Looking for node metadata at key: {node_key}")
            
            try:
                response = self.client.get_object(
                    Bucket=self.bucket_name,
                    Key=node_key
                )
                
                node_data = json.loads(response['Body'].read().decode('utf-8'))
                node_info = FSNodeInfo.from_dict(node_data)
                
                # Update cache
                self._update_cache(path, node_info)
                
                if self.debug:
                    logger.debug(f"Found node info for path: {path}, is_dir={node_info.is_dir}")
                
                return node_info
            except self.client.exceptions.NoSuchKey:
                if self.debug:
                    logger.debug(f"No node info found at key: {node_key}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting node info: {e}")
            return None
            
    def list_directory(self, path: str) -> List[str]:
        """
        List contents of a directory.
        
        improved handling of prefixes and proper listing of files
        at the root directory even when using a prefix.
        """
        if not self.client:
            logger.warning("S3 client not initialized")
            return []
            
        # Normalize path
        if not path:
            path = "/"
        elif path != "/" and path.endswith("/"):
            path = path[:-1]
            
        logger.debug(f"list_directory: normalized path '{path}'")
            
        try:
            # Check if path is a directory
            node_info = self.get_node_info(path)
            if not node_info or not node_info.is_dir:
                logger.warning(f"Path '{path}' is not a directory or doesn't exist")
                return []
                
            # List objects with common prefix
            prefix = self._get_s3_key(path)
            
            # Important! For root directory, we need special handling
            if path == "/":
                # When listing root with a prefix, we need to list only items directly under the prefix
                if self.prefix:
                    prefix = f"{self.prefix}/"
                else:
                    prefix = ""
            else:
                # For non-root directories, ensure the prefix ends with a slash to list contents
                if not prefix.endswith('/'):
                    prefix += '/'
            
            logger.debug(f"Using prefix '{prefix}' for listing directory '{path}'")
                
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter='/'  # Use delimiter to get "folders"
            )
            
            results = []
            
            # Debug what's coming back from S3
            try:
                response = self.client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=prefix,
                    Delimiter='/'
                )
                logger.debug(f"S3 list response keys: {list(response.keys())}")
                if 'Contents' in response:
                    logger.debug(f"S3 list contains {len(response['Contents'])} objects")
                    for obj in response['Contents'][:5]:  # Log first 5 items
                        logger.debug(f" - Content key: {obj['Key']}")
                if 'CommonPrefixes' in response:
                    logger.debug(f"S3 list contains {len(response['CommonPrefixes'])} common prefixes")
                    for pfx in response['CommonPrefixes'][:5]:  # Log first 5 items
                        logger.debug(f" - Common prefix: {pfx['Prefix']}")
            except Exception as debug_e:
                logger.warning(f"Debug listing failed: {debug_e}")
            
            # Process all pages
            for page in pages:
                # Process files (direct children only)
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        logger.debug(f"Processing key: {key}")
                        
                        # Skip node metadata files and non-direct children
                        if key.endswith('.node.json'):
                            logger.debug(f"Skipping metadata file: {key}")
                            continue
                            
                        # Skip keys that are the same as the prefix (directory marker)
                        if key == prefix:
                            logger.debug(f"Skipping directory marker: {key}")
                            continue
                            
                        # Extract name from key
                        if prefix:
                            name = key[len(prefix):]
                        else:
                            name = key
                            
                        logger.debug(f"Extracted name: '{name}' from key: '{key}' with prefix: '{prefix}'")
                            
                        # Skip empty names and names with path separators (not direct children)
                        if name and '/' not in name:
                            logger.debug(f"Adding file: {name}")
                            results.append(name)
                        elif name and '/' in name:
                            logger.debug(f"Skipping indirect child: {name}")
                
                # Process "folders" (common prefixes)
                if 'CommonPrefixes' in page:
                    for common_prefix in page['CommonPrefixes']:
                        prefix_value = common_prefix['Prefix']
                        logger.debug(f"Processing common prefix: {prefix_value}")
                        
                        # Extract name from prefix
                        if prefix:
                            name = prefix_value[len(prefix):]
                        else:
                            name = prefix_value
                            
                        logger.debug(f"Extracted directory name: '{name}' from prefix: '{prefix_value}'")
                            
                        # Remove trailing slash and add to results
                        if name.endswith('/'):
                            name = name[:-1]
                            
                        if name:
                            logger.debug(f"Adding directory: {name}")
                            results.append(name)
            
            logger.debug(f"Final results for directory '{path}': {results}")
            return results
                
        except Exception as e:
            logger.error(f"Error listing directory '{path}': {e}", exc_info=True)
            return []
            
    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file"""
        if not self.client:
            return False
            
        try:
            # Check if path exists and is a file
            node_info = self.get_node_info(path)
            if not node_info or node_info.is_dir:
                if self.debug:
                    if not node_info:
                        logger.debug(f"No node found at path: {path}")
                    else:
                        logger.debug(f"Cannot write to a directory: {path}")
                return False
                
            # Update content
            content_key = self._get_content_key(path)
            if self.debug:
                logger.debug(f"Writing content to key: {content_key}")
                
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=content_key,
                Body=content
            )
            
            # Update modification time
            node_info.modified_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            node_key = self._get_node_key(path)
            
            if self.debug:
                logger.debug(f"Updating metadata at key: {node_key}")
                
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=node_key,
                Body=json.dumps(node_info.to_dict())
            )
            
            # Update cache
            self._update_cache(path, node_info)
            
            if self.debug:
                logger.debug(f"Successfully wrote content to path: {path}")
            
            return True
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return False
            
    def read_file(self, path: str) -> Optional[str]:
        """Read content from a file"""
        if not self.client:
            return None
            
        try:
            # Check if path exists and is a file
            node_info = self.get_node_info(path)
            if not node_info or node_info.is_dir:
                if self.debug:
                    if not node_info:
                        logger.debug(f"No node found at path: {path}")
                    else:
                        logger.debug(f"Cannot read from a directory: {path}")
                return None
                
            # Get content
            content_key = self._get_content_key(path)
            
            if self.debug:
                logger.debug(f"Reading content from key: {content_key}")
            
            try:
                response = self.client.get_object(
                    Bucket=self.bucket_name,
                    Key=content_key
                )
                
                content = response['Body'].read().decode('utf-8')
                if self.debug:
                    logger.debug(f"Successfully read content from path: {path} (length: {len(content)})")
                return content
            except self.client.exceptions.NoSuchKey:
                if self.debug:
                    logger.debug(f"No content found at key: {content_key}")
                return ""
                
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return None
    
    def rm(self, path: str) -> bool:
        """
        Remove a file from the filesystem.
        
        Args:
            path: Path to the file to remove
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.warning("S3 client not initialized")
            return False
            
        try:
            # Check if path exists
            node_info = self.get_node_info(path)
            if not node_info:
                logger.warning(f"Path does not exist: {path}")
                return False
                
            # Don't allow removing directories with this method
            if node_info.is_dir:
                logger.warning(f"Cannot use rm() on a directory: {path}")
                return False
                
            # Get the S3 keys for this file
            content_key = self._get_content_key(path)
            node_key = self._get_node_key(path)
            
            logger.info(f"Removing file at path: {path}")
            logger.debug(f"Deleting content at key: {content_key}")
            logger.debug(f"Deleting metadata at key: {node_key}")
            
            # Delete both the content and metadata objects
            success = True
            
            # Delete the node metadata first
            try:
                self.client.delete_object(
                    Bucket=self.bucket_name,
                    Key=node_key
                )
                logger.debug(f"Deleted metadata key: {node_key}")
            except Exception as e:
                logger.error(f"Error deleting metadata: {e}")
                success = False
                
            # Delete the content
            try:
                self.client.delete_object(
                    Bucket=self.bucket_name,
                    Key=content_key
                )
                logger.debug(f"Deleted content key: {content_key}")
            except Exception as e:
                logger.error(f"Error deleting content: {e}")
                success = False
                
            # Remove from cache
            if path in self.node_cache:
                del self.node_cache[path]
                if path in self.cache_timestamps:
                    del self.cache_timestamps[path]
                logger.debug(f"Removed path from cache: {path}")
                
            # Verify deletion if debugging is enabled
            if self.debug:
                try:
                    exists = False
                    try:
                        self.client.head_object(Bucket=self.bucket_name, Key=content_key)
                        exists = True
                        logger.warning(f"Content still exists after deletion: {content_key}")
                    except:
                        logger.debug(f"Content successfully deleted: {content_key}")
                        
                    try:
                        self.client.head_object(Bucket=self.bucket_name, Key=node_key)
                        exists = True
                        logger.warning(f"Metadata still exists after deletion: {node_key}")
                    except:
                        logger.debug(f"Metadata successfully deleted: {node_key}")
                        
                    if exists:
                        logger.warning("File not completely deleted!")
                    else:
                        logger.debug("File successfully deleted")
                except Exception as e:
                    logger.error(f"Error verifying deletion: {e}")
                
            return success
        except Exception as e:
            logger.error(f"Error in rm operation for path {path}: {e}")
            return False
            
    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        if not self.client:
            return {"error": "S3 client not initialized"}
            
        try:
            # Use prefix if specified
            prefix = self.prefix if self.prefix else "" 
            
            if self.debug:
                logger.debug(f"Getting storage stats with prefix: {prefix}")
            
            # Count objects and get size
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            total_size = 0
            object_count = 0
            file_count = 0
            dir_count = 0
            
            # Process all pages
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        object_count += 1
                        total_size += obj['Size']
                        
                        # Count files and directories
                        if obj['Key'].endswith('.node.json'):
                            # Check if it's a directory
                            try:
                                response = self.client.get_object(
                                    Bucket=self.bucket_name,
                                    Key=obj['Key']
                                )
                                
                                node_data = json.loads(response['Body'].read().decode('utf-8'))
                                if node_data.get('is_dir', False):
                                    dir_count += 1
                                else:
                                    file_count += 1
                            except:
                                # Count as file if we can't determine
                                file_count += 1
                        
            stats = {
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "file_count": file_count,
                "directory_count": dir_count,
                "object_count": object_count
            }
            
            if self.debug:
                logger.debug(f"Storage stats: {stats}")
                
            return stats
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {"error": str(e)}
            
    def cleanup(self) -> Dict:
        """Perform cleanup operations"""
        if not self.client:
            return {"error": "S3 client not initialized"}
            
        try:
            # Get prefix for tmp directory
            tmp_prefix = f"{self.prefix}/tmp" if self.prefix else "tmp"
            if not tmp_prefix.endswith('/'):
                tmp_prefix += '/'
                
            if self.debug:
                logger.debug(f"Cleaning up temporary files with prefix: {tmp_prefix}")
                
            # List objects to delete
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=tmp_prefix
            )
            
            total_size = 0
            deleted_count = 0
            
            # Process all pages
            for page in pages:
                if 'Contents' in page:
                    # Collect objects to delete
                    delete_keys = []
                    for obj in page['Contents']:
                        delete_keys.append({'Key': obj['Key']})
                        total_size += obj['Size']
                        deleted_count += 1
                        
                    # Delete objects in batches
                    if delete_keys:
                        if self.debug:
                            logger.debug(f"Deleting {len(delete_keys)} objects")
                            
                        self.client.delete_objects(
                            Bucket=self.bucket_name,
                            Delete={'Objects': delete_keys}
                        )
                        
                        # Clear related cache entries
                        for key in delete_keys:
                            s3_key = key['Key']
                            # Convert S3 key back to path
                            if s3_key.endswith('.node.json'):
                                path_key = s3_key[:-10]  # Remove .node.json
                                if self.prefix and path_key.startswith(self.prefix + '/'):
                                    path = '/' + path_key[len(self.prefix) + 1:]
                                else:
                                    path = '/' + path_key
                                    
                                if path in self.node_cache:
                                    del self.node_cache[path]
                                    del self.cache_timestamps[path]
                                    
                                    if self.debug:
                                        logger.debug(f"Removed path from cache: {path}")
            
            result = {
                "bytes_freed": total_size,
                "files_removed": deleted_count
            }
            
            if self.debug:
                logger.debug(f"Cleanup result: {result}")
                
            return result
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {"error": str(e)}