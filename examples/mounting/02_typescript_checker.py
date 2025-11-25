#!/usr/bin/env python3
"""
Example 2: AI Code Assistant with TypeScript Checking

This example simulates an AI coding assistant that:
1. Generates TypeScript code
2. Mounts it so TypeScript can check it
3. Reads type errors
4. Fixes the code
5. Verifies it compiles

This demonstrates the core "AI + Tools" integration pattern.

Usage:
    python examples/mounting/02_typescript_checker.py

Requirements:
    npm install -g typescript  # or have tsc in PATH
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.mount import MountOptions, mount


class SimpleAIAssistant:
    """Simulates an AI that generates and fixes code."""

    @staticmethod
    def generate_initial_code() -> str:
        """Generate TypeScript code with intentional type error."""
        return dedent("""
            interface User {
                name: string;
                age: number;
            }

            function greetUser(user: User): string {
                // Type error: trying to use number as string
                return "Hello, " + user.age;  // Should be user.name!
            }

            const myUser = {
                name: "Alice",
                age: 30
            };

            console.log(greetUser(myUser));
        """).strip()

    @staticmethod
    def fix_code(original: str, error_message: str) -> str:
        """Fix the code based on error message."""
        # Simple fix: replace user.age with user.name
        if "user.age" in original:
            fixed = original.replace(
                'return "Hello, " + user.age;', 'return "Hello, " + user.name;'
            )
            return fixed
        return original


async def check_typescript(mount_point: Path) -> tuple[bool, str]:
    """Run TypeScript compiler and return results."""
    try:
        result = subprocess.run(
            ["tsc", "--noEmit", "--pretty", "false"],
            cwd=str(mount_point),
            capture_output=True,
            text=True,
            timeout=10,
        )

        # tsc returns 0 if no errors
        if result.returncode == 0:
            return True, "No type errors!"
        else:
            return False, result.stdout + result.stderr

    except FileNotFoundError:
        return False, "TypeScript not installed (npm install -g typescript)"
    except subprocess.TimeoutExpired:
        return False, "TypeScript check timed out"


async def main() -> None:
    print("=" * 70)
    print("Example 2: AI Code Assistant with TypeScript Checking")
    print("=" * 70)

    # Check if TypeScript is available
    try:
        subprocess.run(["tsc", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("\n❌ TypeScript not found!")
        print("   Install with: npm install -g typescript")
        return

    # Create VFS
    print("\n1. Creating virtual filesystem...")
    vfs = SyncVirtualFileSystem()

    # Setup TypeScript config
    print("2. Setting up TypeScript project...")
    tsconfig = {
        "compilerOptions": {
            "target": "ES2020",
            "module": "commonjs",
            "strict": True,
            "esModuleInterop": True,
            "skipLibCheck": True,
            "forceConsistentCasingInFileNames": True,
        }
    }
    vfs.write_file("/tsconfig.json", json.dumps(tsconfig, indent=2))
    print("   ✅ Created tsconfig.json")

    # AI generates initial code with error
    print("\n3. AI Assistant generating code...")
    ai = SimpleAIAssistant()
    initial_code = ai.generate_initial_code()
    vfs.write_file("/index.ts", initial_code)
    print("   ✅ Generated index.ts")
    print("\n   Code snippet:")
    print("   " + "\n   ".join(initial_code.split("\n")[:10]))
    print("   ...")

    # Setup mount point
    if sys.platform == "win32":
        mount_point = Path("Z:")
    else:
        mount_point = Path("/tmp/chukfs_ts")
        mount_point.mkdir(exist_ok=True)

    print(f"\n4. Mounting at {mount_point}...")

    try:
        async with mount(vfs, mount_point, MountOptions()):
            print("   ✅ Mounted!")

            # First check - should fail
            print("\n5. Running TypeScript compiler (first attempt)...")
            success, output = await check_typescript(mount_point)

            if not success:
                print("   ❌ Type errors found:")
                print("\n   " + "\n   ".join(output.split("\n")[:5]))
                print()

                # AI fixes the code
                print("6. AI Assistant analyzing errors...")
                await asyncio.sleep(1)  # Simulate AI thinking
                print("   🤖 Found issue: using 'user.age' instead of 'user.name'")

                print("7. AI Assistant fixing code...")
                fixed_code = ai.fix_code(initial_code, output)
                vfs.write_file("/index.ts", fixed_code)
                print("   ✅ Code updated")

                # Second check - should pass
                print("\n8. Running TypeScript compiler (second attempt)...")
                await asyncio.sleep(0.5)  # Give filesystem time to sync
                success, output = await check_typescript(mount_point)

                if success:
                    print("   ✅ No type errors!")
                    print("\n" + "=" * 70)
                    print("🎉 AI successfully fixed the code!")
                    print("=" * 70)
                else:
                    print("   ❌ Still has errors:")
                    print("   " + output)

            else:
                print("   ✅ Code already has no errors!")

            print("\n9. Final code:")
            final_code = vfs.read_file("/index.ts")
            print("   " + "\n   ".join(final_code.split("\n")))

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

    print("\n✅ Example complete!")
    print("\nKey takeaway:")
    print("  AI writes to VFS → TypeScript sees it via mount → AI reads errors")
    print("  No custom TypeScript integration needed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
