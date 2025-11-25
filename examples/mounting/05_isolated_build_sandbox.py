#!/usr/bin/env python3
"""
Example 5: Isolated Build Sandbox

This example demonstrates:
1. Creating isolated build environments
2. Running builds in sandboxed VFS
3. Collecting build artifacts
4. Clean teardown (no filesystem pollution)

Perfect for CI/CD, testing, and containerless sandboxing.

Usage:
    python examples/mounting/05_isolated_build_sandbox.py
"""

import asyncio
import contextlib
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent

from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.mount import MountOptions, mount


class BuildSandbox:
    """Manages isolated build environments."""

    def __init__(self, build_id: str):
        self.build_id = build_id
        self.vfs = SyncVirtualFileSystem()
        self.results = {}

    def setup_python_project(self) -> None:
        """Setup a simple Python project."""
        # Create project structure
        self.vfs.mkdir("/src")
        self.vfs.mkdir("/tests")
        self.vfs.mkdir("/dist")

        # Main module
        main_py = dedent("""
            '''
            Example module for demonstration.
            '''

            def add(a: int, b: int) -> int:
                '''Add two numbers.'''
                return a + b

            def multiply(a: int, b: int) -> int:
                '''Multiply two numbers.'''
                return a * b

            if __name__ == '__main__':
                print(f"add(2, 3) = {add(2, 3)}")
                print(f"multiply(4, 5) = {multiply(4, 5)}")
        """).strip()
        self.vfs.write_file("/src/main.py", main_py)

        # Test file
        test_py = dedent("""
            import sys
            sys.path.insert(0, '/src')

            from main import add, multiply

            def test_add():
                assert add(2, 3) == 5
                assert add(0, 0) == 0
                assert add(-1, 1) == 0
                print("✓ test_add passed")

            def test_multiply():
                assert multiply(2, 3) == 6
                assert multiply(0, 5) == 0
                assert multiply(-2, 3) == -6
                print("✓ test_multiply passed")

            if __name__ == '__main__':
                test_add()
                test_multiply()
                print("\\n✅ All tests passed!")
        """).strip()
        self.vfs.write_file("/tests/test_main.py", test_py)

        # Setup file
        setup_py = dedent("""
            from setuptools import setup, find_packages

            setup(
                name='demo-package',
                version='1.0.0',
                packages=find_packages(),
                install_requires=[],
            )
        """).strip()
        self.vfs.write_file("/setup.py", setup_py)

        # README
        readme = (
            dedent("""
            # Demo Package

            A simple demo package built in virtual filesystem.

            ## Build ID
            {}
        """)
            .format(self.build_id)
            .strip()
        )
        self.vfs.write_file("/README.md", readme)

    async def run_build(self, mount_point: Path) -> dict:
        """Run the build process."""
        results = {
            "build_id": self.build_id,
            "steps": [],
            "artifacts": [],
            "success": False,
        }

        # Step 1: Run tests
        print("\n   Running tests...")
        try:
            result = subprocess.run(
                [sys.executable, "tests/test_main.py"],
                cwd=str(mount_point),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                results["steps"].append(("tests", "passed"))
                print("   ✅ Tests passed")
            else:
                results["steps"].append(("tests", "failed"))
                print(f"   ❌ Tests failed: {result.stderr}")
                return results

        except Exception as e:
            results["steps"].append(("tests", f"error: {e}"))
            print(f"   ❌ Test error: {e}")
            return results

        # Step 2: Run main module
        print("\n   Running main module...")
        try:
            result = subprocess.run(
                [sys.executable, "src/main.py"],
                cwd=str(mount_point),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                results["steps"].append(("run", "success"))
                print("   ✅ Module executed successfully")
                print(f"   Output: {result.stdout.strip()}")
            else:
                results["steps"].append(("run", "failed"))
                print(f"   ❌ Execution failed: {result.stderr}")
                return results

        except Exception as e:
            results["steps"].append(("run", f"error: {e}"))
            print(f"   ❌ Execution error: {e}")
            return results

        # Step 3: Collect artifacts
        print("\n   Collecting artifacts...")
        try:
            # List all files
            artifacts = []
            for path in ["/src/main.py", "/tests/test_main.py", "/README.md"]:
                if self.vfs.exists(path):
                    size = len(self.vfs.read_file(path))
                    artifacts.append({"path": path, "size": size})

            results["artifacts"] = artifacts
            results["steps"].append(("artifacts", "collected"))
            print(f"   ✅ Collected {len(artifacts)} artifacts")

        except Exception as e:
            results["steps"].append(("artifacts", f"error: {e}"))
            print(f"   ❌ Artifact collection error: {e}")
            return results

        results["success"] = True
        return results


async def run_isolated_build(build_id: str) -> dict:
    """Run a complete build in an isolated sandbox."""
    print(f"\n🔨 Build {build_id}")
    print("-" * 70)

    # Create sandbox
    sandbox = BuildSandbox(build_id)

    print("1. Setting up project...")
    sandbox.setup_python_project()
    print("   ✅ Project structure created")

    # Create temporary mount point
    mount_point = Path(tempfile.mkdtemp(prefix=f"build_{build_id}_"))
    print(f"2. Mounting at {mount_point}...")

    try:
        async with mount(sandbox.vfs, mount_point, MountOptions()):
            print("   ✅ Mounted")

            print("3. Running build...")
            results = await sandbox.run_build(mount_point)

            return results

    finally:
        # Cleanup mount point
        with contextlib.suppress(Exception):
            mount_point.rmdir()


async def main() -> None:
    print("=" * 70)
    print("Example 5: Isolated Build Sandbox")
    print("=" * 70)

    print("\nThis example demonstrates CI/CD-style isolated builds.")
    print("Each build gets its own VFS, runs in isolation, then disappears.")

    # Run multiple builds
    builds = ["build_001", "build_002", "build_003"]

    all_results = []

    for build_id in builds:
        result = await run_isolated_build(build_id)
        all_results.append(result)

        await asyncio.sleep(1)  # Brief pause between builds

    # Summary
    print("\n" + "=" * 70)
    print("📊 Build Summary")
    print("=" * 70)

    for result in all_results:
        status = "✅ SUCCESS" if result["success"] else "❌ FAILED"
        print(f"\n{result['build_id']}: {status}")
        print(f"  Steps: {len(result['steps'])}")
        print(f"  Artifacts: {len(result['artifacts'])}")

        for step_name, step_status in result["steps"]:
            print(f"    - {step_name}: {step_status}")

    print("\n" + "=" * 70)
    print("✅ Example complete!")
    print("=" * 70)

    print("\nKey takeaways:")
    print("  ✓ Each build is completely isolated")
    print("  ✓ No filesystem pollution (VFS is in-memory)")
    print("  ✓ Perfect for parallel builds")
    print("  ✓ Instant cleanup (unmount = gone)")
    print("  ✓ Can be extended to any build system")

    print("\nReal-world applications:")
    print("  • CI/CD pipelines")
    print("  • Testing different configurations")
    print("  • Reproducible builds")
    print("  • Containerless sandboxing")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
