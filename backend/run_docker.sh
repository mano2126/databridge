#!/bin/bash
# ============================================================
# DataBridge Docker Launcher (macOS / Linux)
# v95_p107 hotfix_097 (2026-05-13 본부장님 본질 처방)
#
# 본부장님 짚으심:
#   "run_docker 라고 실행하면 어떤 db 있는지 보여주고 그렇게 입력하게 만들면 안될까?"
#
# 본질:
#   컨테이너 이름 하드코딩 X — 본부장님 환경의 실제 컨테이너 동적 발견.
#   본부장님이 새 컨테이너 (redis 등) 추가해도 코드 수정 불필요.
# ============================================================
# Usage:
#   bash run_docker.sh                          # 인터랙티브 (컨테이너 목록 + 선택)
#   bash run_docker.sh status                   # 전체 상태
#   bash run_docker.sh start <name1> [name2..]  # 특정 컨테이너 시작
#   bash run_docker.sh start all                # 발견된 모든 컨테이너 시작
#   bash run_docker.sh stop <name1> [name2..]   # 특정 컨테이너 중지
#   bash run_docker.sh stop all                 # 모든 컨테이너 중지
#   bash run_docker.sh restart <name1> [name2..]
#   bash run_docker.sh logs <name>              # 컨테이너 로그 tail
#   bash run_docker.sh ping <name1> [name2..]   # DB ping 테스트
#   bash run_docker.sh nuke                     # Docker Desktop 종료 (위험)
# ============================================================
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 색상
if [ -t 1 ]; then
    G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[0;34m'; BOLD='\033[1m'; N='\033[0m'
else
    G=''; R=''; Y=''; B=''; BOLD=''; N=''
fi

OS_NAME="$(uname -s)"

# ──────────────────────────────────────────────────────────
# 보조 함수
# ──────────────────────────────────────────────────────────

is_docker_alive() {
    docker info > /dev/null 2>&1
}

is_docker_desktop_running() {
    if [ "$OS_NAME" != "Darwin" ]; then return 0; fi
    pgrep -f "Docker Desktop" > /dev/null 2>&1
}

# 컨테이너 상태: running | exited | created | paused | restarting | dead | missing
container_status() {
    local name="$1"
    docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null || echo "missing"
}

# 컨테이너 이미지
container_image() {
    local name="$1"
    docker inspect -f '{{.Config.Image}}' "$name" 2>/dev/null || echo "?"
}

# 발견된 모든 컨테이너 목록 (실행 + 중지 포함)
list_all_containers() {
    docker ps -a --format '{{.Names}}' 2>/dev/null
}

# 상태 아이콘
status_icon() {
    case "$1" in
        running)    echo -e "${G}●${N}";;
        exited)     echo -e "${R}○${N}";;
        paused)     echo -e "${Y}‖${N}";;
        restarting) echo -e "${Y}↻${N}";;
        dead)       echo -e "${R}✗${N}";;
        created)    echo -e "${Y}◌${N}";;
        missing)    echo -e "${R}?${N}";;
        *)          echo -e "${Y}?${N}";;
    esac
}

# Docker Desktop 시작 (macOS)
start_docker_desktop() {
    if [ "$OS_NAME" != "Darwin" ]; then
        echo -e "${R}[ERROR] Docker Desktop 자동 시작은 macOS 만 지원${N}"
        echo "        Linux: sudo systemctl start docker"
        return 1
    fi
    echo -e "${B}[START]${N} Docker Desktop 앱 실행"
    open -a Docker 2>/dev/null || open /Applications/Docker.app
    echo -ne "        ${Y}Docker daemon 준비 대기 (최대 90초)${N}"
    local waited=0
    while ! is_docker_alive; do
        sleep 3
        waited=$((waited + 3))
        echo -n "."
        if [ $waited -ge 90 ]; then
            echo ""
            echo -e "${R}[FAIL] Docker daemon 90초 내 응답 없음${N}"
            return 1
        fi
    done
    echo ""
    echo -e "        ${G}✓ Docker daemon 준비됨 (${waited}초)${N}"
    return 0
}

