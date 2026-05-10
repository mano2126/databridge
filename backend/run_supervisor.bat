@echo off
REM ============================================================
REM DataBridge Supervisor Launcher (Windows)
REM v95_p106 (2026-05-09 본부장님 비전)
REM ============================================================
REM Usage:
REM   run_supervisor.bat start             : Supervisor + Backend + Frontend
REM   run_supervisor.bat start backend     : Supervisor + Backend
REM   run_supervisor.bat start frontend    : Supervisor + Frontend
REM   run_supervisor.bat start daemon      : Supervisor only
REM   run_supervisor.bat stop              : Supervisor + 자식 종료
REM   run_supervisor.bat status            : 상태 확인
REM ============================================================
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set DATA_DIR=%SCRIPT_DIR%data
set LOGS_DIR=%SCRIPT_DIR%logs
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

set SUPERVISOR_PID=%DATA_DIR%\supervisor.pid
set SUPERVISOR_LOG=%LOGS_DIR%\supervisor.log
set SUPERVISOR_PORT=8765

set CMD=%1
set OPT=%2
if "%CMD%"=="" set CMD=status

if "%CMD%"=="start" goto :do_start
if "%CMD%"=="stop" goto :do_stop
if "%CMD%"=="status" goto :do_status
if "%CMD%"=="foreground" goto :do_foreground
if "%CMD%"=="fg" goto :do_foreground
goto :usage

:do_start
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] venv not found at: %SCRIPT_DIR%venv\Scripts\activate.bat
    echo   Run: python -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt
    exit /b 1
)

REM 이미 실행 중인지 체크
if exist "%SUPERVISOR_PID%" (
    set /p OLD_PID=<"%SUPERVISOR_PID%"
    tasklist /FI "PID eq !OLD_PID!" 2>NUL | find "!OLD_PID!" >NUL
    if not errorlevel 1 (
        echo [INFO] Supervisor already running ^(PID=!OLD_PID!^)
        echo   Status: http://127.0.0.1:%SUPERVISOR_PORT%/supervisor/status
        exit /b 0
    )
)

echo [START] DataBridge Supervisor 데몬 시작...
call venv\Scripts\activate.bat
REM start /B 로 백그라운드 실행, 결과 PID 는 Python에서 supervisor.pid 로 기록
start "DataBridge Supervisor" /B /MIN cmd /c "python supervisor.py >> %SUPERVISOR_LOG% 2>&1"
timeout /t 3 /nobreak >nul

REM PID 파일이 생성되었는지 확인
if exist "%SUPERVISOR_PID%" (
    set /p NEW_PID=<"%SUPERVISOR_PID%"
    echo   ✓ Supervisor 시작됨 ^(PID=!NEW_PID!^)
    echo     API : http://127.0.0.1:%SUPERVISOR_PORT%/supervisor/status
    echo     Log : %SUPERVISOR_LOG%
    
    REM 자동 시작 옵션 처리
    if /I "%OPT%"=="daemon" goto :start_done
    if /I "%OPT%"=="frontend" (
        call :start_frontend
        goto :start_done
    )
    if /I "%OPT%"=="backend" (
        call :start_backend
        goto :start_done
    )
    REM 기본: 둘 다 시작
    call :start_backend
    call :start_frontend
) else (
    echo   ✗ Supervisor 시작 실패
    type "%SUPERVISOR_LOG%" | more
    exit /b 1
)
:start_done
exit /b 0

:start_backend
echo   → Backend 자동 시작 ^(mode=safe^)
curl -s -X POST "http://127.0.0.1:%SUPERVISOR_PORT%/supervisor/start" ^
     -H "Content-Type: application/json" -d "{\"mode\":\"safe\"}"
echo.
exit /b 0

:start_frontend
echo   → Frontend 자동 시작 ^(mode=auto^)
curl -s -X POST "http://127.0.0.1:%SUPERVISOR_PORT%/supervisor/frontend/start" ^
     -H "Content-Type: application/json" -d "{\"mode\":\"auto\"}"
echo.
exit /b 0

:do_stop
if not exist "%SUPERVISOR_PID%" (
    echo [INFO] Supervisor not running
    exit /b 0
)
set /p PID=<"%SUPERVISOR_PID%"
echo [STOP] Supervisor 종료 ^(PID=%PID%^)...
taskkill /PID %PID% /T 2>nul
timeout /t 5 /nobreak >nul
taskkill /PID %PID% /F /T 2>nul
del "%SUPERVISOR_PID%" 2>nul
echo   ✓ Supervisor 종료됨
exit /b 0

:do_status
if not exist "%SUPERVISOR_PID%" (
    echo ○ Supervisor 중지됨
    exit /b 1
)
set /p PID=<"%SUPERVISOR_PID%"
tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL
if errorlevel 1 (
    echo ○ Supervisor 중지됨 ^(stale PID file^)
    del "%SUPERVISOR_PID%" 2>nul
    exit /b 1
)
echo ● Supervisor 실행 중 ^(PID=%PID%, port=%SUPERVISOR_PORT%^)
echo.
curl -s -m 2 "http://127.0.0.1:%SUPERVISOR_PORT%/supervisor/status"
echo.
exit /b 0

:do_foreground
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] venv not found
    exit /b 1
)
echo [FOREGROUND] Supervisor 포그라운드 실행 ^(Ctrl+C 종료^)
call venv\Scripts\activate.bat
python supervisor.py
exit /b 0

:usage
echo Usage: %0 {start^|stop^|status^|foreground} [backend^|frontend^|daemon]
echo.
echo   start                : 데몬 + Backend + Frontend 모두 시작
echo   start backend        : 데몬 + Backend
echo   start frontend       : 데몬 + Frontend
echo   start daemon         : 데몬만 (관리자 UI에서 시작)
echo   stop                 : Supervisor + 자식 종료
echo   status               : 현재 상태
echo   foreground           : 포그라운드 (디버깅)
exit /b 1
