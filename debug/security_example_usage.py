"""
debug/security_example_usage.py - Comprehensive demonstration of virtual filesystem security features
"""

from chuk_virtual_fs import (
    VirtualFileSystem,
    get_available_profiles,
    get_profile_settings,
)


def security_profiles_demo():
    """Demonstrate available security profiles."""
    print("\n===== SECURITY PROFILES OVERVIEW =====")
    print("The virtual filesystem supports multiple predefined security profiles:")

    profiles = get_available_profiles()
    for profile in profiles:
        settings = get_profile_settings(profile)
        print(f"\n{profile.upper()} Profile:")
        print(f"  Purpose: {_get_profile_description(profile)}")
        print(f"  Max File Size: {settings['max_file_size'] / 1024 / 1024:.1f} MB")
        print(f"  Max Total Size: {settings['max_total_size'] / 1024 / 1024:.1f} MB")
        print(f"  Read Only: {settings['read_only']}")
        print(f"  Max Files: {settings['max_files']}")
        print(f"  Max Path Depth: {settings['max_path_depth']}")
        if "allowed_paths" in settings:
            print(f"  Allowed Paths: {settings['allowed_paths']}")


def _get_profile_description(profile: str) -> str:
    """Provide a human-readable description for each security profile."""
    descriptions = {
        "default": "Standard security with moderate restrictions",
        "strict": "High security with tight constraints",
        "readonly": "Completely read-only, no modifications allowed",
        "untrusted": "Highly restrictive environment for untrusted code",
        "testing": "Relaxed security for development and testing",
    }
    return descriptions.get(profile, "Custom security profile")


def default_security_example():
    """Example using the default security profile."""
    print("\n===== DEFAULT SECURITY PROFILE DEMONSTRATION =====")
    print("This example shows how the default security profile prevents:")
    print("1. Writing to sensitive system paths")
    print("2. Creating files with potentially dangerous patterns")

    fs = VirtualFileSystem(security_profile="default")

    # 1. Demonstrate writing to a protected system path.
    print("\n1. Attempting to write to a protected system path (/etc/passwd):")
    result = fs.write_file("/etc/passwd", "root:x:0:0:")
    print(f"   Write result: {'Success' if result else 'Failed (as expected)'}")

    # 2. Demonstrate blocking a file creation with path traversal.
    print(
        "\n2. Attempting to create a file with a path traversal pattern (/home/user/../etc/sensitive):"
    )
    result = fs.touch("/home/user/../etc/sensitive")
    print(f"   File creation result: {'Success' if result else 'Failed (as expected)'}")

    violations = fs.get_security_violations()
    print("\nSecurity Violations Detected:")
    for i, violation in enumerate(violations, 1):
        print(f"  {i}. Operation: {violation['operation']}")
        print(f"     Path: {violation['path']}")
        print(f"     Reason: {violation['reason']}")


def advanced_quota_management_example():
    """Demonstrate advanced quota management and security features."""
    print("\n===== ADVANCED QUOTA MANAGEMENT =====")
    print("This example shows how to manage storage quotas and restrictions:")

    # Use the untrusted profile (tight restrictions)
    fs = VirtualFileSystem(security_profile="untrusted")

    stats = fs.get_storage_stats()
    print("\nCurrent Quota Settings:")
    print(f"  Max File Size: {stats['max_file_size'] / 1024:.1f} KB")
    print(f"  Max Total Storage: {stats['max_total_size'] / 1024:.1f} KB")
    print(f"  Max Number of Files: {stats['max_files']}")

    print("\nDemonstrating File Size Restrictions:")
    small_data = "x" * 1000  # 1KB
    large_data = "x" * (600 * 1024)  # 600KB

    print("1. Writing a small file (/sandbox/small.txt) (should succeed):")
    result = fs.write_file("/sandbox/small.txt", small_data)
    print(f"   Result: {'Success' if result else 'Failed'}")

    print("\n2. Attempting to write a large file (/sandbox/large.txt) (should fail):")
    result = fs.write_file("/sandbox/large.txt", large_data)
    print(f"   Result: {'Success' if result else 'Failed (as expected)'}")

    violations = fs.get_security_violations()
    print("\nSecurity Violations:")
    for violation in violations:
        print(
            f"  - {violation['operation']} on {violation['path']}: {violation['reason']}"
        )


def custom_security_configuration_example():
    """Demonstrate creating a custom security configuration."""
    print("\n===== CUSTOM SECURITY CONFIGURATION =====")
    print("This example shows how to apply custom security settings:")

    fs = VirtualFileSystem(
        security_profile="default",
        security_max_file_size=50 * 1024,  # 50KB max file size
        security_allowed_paths=["/projects", "/data"],
        security_denied_patterns=[r".*\.exe", r".*\.sh", r"^\."],
    )

    print("\nCustom Security Configuration:")
    print("  - Max File Size: 50 KB")
    print("  - Allowed Paths: /projects, /data")
    print("  - Denied File Patterns: .exe, .sh, hidden files")

    print("\nDemonstrating Restrictions:")
    print("1. Writing to allowed path (/projects/notes.txt):")
    result = fs.write_file("/projects/notes.txt", "Project documentation")
    print(f"   Result: {'Success' if result else 'Failed'}")

    print("\n2. Attempting to write outside allowed paths (/home/unauthorized.txt):")
    result = fs.write_file("/home/unauthorized.txt", "Unauthorized file")
    print(f"   Result: {'Success' if result else 'Failed (as expected)'}")

    print(
        "\n3. Attempting to create a file with a denied extension (/projects/malicious.exe):"
    )
    result = fs.touch("/projects/malicious.exe")
    print(f"   Result: {'Success' if result else 'Failed (as expected)'}")

    violations = fs.get_security_violations()
    print("\nSecurity Violations:")
    for violation in violations:
        print(
            f"  - {violation['operation']} on {violation['path']}: {violation['reason']}"
        )


def security_violation_management_example():
    """Demonstrate security violation tracking and management."""
    print("\n===== SECURITY VIOLATION MANAGEMENT =====")
    print("This example shows how to track and manage security violations:")

    fs = VirtualFileSystem(security_profile="default")

    print("\nGenerating Security Violations:")
    fs.write_file("/etc/passwd", "test")  # Denied path
    fs.touch("/home/user/../etc/shadow")  # Path traversal

    violations = fs.get_security_violations()
    print(f"\nTotal Violations: {len(violations)}")

    print("\nDetailed Violation Log:")
    for i, violation in enumerate(violations, 1):
        print(f"{i}. Operation: {violation['operation']}")
        print(f"   Path: {violation['path']}")
        print(f"   Reason: {violation['reason']}")
        print(f"   Timestamp: {violation.get('timestamp', 'N/A')}")
        print()

    print("Clearing Violation Log:")
    fs.provider.clear_violations()
    violations_after_clear = fs.get_security_violations()
    print(f"Violations after clearing: {len(violations_after_clear)}")


def main():
    """Main demonstration function."""
    print("=" * 60)
    print("VIRTUAL FILESYSTEM SECURITY FEATURES DEMONSTRATION")
    print("=" * 60)

    print("\nThis demonstration will showcase the robust security features:")
    print("1. Predefined security profiles")
    print("2. Default security restrictions")
    print("3. Advanced quota management")
    print("4. Custom security configuration")
    print("5. Security violation tracking")

    # Run demonstration scenarios
    security_profiles_demo()
    default_security_example()
    advanced_quota_management_example()
    custom_security_configuration_example()
    security_violation_management_example()

    print("\n" + "=" * 60)
    print("SECURITY DEMONSTRATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