# 컨테이너 시작 — 이름 배열 받음
start_named_containers() {
    local started=0 skipped=0 failed=0
    for c in "$@"; do
        local s=$(container_status "$c")
        case "$s" in
            running)
                echo -e "  ${G}✓${N} $c  ${Y}(이미 실행 중)${N}"
                skipped=$((skipped+1))
                ;;
            exited|created|paused)
                echo -ne "  ${B}[START]${N} $c "
                if docker start "$c" > /dev/null 2>&1; then
                    echo -e "${G}✓${N}"
                    started=$((started+1))
                else
                    echo -e "${R}✗ 시작 실패${N}"
                    failed=$((failed+1))
                fi
                ;;
            missing)
                echo -e "  ${R}✗${N} $c  ${R}(컨테이너 없음 — docker run / compose up 필요)${N}"
                failed=$((failed+1))
                ;;
            *)
                echo -e "  ${Y}?${N} $c  ${Y}(상태=$s)${N}"
                ;;
        esac
    done
    echo ""
    echo -e "  요약: ${G}$started 시작${N} / ${Y}$skipped 스킵${N} / ${R}$failed 실패${N}"
}

stop_named_containers() {
    local stopped=0 skipped=0 failed=0
    for c in "$@"; do
        local s=$(container_status "$c")
        case "$s" in
            running|restarting|paused)
                echo -ne "  ${B}[STOP]${N} $c "
                if docker stop "$c" > /dev/null 2>&1; then
                    echo -e "${G}✓${N}"
                    stopped=$((stopped+1))
                else
                    echo -e "${R}✗${N}"
                    failed=$((failed+1))
                fi
                ;;
            *)
                echo -e "  ${Y}-${N} $c  ${Y}(already $s)${N}"
                skipped=$((skipped+1))
                ;;
        esac
    done
    echo ""
    echo -e "  요약: ${G}$stopped 중지${N} / ${Y}$skipped 스킵${N} / ${R}$failed 실패${N}"
}

# all 키워드 → 모든 컨테이너 이름 반환
expand_targets() {
    local args=("$@")
    if [ "${#args[@]}" -eq 1 ] && [ "${args[0]}" = "all" ]; then
        list_all_containers
    else
        printf '%s\n' "${args[@]}"
    fi
}

# 인터랙티브 모드 — 컨테이너 목록 표시 + 사용 예시 + 입력 받음
interactive_mode() {
    echo -e "${BOLD}DataBridge Docker — 인터랙티브${N}"
    echo ""

    # daemon 체크
    if ! is_docker_alive; then
        echo -e "${R}○${N} Docker daemon 응답 없음"
        read -r -p "$(echo -e ${Y}Docker Desktop 자동 시작?${N} [y/N]: )" yn
        if [[ "$yn" =~ ^[Yy]$ ]]; then
            start_docker_desktop || exit 1
        else
            exit 1
        fi
    fi
    echo -e "${G}●${N} Docker daemon: OK"
    echo ""

    # 컨테이너 목록
    echo -e "${BOLD}발견된 컨테이너${N} (docker ps -a):"
    local names=()
    while IFS= read -r name; do
        [ -z "$name" ] && continue
        names+=("$name")
    done < <(list_all_containers)

    if [ "${#names[@]}" -eq 0 ]; then
        echo -e "  ${Y}(없음 — docker run / compose up 으로 생성 필요)${N}"
        exit 0
    fi

    local i=1
    for name in "${names[@]}"; do
        local s=$(container_status "$name")
        local img=$(container_image "$name")
        printf "  [%d] %s  %-25s  %s  %s\n" \
            "$i" "$(status_icon $s)" "$name" "$s" "${img:0:40}"
        i=$((i+1))
    done

    echo ""
    echo -e "${BOLD}사용 예시${N}:"
    if [ "${#names[@]}" -ge 2 ]; then
        echo -e "  ${B}bash run_docker.sh start ${names[0]} ${names[1]}${N}"
    fi
    if [ "${#names[@]}" -ge 1 ]; then
        echo -e "  ${B}bash run_docker.sh start all${N}                ${Y}# 모든 컨테이너${N}"
        echo -e "  ${B}bash run_docker.sh stop ${names[0]}${N}"
        echo -e "  ${B}bash run_docker.sh logs ${names[0]}${N}"
        echo -e "  ${B}bash run_docker.sh ping ${names[0]}${N}              ${Y}# DB SELECT 1${N}"
    fi
    echo -e "  ${B}bash run_docker.sh status${N}                 ${Y}# 전체 진단${N}"
    echo ""

    # 입력 받기
    echo -e "${BOLD}어떤 작업?${N}"
    echo "  명령 + 컨테이너 이름 (또는 all) 입력"
    echo "  예: start db_mssql db_mysql"
    echo "  예: start all"
    echo "  취소: Ctrl+C 또는 빈 입력"
    echo ""
    read -r -p "$(echo -e ${BOLD}\>${N} )" user_input

    if [ -z "$user_input" ]; then
        echo "취소됨"
        exit 0
    fi

    # 입력 파싱 → 재귀 실행
    echo ""
    echo -e "${B}실행${N}: bash run_docker.sh $user_input"
    echo "─────────────────────────────────────"
    # shellcheck disable=SC2086
    exec bash "$SCRIPT_DIR/run_docker.sh" $user_input
}

