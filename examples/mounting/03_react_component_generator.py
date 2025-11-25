#!/usr/bin/env python3
"""
Example 3: React Component Generator with Hot Reload

This example demonstrates:
1. AI generates React components
2. Mounts them so Vite can see them
3. Vite dev server hot-reloads automatically
4. Simulates iterative component development

This shows how AI + Vite (or any dev server) can work together seamlessly.

Usage:
    # Terminal 1: Start this script
    python examples/mounting/03_react_component_generator.py

    # Terminal 2: Start Vite dev server
    cd /tmp/chukfs_react && npm run dev

Note: This creates a minimal React + Vite project structure
"""

import asyncio
import json
import sys
from pathlib import Path
from textwrap import dedent

from chuk_virtual_fs import SyncVirtualFileSystem
from chuk_virtual_fs.mount import MountOptions, mount


class ComponentGenerator:
    """Simulates AI that generates React components."""

    @staticmethod
    def generate_package_json() -> dict:
        """Generate package.json for Vite + React."""
        return {
            "name": "vfs-react-app",
            "version": "1.0.0",
            "type": "module",
            "scripts": {"dev": "vite", "build": "vite build"},
            "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"},
            "devDependencies": {
                "@types/react": "^18.2.0",
                "@types/react-dom": "^18.2.0",
                "@vitejs/plugin-react": "^4.0.0",
                "vite": "^4.3.0",
            },
        }

    @staticmethod
    def generate_vite_config() -> str:
        """Generate vite.config.js."""
        return dedent("""
            import { defineConfig } from 'vite'
            import react from '@vitejs/plugin-react'

            export default defineConfig({
              plugins: [react()],
            })
        """).strip()

    @staticmethod
    def generate_index_html() -> str:
        """Generate index.html."""
        return dedent("""
            <!DOCTYPE html>
            <html lang="en">
              <head>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>VFS React App</title>
              </head>
              <body>
                <div id="root"></div>
                <script type="module" src="/src/main.jsx"></script>
              </body>
            </html>
        """).strip()

    @staticmethod
    def generate_main_jsx() -> str:
        """Generate main.jsx."""
        return dedent("""
            import React from 'react'
            import ReactDOM from 'react-dom/client'
            import App from './App'

            ReactDOM.createRoot(document.getElementById('root')).render(
              <React.StrictMode>
                <App />
              </React.StrictMode>,
            )
        """).strip()

    @staticmethod
    def generate_button_v1() -> str:
        """Generate initial Button component (simple)."""
        return dedent("""
            import React from 'react'

            export default function Button({ children, onClick }) {
              return (
                <button onClick={onClick} style={{ padding: '10px 20px' }}>
                  {children}
                </button>
              )
            }
        """).strip()

    @staticmethod
    def generate_button_v2() -> str:
        """Generate improved Button component (with variants)."""
        return dedent("""
            import React from 'react'

            export default function Button({ children, onClick, variant = 'primary' }) {
              const styles = {
                primary: {
                  padding: '10px 20px',
                  backgroundColor: '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                },
                secondary: {
                  padding: '10px 20px',
                  backgroundColor: '#6c757d',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                },
              }

              return (
                <button onClick={onClick} style={styles[variant]}>
                  {children}
                </button>
              )
            }
        """).strip()

    @staticmethod
    def generate_app_jsx(version: int = 1) -> str:
        """Generate App component that uses Button."""
        if version == 1:
            return dedent("""
                import React, { useState } from 'react'
                import Button from './components/Button'

                function App() {
                  const [count, setCount] = useState(0)

                  return (
                    <div style={{ padding: '50px', fontFamily: 'sans-serif' }}>
                      <h1>Virtual Filesystem React Demo</h1>
                      <p>Count: {count}</p>
                      <Button onClick={() => setCount(count + 1)}>
                        Increment
                      </Button>
                    </div>
                  )
                }

                export default App
            """).strip()
        else:
            return dedent("""
                import React, { useState } from 'react'
                import Button from './components/Button'

                function App() {
                  const [count, setCount] = useState(0)

                  return (
                    <div style={{ padding: '50px', fontFamily: 'sans-serif' }}>
                      <h1>Virtual Filesystem React Demo</h1>
                      <p>Count: {count}</p>
                      <div style={{ display: 'flex', gap: '10px' }}>
                        <Button variant="primary" onClick={() => setCount(count + 1)}>
                          Increment
                        </Button>
                        <Button variant="secondary" onClick={() => setCount(0)}>
                          Reset
                        </Button>
                      </div>
                    </div>
                  )
                }

                export default App
            """).strip()


