#!/bin/bash
# One-click script to run any chuk-virtual-fs example
# Usage: ./run_example.sh [example_number_or_name]

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Show menu if no argument provided
show_menu() {
    print_header "chuk-virtual-fs Example Runner"
    echo ""
    echo "WebDAV Examples (Easiest - No Installation!):"
    echo -e "  ${GREEN}1${NC}  Basic WebDAV Server           (./webdav/01_basic_webdav.py)"
    echo -e "  ${GREEN}2${NC}  Background WebDAV Server      (./webdav/02_background_server.py)"
    echo -e "  ${GREEN}3${NC}  Read-Only WebDAV Server       (./webdav/03_readonly_server.py)"
    echo ""
    echo "FUSE Mounting Examples (Docker - No Host Changes!):"
    echo -e "  ${GREEN}4${NC}  Test Infrastructure           (./mounting/00_test_without_fuse.py)"
    echo -e "  ${GREEN}5${NC}  Basic FUSE Mount (Docker)     (docker)"
    echo -e "  ${GREEN}6${NC}  TypeScript Checker (Docker)   (docker + TypeScript)"
    echo ""
    echo "Storage Provider Examples:"
    echo -e "  ${GREEN}7${NC}  Memory Provider               (./providers/memory_provider_example.py)"
    echo -e "  ${GREEN}8${NC}  Filesystem Provider           (./providers/filesystem_provider_example.py)"
    echo -e "  ${GREEN}9${NC}  SQLite Provider               (./providers/sqlite_provider_example.py)"
    echo ""
    echo "Test Suites:"
    echo -e "  ${GREEN}10${NC} Test All WebDAV Examples      (uv run python ../test_all_examples.py)"
    echo -e "  ${GREEN}11${NC} Test All Docker Mount Examples (uv run python ../test_docker_mount_examples.py)"
    echo ""
    echo -e "Usage: ${YELLOW}./run_example.sh [number]${NC}"
    echo ""
}

# Check dependencies
check_webdav_deps() {
    if ! python -c "import wsgidav" 2>/dev/null; then
        print_warning "WebDAV dependencies not installed"
        echo "Install with: pip install chuk-virtual-fs[webdav]"
        read -p "Install now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            pip install chuk-virtual-fs[webdav]
        else
            exit 1
        fi
    fi
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is required for this example"
        echo "Install from: https://www.docker.com/get-started"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker is not running"
        echo "Please start Docker Desktop"
        exit 1
    fi
}

build_docker_image() {
    if [[ "$(docker images -q chuk-virtual-fs-mount:test 2> /dev/null)" == "" ]]; then
        print_warning "Docker image not found. Building..."
        docker build -f mounting/Dockerfile -t chuk-virtual-fs-mount:test ..
        print_success "Docker image built"
    fi
}

# Run example based on selection
run_example() {
    case $1 in
        1|webdav1|basic-webdav)
            print_header "Running: Basic WebDAV Server"
            check_webdav_deps
            echo ""
            print_success "Starting server on http://localhost:8080"
            echo ""
            echo "To mount in Finder (macOS):"
            echo -e "  1. Press Cmd+K"
            echo -e "  2. Enter: http://localhost:8080"
            echo -e "  3. Click Connect"
            echo ""
            echo "Press Ctrl+C to stop"
            echo ""
            uv run python ./webdav/01_basic_webdav.py
            ;;

        2|webdav2|background-webdav)
            print_header "Running: Background WebDAV Server"
            check_webdav_deps
            echo ""
            print_success "Starting background server..."
            echo ""
            uv run python ./webdav/02_background_server.py
            ;;

        3|webdav3|readonly-webdav)
            print_header "Running: Read-Only WebDAV Server"
            check_webdav_deps
            echo ""
            print_success "Starting read-only server..."
            echo ""
            uv run python ./webdav/03_readonly_server.py
            ;;

        4|mount0|test-infrastructure)
            print_header "Running: Test Infrastructure (No FUSE Required)"
            echo ""
            uv run python ./mounting/00_test_without_fuse.py
            ;;

        5|mount1|basic-mount-docker)
            print_header "Running: Basic FUSE Mount (Docker)"
            check_docker
            build_docker_image
            echo ""
            print_success "Running in Docker (no host system changes)..."
            echo ""
            docker run --rm --privileged --device /dev/fuse chuk-virtual-fs-mount:test
            ;;

        6|mount2|typescript-docker)
            print_header "Running: TypeScript Checker (Docker)"
            check_docker
            build_docker_image
            echo ""
            print_success "Running TypeScript example in Docker..."
            echo ""
            echo "This demonstrates the AI + Tools integration pattern:"
            echo -e "  1. AI generates TypeScript code"
            echo -e "  2. Mount it so TypeScript can check it"
            echo -e "  3. Read type errors"
            echo -e "  4. AI fixes the code"
            echo ""
            docker run --rm --privileged --device /dev/fuse chuk-virtual-fs-mount:test \
                timeout 30 python examples/mounting/02_typescript_checker.py || true
            ;;

        7|memory)
            print_header "Running: Memory Provider Example"
            echo ""
            uv run python ./providers/memory_provider_example.py
            ;;

        8|filesystem)
            print_header "Running: Filesystem Provider Example"
            echo ""
            uv run python ./providers/filesystem_provider_example.py
            ;;

        9|sqlite)
            print_header "Running: SQLite Provider Example"
            echo ""
            uv run python ./providers/sqlite_provider_example.py
            ;;

        10|test-webdav)
            print_header "Testing: All WebDAV Examples"
            check_webdav_deps
            echo ""
            uv run python ../test_all_examples.py
            ;;

        11|test-docker)
            print_header "Testing: All Docker Mount Examples"
            check_docker
            build_docker_image
            echo ""
            uv run python ../test_docker_mount_examples.py
            ;;

        *)
            print_error "Unknown example: $1"
            echo ""
            show_menu
            exit 1
            ;;
    esac
}

# Main script
main() {
    # Change to examples directory (where this script is)
    cd "$(dirname "$0")"

    if [ $# -eq 0 ]; then
        show_menu
        read -p "Select an example (1-11): " choice
        echo ""
        run_example "$choice"
    else
        run_example "$1"
    fi
}

main "$@"