# DB ping
db_ping_one() {
    local c="$1"
    local s=$(container_status "$c")
    if [ "$s" != "running" ]; then
        echo -e "  ${Y}-${N} $c  ${Y}(not running)${N}"
        return
    fi
    local img=$(container_image "$c")

    # 이미지 보고 ping 명령 결정
    if echo "$img" | grep -qi "mssql"; then
        if timeout 3 docker exec "$c" /opt/mssql-tools18/bin/sqlcmd -C -N -Q "SELECT 1" -U sa -P 'Bridge@1234' > /dev/null 2>&1; then
            echo -e "  ${G}✓${N} $c  ${G}MSSQL ping OK${N}"
        else
            echo -e "  ${Y}?${N} $c  ${Y}MSSQL no-ping${N} (비밀번호 또는 sqlcmd 경로 확인)"
        fi
    elif echo "$img" | grep -qi "mysql\|mariadb"; then
        if timeout 3 docker exec "$c" mysql -uroot -p'Bridge@1234' -e "SELECT 1" > /dev/null 2>&1; then
            echo -e "  ${G}✓${N} $c  ${G}MySQL ping OK${N}"
        else
            echo -e "  ${Y}?${N} $c  ${Y}MySQL no-ping${N} (비밀번호 확인)"
        fi
    elif echo "$img" | grep -qi "postgres"; then
        if timeout 3 docker exec "$c" pg_isready > /dev/null 2>&1; then
            echo -e "  ${G}✓${N} $c  ${G}PostgreSQL ping OK${N}"
        else
            echo -e "  ${Y}?${N} $c  ${Y}PostgreSQL no-ping${N}"
        fi
    elif echo "$img" | grep -qi "redis"; then
        if timeout 3 docker exec "$c" redis-cli ping > /dev/null 2>&1; then
            echo -e "  ${G}✓${N} $c  ${G}Redis ping OK${N}"
        else
            echo -e "  ${Y}?${N} $c  ${Y}Redis no-ping${N}"
        fi
    else
        echo -e "  ${Y}?${N} $c  ${Y}ping 불가 (이미지 미지원: $img)${N}"
    fi
}

# ──────────────────────────────────────────────────────────
# 명령 분기
# ──────────────────────────────────────────────────────────

CMD="${1:-}"

# 인자 없으면 인터랙티브
if [ -z "$CMD" ]; then
    interactive_mode
fi

shift || true   # CMD 토큰 소비

