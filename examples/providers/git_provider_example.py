"""
Git Provider Example - Demonstrates both snapshot and worktree modes

This example shows how to use the Git provider in two modes:
1. snapshot: Read-only view of a repository at a specific commit/branch
2. worktree: Writable working directory backed by a git repository

Perfect for:
- MCP devboxes: "mount this repo for the LLM"
- Code review tools: Read-only snapshot at a commit
- AI coding: Clone, modify, commit workflow
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from chuk_virtual_fs import AsyncVirtualFileSystem


async def example_snapshot_mode():
    """Example: Read-only snapshot of a repository."""
    print("=" * 60)
    print("EXAMPLE 1: Snapshot Mode (Read-Only)")
    print("=" * 60)
    print()

    # Create a temporary local repo for testing
    temp_repo = tempfile.mkdtemp(prefix="git-test-")
    print(f"Creating test repository at: {temp_repo}")

    # Initialize a test repo
    os.system(f"cd {temp_repo} && git init")
    os.system(f"cd {temp_repo} && git config user.name 'Test User'")
    os.system(f"cd {temp_repo} && git config user.email 'test@example.com'")

    # Create some files
    Path(temp_repo, "README.md").write_text("# Test Repository\n\nFor demo purposes")
    Path(temp_repo, "src").mkdir()
    Path(temp_repo, "src", "main.py").write_text("def main():\n    print('Hello!')\n")

    # Commit
    os.system(f"cd {temp_repo} && git add .")
    os.system(f"cd {temp_repo} && git commit -m 'Initial commit'")

    print()
    print("Repository created with initial commit")
    print()

    # Create VFS with Git provider in snapshot mode
    async with AsyncVirtualFileSystem(
        provider="git", repo_url=temp_repo, mode="snapshot", ref="HEAD"
    ) as fs:
        print("✓ Mounted repository in snapshot mode")
        print()

        # List root directory
        print("Root directory contents:")
        files = await fs.ls("/")
        for file in files:
            print(f"  - {file}")
        print()

        # Read README
        content = await fs.read_text("/README.md")
        print("README.md contents:")
        print(content)
        print()

        # Read source file
        code = await fs.read_text("/src/main.py")
        print("src/main.py contents:")
        print(code)
        print()

        # Get metadata
        metadata = await fs.get_metadata("/")
        print("Repository metadata:")
        print(f"  Mode: {metadata.get('mode')}")
        print(f"  Ref: {metadata.get('ref')}")
        print(f"  Commit: {metadata.get('commit_sha', 'N/A')[:8]}")
        print(f"  Author: {metadata.get('commit_author', 'N/A')}")
        print()

        # Try to write (should fail in snapshot mode)
        print("Attempting write operation (should fail)...")
        success = await fs.write_file("/test.txt", "This won't work")
        print(f"  Write result: {success}")
        print()

    # Cleanup
    import shutil

    shutil.rmtree(temp_repo)


async def example_worktree_mode():
    """Example: Writable worktree mode with commit/push."""
    print("=" * 60)
    print("EXAMPLE 2: Worktree Mode (Writable)")
    print("=" * 60)
    print()

    # Create a temporary local repo for testing
    temp_repo = tempfile.mkdtemp(prefix="git-worktree-")
    print(f"Creating test repository at: {temp_repo}")

    # Initialize a test repo
    os.system(f"cd {temp_repo} && git init")
    os.system(f"cd {temp_repo} && git config user.name 'Test User'")
    os.system(f"cd {temp_repo} && git config user.email 'test@example.com'")

    # Create initial commit
    Path(temp_repo, "README.md").write_text("# Project\n")
    os.system(f"cd {temp_repo} && git add .")
    os.system(f"cd {temp_repo} && git commit -m 'Initial commit'")

    print()
    print("Repository created")
    print()

    # Create VFS with Git provider in worktree mode
    async with AsyncVirtualFileSystem(
        provider="git", repo_url=temp_repo, mode="worktree", branch="main"
    ) as fs:
        print("✓ Mounted repository in worktree mode")
        print()

        # Create a new file
        print("Creating new file: /src/app.py")
        await fs.mkdir("/src")
        await fs.write_file(
            "/src/app.py",
            """\"\"\"Application module.\"\"\"

def run():
    print("Application running!")

if __name__ == "__main__":
    run()
""",
        )
        print("  ✓ File created")
        print()

        # Modify existing file
        print("Updating README.md")
        await fs.write_file(
            "/README.md",
            """# My Project

A test project to demonstrate Git provider worktree mode.

