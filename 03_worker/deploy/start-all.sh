#!/usr/bin/env bash
# Start all OCR workers locally
#
# Usage:
#   bash start-all.sh                  # Start all workers
#   bash start-all.sh paddle-text      # Start only paddle-text
#   bash start-all.sh paddle-text paddle-vl  # Start specific workers
#   bash start-all.sh stop             # Stop all workers
#   bash start-all.sh status           # Show worker status
#
# Log files: /tmp/worker_<name>.log

set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="/tmp"
ALL_WORKERS=("paddle-text" "paddle-vl" "tesseract-cpu")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  OCR Worker Manager${NC}"
    echo -e "${CYAN}========================================${NC}"
}

get_worker_pid() {
    local name="$1"
    local service_type
    case "$name" in
        paddle-text)   service_type="ocr-paddle" ;;
        paddle-vl)     service_type="ocr-paddle-vl" ;;
        tesseract-cpu) service_type="ocr-tesseract" ;;
    esac
    # Find python process with matching WORKER_SERVICE_TYPE env var
    for pid in $(pgrep -f "python.*app\.main" 2>/dev/null); do
        if tr '\0' '\n' < /proc/$pid/environ 2>/dev/null | grep -q "WORKER_SERVICE_TYPE=$service_type"; then
            echo "$pid"
            return
        fi
    done
}

do_status() {
    print_header
    printf "%-16s %-8s %-8s %-8s %-12s %s\n" "WORKER" "PID" "CPU%" "MEM%" "UPTIME" "LOG"
    echo "------------------------------------------------------------------------"
    for name in "${ALL_WORKERS[@]}"; do
        pid=$(get_worker_pid "$name")
        log_file="${LOG_DIR}/worker_${name//-/_}.log"
        if [ -n "$pid" ]; then
            stats=$(ps -p "$pid" -o %cpu,%mem,etime --no-headers 2>/dev/null)
            cpu=$(echo "$stats" | awk '{print $1}')
            mem=$(echo "$stats" | awk '{print $2}')
            uptime=$(echo "$stats" | awk '{print $3}')
            printf "%-16s ${GREEN}%-8s${NC} %-8s %-8s %-12s %s\n" "$name" "$pid" "$cpu" "$mem" "$uptime" "$log_file"
        else
            printf "%-16s ${RED}%-8s${NC} %-8s %-8s %-12s %s\n" "$name" "stopped" "-" "-" "-" "$log_file"
        fi
    done
    echo ""
}

do_start() {
    local workers=("$@")
    print_header

    for name in "${workers[@]}"; do
        script="${DEPLOY_DIR}/${name}/run-local.sh"
        log_file="${LOG_DIR}/worker_${name//-/_}.log"

        if [ ! -f "$script" ]; then
            echo -e "${RED}[x] ${name}: run-local.sh not found${NC}"
            continue
        fi

        # Check if already running
        pid=$(get_worker_pid "$name")
        if [ -n "$pid" ]; then
            echo -e "${YELLOW}[~] ${name}: already running (PID ${pid}), skipping${NC}"
            continue
        fi

        echo -e "${GREEN}[+] Starting ${name}...${NC}"
        bash "$script" > "$log_file" 2>&1 &
        echo "    PID: $!  |  Log: $log_file"
    done

    # Wait a moment then show status
    echo ""
    echo "Waiting 3s for workers to initialize..."
    sleep 3
    do_status
}

do_stop() {
    local workers=("$@")
    print_header

    for name in "${workers[@]}"; do
        pid=$(get_worker_pid "$name")
        if [ -n "$pid" ]; then
            echo -e "${YELLOW}[-] Stopping ${name} (PID ${pid})...${NC}"
            kill "$pid" 2>/dev/null
            # Wait up to 5s for graceful shutdown
            for i in $(seq 1 10); do
                if ! kill -0 "$pid" 2>/dev/null; then break; fi
                sleep 0.5
            done
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
                echo -e "${RED}    Force killed${NC}"
            else
                echo -e "${GREEN}    Stopped${NC}"
            fi
        else
            echo -e "${CYAN}[~] ${name}: not running${NC}"
        fi
    done
}

do_restart() {
    local workers=("$@")
    do_stop "${workers[@]}"
    echo ""
    sleep 1
    do_start "${workers[@]}"
}

# --- Main ---

case "${1:-}" in
    stop)
        shift
        targets=("${@:-${ALL_WORKERS[@]}}")
        [ ${#targets[@]} -eq 0 ] && targets=("${ALL_WORKERS[@]}")
        do_stop "${targets[@]}"
        ;;
    status)
        do_status
        ;;
    restart)
        shift
        targets=("${@:-${ALL_WORKERS[@]}}")
        [ ${#targets[@]} -eq 0 ] && targets=("${ALL_WORKERS[@]}")
        do_restart "${targets[@]}"
        ;;
    help|-h|--help)
        echo "Usage: bash start-all.sh [command] [workers...]"
        echo ""
        echo "Commands:"
        echo "  (default)   Start workers (all or specified)"
        echo "  stop        Stop workers (all or specified)"
        echo "  restart     Restart workers (all or specified)"
        echo "  status      Show worker status"
        echo ""
        echo "Workers: ${ALL_WORKERS[*]}"
        echo ""
        echo "Examples:"
        echo "  bash start-all.sh                       # Start all"
        echo "  bash start-all.sh paddle-text paddle-vl # Start specific"
        echo "  bash start-all.sh stop paddle-vl        # Stop one"
        echo "  bash start-all.sh restart                # Restart all"
        echo "  bash start-all.sh status                 # Show status"
        ;;
    *)
        # Default: start specified workers or all
        if [ $# -eq 0 ]; then
            targets=("${ALL_WORKERS[@]}")
        else
            targets=("$@")
        fi
        do_start "${targets[@]}"
        ;;
esac