case "$CMD" in
    start)
        # daemon 자동 시작
        if ! is_docker_alive; then
            echo -e "${Y}○${N} Docker daemon 응답 없음 — 자동 시작 시도"
            start_docker_desktop || exit 1
            echo ""
        fi
        # 인자 없으면 인터랙티브로 fallback
        if [ "$#" -eq 0 ]; then
            echo -e "${Y}[INFO]${N} 컨테이너 이름을 지정하지 않았습니다 — 인터랙티브 모드"
            exec bash "$SCRIPT_DIR/run_docker.sh"
        fi
        # 대상 확장 (all → 전체)
        targets=()
        while IFS= read -r name; do
            [ -z "$name" ] && continue
            targets+=("$name")
        done < <(expand_targets "$@")
        if [ "${#targets[@]}" -eq 0 ]; then
            echo -e "${R}[ERROR] 대상 컨테이너 없음${N}"
            exit 1
        fi
        echo -e "${BOLD}컨테이너 시작 (${#targets[@]}개)${N}"
        start_named_containers "${targets[@]}"
        echo ""
        echo -e "${BOLD}DB ping${N}"
        for t in "${targets[@]}"; do
            db_ping_one "$t"
        done
        ;;

    stop)
        if ! is_docker_alive; then
            echo -e "${Y}[INFO] Docker daemon 응답 없음 — 컨테이너도 이미 중지${N}"
            exit 0
        fi
        if [ "$#" -eq 0 ]; then
            exec bash "$SCRIPT_DIR/run_docker.sh"
        fi
        targets=()
        while IFS= read -r name; do
            [ -z "$name" ] && continue
            targets+=("$name")
        done < <(expand_targets "$@")
        echo -e "${BOLD}컨테이너 중지 (${#targets[@]}개)${N}"
        echo -e "${Y}[INFO]${N} Docker Desktop 앱 자체는 유지"
        echo ""
        stop_named_containers "${targets[@]}"
        ;;

    restart)
        if ! is_docker_alive; then
            start_docker_desktop || exit 1
        fi
        if [ "$#" -eq 0 ]; then
            exec bash "$SCRIPT_DIR/run_docker.sh"
        fi
        targets=()
        while IFS= read -r name; do
            [ -z "$name" ] && continue
            targets+=("$name")
        done < <(expand_targets "$@")
        echo -e "${BOLD}컨테이너 재시작 (${#targets[@]}개)${N}"
        stop_named_containers "${targets[@]}"
        sleep 2
        start_named_containers "${targets[@]}"
        echo ""
        for t in "${targets[@]}"; do
            db_ping_one "$t"
        done
        ;;

    status)
        echo -e "${BOLD}DataBridge Docker 상태${N}"
        echo ""
        if [ "$OS_NAME" = "Darwin" ]; then
            if is_docker_desktop_running; then
                echo -e "  ${G}●${N} Docker Desktop 앱: 실행 중"
            else
                echo -e "  ${R}○${N} Docker Desktop 앱: 종료됨"
            fi
        fi
        if is_docker_alive; then
            echo -e "  ${G}●${N} Docker daemon: 응답 OK"
        else
            echo -e "  ${R}○${N} Docker daemon: 응답 없음"
            exit 1
        fi
        echo ""
        echo -e "${BOLD}컨테이너 (docker ps -a)${N}"
        local found=0
        while IFS= read -r name; do
            [ -z "$name" ] && continue
            found=1
            local s=$(container_status "$name")
            local img=$(container_image "$name")
            printf "  %s %-25s  %s  %s\n" \
                "$(status_icon $s)" "$name" "$s" "${img:0:40}"
        done < <(list_all_containers)
        if [ "$found" -eq 0 ]; then
            echo -e "  ${Y}(컨테이너 없음)${N}"
        fi
        ;;

    logs)
        target="${1:-}"
        if [ -z "$target" ]; then
            echo -e "${R}[ERROR] 컨테이너 이름 필요${N}: bash run_docker.sh logs <name>"
            exit 1
        fi
        echo -e "${B}[LOGS]${N} docker logs -f --tail 50 $target"
        docker logs -f --tail 50 "$target"
        ;;

    ping)
        if ! is_docker_alive; then
            echo -e "${R}[ERROR] Docker daemon 응답 없음${N}"
            exit 1
        fi
        if [ "$#" -eq 0 ]; then
            # ping 대상 없으면 모든 실행 중 컨테이너 ping
            echo -e "${BOLD}모든 running 컨테이너 ping${N}"
            while IFS= read -r name; do
                [ -z "$name" ] && continue
                local s=$(container_status "$name")
                if [ "$s" = "running" ]; then
                    db_ping_one "$name"
                fi
            done < <(list_all_containers)
        else
            echo -e "${BOLD}DB ping${N}"
            for c in "$@"; do
                db_ping_one "$c"
            done
        fi
        ;;

    nuke)
        echo -e "${R}${BOLD}[NUKE]${N} Docker Desktop 자체 종료"
        echo -e "${Y}[WARN]${N} 본부장님 macOS 의 모든 컨테이너 중지됩니다"
        read -r -p "$(echo -e ${R}계속?${N} [y/N]: )" yn
        if [[ ! "$yn" =~ ^[Yy]$ ]]; then
            echo "취소됨"
            exit 0
        fi
        if is_docker_alive; then
            stop_named_containers $(list_all_containers)
        fi
        if [ "$OS_NAME" = "Darwin" ]; then
            echo -e "  Docker Desktop 앱 종료..."
            osascript -e 'quit app "Docker"' 2>/dev/null || pkill -f "Docker Desktop" || true
            sleep 2
            echo -e "  ${G}✓ Docker Desktop 종료됨${N}"
        else
            echo -e "  Linux: sudo systemctl stop docker"
        fi
        ;;

    -h|--help|help)
        echo "Usage: $0 [command] [container_name...]"
        echo ""
        echo "Commands:"
        echo "  (no args)           인터랙티브 (컨테이너 목록 + 선택)"
        echo "  status              전체 상태"
        echo "  start <name|all>    컨테이너 시작"
        echo "  stop <name|all>     컨테이너 중지"
        echo "  restart <name|all>  재시작"
        echo "  logs <name>         로그 tail"
        echo "  ping [name|all]     DB ping (인자 없으면 모든 running)"
        echo "  nuke                Docker Desktop 자체 종료"
        ;;

    *)
        echo -e "${R}[ERROR] 알 수 없는 명령: $CMD${N}"
        echo "도움말: bash $0 help"
        exit 1
        ;;
esac
