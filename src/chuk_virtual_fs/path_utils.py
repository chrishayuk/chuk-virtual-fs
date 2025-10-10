"""
chuk_virtual_fs/path_utils.py - Path utility functions for virtual filesystem

Provides a comprehensive set of path manipulation utilities similar to os.path
but designed for the virtual filesystem.
"""

import posixpath


def normalize(path: str) -> str:
    """
    Normalize a path by removing redundant separators and resolving . and ..

    Args:
        path: Path to normalize

    Returns:
        Normalized path

    Examples:
        >>> normalize("/home//user/../john/./docs")
        '/home/john/docs'
    """
    return posixpath.normpath(path)


def join(*paths: str) -> str:
    """
    Join one or more path components intelligently

    Args:
        *paths: Path components to join

    Returns:
        Joined path

    Examples:
        >>> join("/home", "user", "docs")
        '/home/user/docs'
        >>> join("/home/user", "../other")
        '/home/other'
    """
    return posixpath.normpath(posixpath.join(*paths))


def dirname(path: str) -> str:
    """
    Get the directory name of a path

    Args:
        path: Path to process

    Returns:
        Directory portion of path

    Examples:
        >>> dirname("/home/user/file.txt")
        '/home/user'
        >>> dirname("/home/user/")
        '/home/user'
    """
    result = posixpath.dirname(path)
    return result if result else "/"


def basename(path: str) -> str:
    """
    Get the base name of a path

    Args:
        path: Path to process

    Returns:
        Base name (file or directory name)

    Examples:
        >>> basename("/home/user/file.txt")
        'file.txt'
        >>> basename("/home/user/")
        'user'
    """
    return posixpath.basename(path.rstrip("/"))


def split(path: str) -> tuple[str, str]:
    """
    Split path into directory and base name

    Args:
        path: Path to split

    Returns:
        Tuple of (directory, basename)

    Examples:
        >>> split("/home/user/file.txt")
        ('/home/user', 'file.txt')
    """
    dir_part, base_part = posixpath.split(path)
    return (dir_part if dir_part else "/", base_part)


def splitext(path: str) -> tuple[str, str]:
    """
    Split path into root and extension

    Args:
        path: Path to split

    Returns:
        Tuple of (root, extension)

    Examples:
        >>> splitext("/home/user/file.txt")
        ('/home/user/file', '.txt')
        >>> splitext("/home/user/archive.tar.gz")
        ('/home/user/archive.tar', '.gz')
    """
    return posixpath.splitext(path)


def extension(path: str, include_dot: bool = True) -> str:
    """
    Get the file extension

    Args:
        path: Path to process
        include_dot: Whether to include the dot in the extension

    Returns:
        File extension

    Examples:
        >>> extension("/home/user/file.txt")
        '.txt'
        >>> extension("/home/user/file.txt", include_dot=False)
        'txt'
    """
    _, ext = posixpath.splitext(path)
    return ext if include_dot else ext.lstrip(".")


def get_all_extensions(path: str) -> list[str]:
    """
    Get all extensions from a path (for files like .tar.gz)

    Args:
        path: Path to process

    Returns:
        List of extensions (without dots)

    Examples:
        >>> get_all_extensions("/home/user/archive.tar.gz")
        ['tar', 'gz']
        >>> get_all_extensions("/home/user/file.txt")
        ['txt']
    """
    base = basename(path)
    parts = base.split(".")
    if len(parts) <= 1:
        return []
    return parts[1:]


def stem(path: str) -> str:
    """
    Get the filename without extension

    Args:
        path: Path to process

    Returns:
        Filename without extension

    Examples:
        >>> stem("/home/user/file.txt")
        'file'
        >>> stem("/home/user/archive.tar.gz")
        'archive.tar'
    """
    base = basename(path)
    root, _ = posixpath.splitext(base)
    return root


def is_absolute(path: str) -> bool:
    """
    Check if path is absolute

    Args:
        path: Path to check

    Returns:
        True if path is absolute

    Examples:
        >>> is_absolute("/home/user")
        True
        >>> is_absolute("user/docs")
        False
    """
    return posixpath.isabs(path)


def is_relative(path: str) -> bool:
    """
    Check if path is relative

    Args:
        path: Path to check

    Returns:
        True if path is relative

    Examples:
        >>> is_relative("user/docs")
        True
        >>> is_relative("/home/user")
        False
    """
    return not posixpath.isabs(path)


def relative_to(path: str, base: str) -> str:
    """
    Get the relative path from base to path

    Args:
        path: Target path
        base: Base path

    Returns:
        Relative path from base to path

    Examples:
        >>> relative_to("/home/user/docs/file.txt", "/home/user")
        'docs/file.txt'
    """
    # Normalize both paths
    path = normalize(path)
    base = normalize(base)

    # Ensure base ends with /
    if not base.endswith("/"):
        base += "/"

    # Check if path starts with base
    if path.startswith(base):
        return path[len(base) :]

    # If not a subpath, use posixpath.relpath
    return posixpath.relpath(path, base)


def common_path(*paths: str) -> str:
    """
    Get the common base path of multiple paths

    Args:
        *paths: Paths to compare

    Returns:
        Common base path

    Examples:
        >>> common_path("/home/user/docs", "/home/user/pictures")
        '/home/user'
    """
    if not paths:
        return "/"

    # Normalize all paths
    normalized = [normalize(p) for p in paths]

    # Find common prefix
    common = posixpath.commonpath(normalized)
    return common if common else "/"