## Features
- Read/write operations
- Git commit support
- Full version control
""",
        )
        print("  ✓ README updated")
        print()

        # Check Git status
        print("Git status:")
        # Access the provider directly for Git-specific operations
        provider = fs.provider
        status = await provider.get_status()
        print(f"  Dirty: {status.get('is_dirty')}")
        print(f"  Untracked files: {len(status.get('untracked_files', []))}")
        if status.get("untracked_files"):
            for f in status["untracked_files"]:
                print(f"    - {f}")
        if status.get("changed_files"):
            print(f"  Changed files: {len(status['changed_files'])}")
            for f in status["changed_files"]:
                print(f"    - {f['path']} ({f['change_type']})")
        print()

        # Commit changes
        print("Committing changes...")
        commit_success = await provider.commit(
            "Add application module and update README",
            author="AI Agent <ai@example.com>",
        )
        print(f"  Commit result: {commit_success}")
        print()

        # Get updated status
        print("Git status after commit:")
        status = await provider.get_status()
        print(f"  Dirty: {status.get('is_dirty')}")
        print(f"  Untracked files: {len(status.get('untracked_files', []))}")
        print()

        # Get metadata
        metadata = await fs.get_metadata("/")
        print("Repository metadata:")
        print(f"  Mode: {metadata.get('mode')}")
        print(f"  Branch: {metadata.get('branch')}")
        print(f"  Commit: {metadata.get('commit_sha', 'N/A')[:8]}")
        print(f"  Message: {metadata.get('commit_message', 'N/A').strip()}")
        print()

        # Get storage stats
        stats = await fs.get_storage_stats()
        print("Storage stats:")
        print(f"  Mode: {stats.get('mode')}")
        print(f"  Repo URL: {stats.get('repo_url')}")
        print(f"  Active branch: {stats['repo_info'].get('active_branch')}")
        print("  Operations:")
        print(f"    - Reads: {stats['operations']['reads']}")
        print(f"    - Writes: {stats['operations']['writes']}")
        print(f"    - Commits: {stats['operations']['commits']}")
        print()

    # Cleanup
    import shutil

    shutil.rmtree(temp_repo)


async def example_clone_remote():
    """Example: Clone a remote repository (commented out by default)."""
    print("=" * 60)
    print("EXAMPLE 3: Clone Remote Repository (demonstration)")
    print("=" * 60)
    print()

    print("Example code for cloning a remote repository:")
    print()
    print("```python")
    print("# Clone a GitHub repository in snapshot mode")
    print("async with AsyncVirtualFileSystem(")
    print('    provider="git",')
    print('    repo_url="https://github.com/user/repo",')
    print('    mode="snapshot",')
    print('    ref="main",  # or specific commit SHA')
    print("    depth=1  # shallow clone for faster performance")
    print(") as fs:")
    print("    # Read files from the repository")
    print('    readme = await fs.read_text("/README.md")')
    print('    files = await fs.ls("/src")')
    print("```")
    print()
    print("This is perfect for:")
    print("  - MCP servers: 'Mount this repo for Claude to review'")
    print("  - Code analysis: Read-only access to any commit")
    print("  - Documentation: Browse repo without cloning to disk")
    print()


async def example_mcp_use_case():
    """Example: MCP server use case - AI code review."""
    print("=" * 60)
    print("EXAMPLE 4: MCP Use Case - AI Code Review")
    print("=" * 60)
    print()

    print("Simulating MCP server workflow:")
    print()

    # Create a test repo
    temp_repo = tempfile.mkdtemp(prefix="mcp-review-")

    # Initialize with some code
    os.system(f"cd {temp_repo} && git init")
    os.system(f"cd {temp_repo} && git config user.name 'Dev'")
    os.system(f"cd {temp_repo} && git config user.email 'dev@example.com'")

    Path(temp_repo, "src").mkdir()
    Path(temp_repo, "src", "calculator.py").write_text(
        """def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    # BUG: No zero division check!
    return a / b
"""
    )

    os.system(f"cd {temp_repo} && git add .")
    os.system(f"cd {temp_repo} && git commit -m 'Add calculator functions'")

    print("1. Developer creates PR with new code")
    print(f"   Repository: {temp_repo}")
    print()

    # MCP tool: Mount repository for review
    print("2. MCP tool mounts repository for Claude to review")
    async with AsyncVirtualFileSystem(
        provider="git", repo_url=temp_repo, mode="snapshot", ref="HEAD"
    ) as fs:
        print("   ✓ Repository mounted")
        print()

        # Claude reads the code
        print("3. Claude reads the code:")
        code = await fs.read_text("/src/calculator.py")
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            print(f"   {i:2d} | {line}")
        print()

        # Claude identifies issues
        print("4. Claude identifies issues:")
        print("   ⚠️  Line 11: divide() function missing zero division check")
        print("   💡 Suggestion: Add validation before division")
        print()

        print("5. Claude's feedback returned to developer via MCP")
        print()

    # Cleanup
    import shutil

    shutil.rmtree(temp_repo)


async def main():
    """Run all examples."""
    print()
    print("🚀 Git Provider Examples")
    print()

    try:
        # Check if Git provider is available
        from chuk_virtual_fs.providers import GitProvider  # noqa: F401

        print("✓ Git provider is available")
        print()
    except ImportError:
        print("❌ Git provider not available")
        print()
        print("Install with:")
        print("  pip install 'chuk-virtual-fs[git]'")
        print()
        return

    # Run examples
    await example_snapshot_mode()
    await example_worktree_mode()
    await example_clone_remote()
    await example_mcp_use_case()

    print("=" * 60)
    print("✅ All examples completed!")
    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(main())