async def setup_project(vfs: SyncVirtualFileSystem) -> None:
    """Setup the React + Vite project structure."""
    gen = ComponentGenerator()

    print("\n1. Setting up React + Vite project...")

    # Root files
    vfs.write_file("/package.json", json.dumps(gen.generate_package_json(), indent=2))
    vfs.write_file("/vite.config.js", gen.generate_vite_config())
    vfs.write_file("/index.html", gen.generate_index_html())

    # Source files
    vfs.mkdir("/src")
    vfs.write_file("/src/main.jsx", gen.generate_main_jsx())
    vfs.write_file("/src/App.jsx", gen.generate_app_jsx(version=1))

    # Components
    vfs.mkdir("/src/components")
    vfs.write_file("/src/components/Button.jsx", gen.generate_button_v1())

    print("   ✅ Created project structure:")
    print("      - package.json")
    print("      - vite.config.js")
    print("      - index.html")
    print("      - src/main.jsx")
    print("      - src/App.jsx")
    print("      - src/components/Button.jsx")


async def main() -> None:
    print("=" * 70)
    print("Example 3: React Component Generator with Hot Reload")
    print("=" * 70)

    # Create VFS
    vfs = SyncVirtualFileSystem()

    # Setup project
    await setup_project(vfs)

    # Setup mount point
    if sys.platform == "win32":
        mount_point = Path("Z:")
    else:
        mount_point = Path("/tmp/chukfs_react")
        mount_point.mkdir(exist_ok=True)

    print(f"\n2. Mounting at {mount_point}...")

    try:
        async with mount(vfs, mount_point, MountOptions()):
            print("   ✅ Mounted!")

            print("\n" + "=" * 70)
            print("Project is ready!")
            print("=" * 70)
            print("\nTo start the dev server, run in another terminal:")
            print(f"  cd {mount_point}")
            print("  npm install")
            print("  npm run dev")
            print("\nThen open http://localhost:5173 in your browser")
            print("=" * 70)

            # Wait for user to start dev server
            input("\nPress Enter when dev server is running...")

            # Simulate AI iterating on the component
            print("\n3. AI simulating component improvements...")
            print("   (Watch your browser - it should hot reload!)")

            gen = ComponentGenerator()

            print("\n   Iteration 1: Improving Button component...")
            print("   🤖 Adding variant prop and styling...")
            await asyncio.sleep(2)

            vfs.write_file("/src/components/Button.jsx", gen.generate_button_v2())
            print("   ✅ Updated Button.jsx")
            print("   ⚡ Vite should hot reload now!")

            await asyncio.sleep(3)

            print("\n   Iteration 2: Updating App to use new Button features...")
            print("   🤖 Adding Reset button with secondary variant...")
            await asyncio.sleep(2)

            vfs.write_file("/src/App.jsx", gen.generate_app_jsx(version=2))
            print("   ✅ Updated App.jsx")
            print("   ⚡ Vite should hot reload again!")

            print("\n" + "=" * 70)
            print("✨ Demo complete!")
            print("=" * 70)
            print("\nWhat just happened:")
            print("  1. AI wrote React components to VFS")
            print("  2. VFS mounted → Vite saw them as real files")
            print("  3. AI updated components → Vite hot-reloaded automatically")
            print("  4. No custom Vite integration needed!")
            print("\nPress Ctrl+C to unmount and exit...")
            print("=" * 70)

            await asyncio.Event().wait()

    except KeyboardInterrupt:
        print("\n\nUnmounting...")

    print("\n✅ Example complete!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