def parent(path: str, levels: int = 1) -> str:
    """
    Get the parent directory, optionally going up multiple levels

    Args:
        path: Path to process
        levels: Number of levels to go up

    Returns:
        Parent directory path

    Examples:
        >>> parent("/home/user/docs/file.txt")
        '/home/user/docs'
        >>> parent("/home/user/docs/file.txt", levels=2)
        '/home/user'
    """
    result = normalize(path)
    for _ in range(levels):
        result = dirname(result)
        if result == "/":
            break
    return result


def parts(path: str) -> list[str]:
    """
    Split path into all its components

    Args:
        path: Path to split

    Returns:
        List of path components

    Examples:
        >>> parts("/home/user/docs/file.txt")
        ['/', 'home', 'user', 'docs', 'file.txt']
    """
    path = normalize(path)
    if path == "/":
        return ["/"]

    components = ["/"] + [p for p in path.split("/") if p]
    return components


def depth(path: str) -> int:
    """
    Get the depth of a path (number of directories from root)

    Args:
        path: Path to check

    Returns:
        Depth of path

    Examples:
        >>> depth("/")
        0
        >>> depth("/home/user")
        2
    """
    path = normalize(path)
    if path == "/":
        return 0

    return len([p for p in path.split("/") if p])


def is_parent(parent_path: str, child_path: str) -> bool:
    """
    Check if parent_path is a parent of child_path

    Args:
        parent_path: Potential parent path
        child_path: Potential child path

    Returns:
        True if parent_path is a parent of child_path

    Examples:
        >>> is_parent("/home/user", "/home/user/docs/file.txt")
        True
        >>> is_parent("/home/user", "/home/other")
        False
    """
    parent_path = normalize(parent_path)
    child_path = normalize(child_path)

    # Root is parent of everything except itself
    if parent_path == "/":
        return child_path != "/"

    # Ensure parent ends with / for proper comparison
    if not parent_path.endswith("/"):
        parent_path += "/"

    return child_path.startswith(parent_path)


def is_child(child_path: str, parent_path: str) -> bool:
    """
    Check if child_path is a child of parent_path

    Args:
        child_path: Potential child path
        parent_path: Potential parent path

    Returns:
        True if child_path is a child of parent_path

    Examples:
        >>> is_child("/home/user/docs/file.txt", "/home/user")
        True
    """
    return is_parent(parent_path, child_path)


def has_extension(path: str, *extensions: str) -> bool:
    """
    Check if path has any of the given extensions

    Args:
        path: Path to check
        *extensions: Extensions to check (with or without dots)

    Returns:
        True if path has any of the extensions

    Examples:
        >>> has_extension("/home/user/file.txt", ".txt", ".md")
        True
        >>> has_extension("/home/user/file.txt", "txt", "md")
        True
        >>> has_extension("/home/user/file.txt", ".pdf")
        False
    """
    _, ext = posixpath.splitext(path)
    ext = ext.lower()

    for check_ext in extensions:
        check_ext = check_ext.lower()
        if not check_ext.startswith("."):
            check_ext = "." + check_ext

        if ext == check_ext:
            return True

    return False


def change_extension(path: str, new_ext: str) -> str:
    """
    Change the extension of a path

    Args:
        path: Original path
        new_ext: New extension (with or without dot)

    Returns:
        Path with new extension

    Examples:
        >>> change_extension("/home/user/file.txt", ".md")
        '/home/user/file.md'
        >>> change_extension("/home/user/file.txt", "pdf")
        '/home/user/file.pdf'
    """
    root, _ = posixpath.splitext(path)

    if not new_ext.startswith("."):
        new_ext = "." + new_ext

    return root + new_ext


def ensure_trailing_slash(path: str) -> str:
    """
    Ensure path ends with a trailing slash

    Args:
        path: Path to process

    Returns:
        Path with trailing slash

    Examples:
        >>> ensure_trailing_slash("/home/user")
        '/home/user/'
    """
    return path if path.endswith("/") else path + "/"


def remove_trailing_slash(path: str) -> str:
    """
    Remove trailing slash from path (except for root)

    Args:
        path: Path to process

    Returns:
        Path without trailing slash

    Examples:
        >>> remove_trailing_slash("/home/user/")
        '/home/user'
        >>> remove_trailing_slash("/")
        '/'
    """
    if path == "/":
        return path
    return path.rstrip("/")


def safe_join(base: str, *paths: str) -> str:
    """
    Safely join paths, preventing directory traversal attacks

    Args:
        base: Base path
        *paths: Paths to join

    Returns:
        Safely joined path

    Raises:
        ValueError: If result would escape base path

    Examples:
        >>> safe_join("/home/user", "docs", "file.txt")
        '/home/user/docs/file.txt'
    """
    base = normalize(base)
    result = join(base, *paths)
    result = normalize(result)

    # Ensure result is within base
    if not is_parent(base, result) and result != base:
        raise ValueError(f"Path {result} would escape base {base}")

    return result


def glob_match(path: str, pattern: str) -> bool:
    """
    Check if path matches a glob pattern

    Args:
        path: Path to check
        pattern: Glob pattern (* and ? wildcards)

    Returns:
        True if path matches pattern

    Examples:
        >>> glob_match("/home/user/file.txt", "*.txt")
        True
        >>> glob_match("/home/user/file.txt", "/home/*/file.txt")
        True
    """
    import fnmatch

    return fnmatch.fnmatch(path, pattern)
