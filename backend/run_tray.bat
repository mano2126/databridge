@echo off
REM ============================================================
REM DataBridge Tray App Launcher (Windows)
REM v95_p107
REM Usage: run_tray.bat {start|stop|status|foreground}
REM ============================================================
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set DATA_DIR=%SCRIPT_DIR%data
set LOGS_DIR=%SCRIPT_DIR%logs
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

set TRAY_PID=%DATA_DIR%\tray_app.pid
set TRAY_LOG=%LOGS_DIR%\tray_app.log

set CMD=%1
if "%CMD%"=="" set CMD=status

if "%CMD%"=="start" goto :do_start
if "%CMD%"=="stop" goto :do_stop
if "%CMD%"=="status" goto :do_status
if "%CMD%"=="foreground" goto :do_foreground
if "%CMD%"=="fg" goto :do_foreground
goto :usage

:do_start
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] venv not found
    exit /b 1
)

REM 의존성 체크
call venv\Scripts\activate.bat
python -c "import pystray, PIL" 2>NUL
if errorlevel 1 (
    echo [INFO] pystray/Pillow 설치 중...
    pip install --quiet pystray==0.19.5 Pillow==10.4.0
)

REM 이미 실행 중인지
if exist "%TRAY_PID%" (
    set /p OLD_PID=<"%TRAY_PID%"
    tasklist /FI "PID eq !OLD_PID!" 2>NUL | find "!OLD_PID!" >NUL
    if not errorlevel 1 (
        echo [INFO] Tray app already running (PID=!OLD_PID!)
        exit /b 0
    )
)

echo [START] Tray app 시작...
REM Windows: pythonw.exe (콘솔 창 안 뜸) 사용
if exist "venv\Scripts\pythonw.exe" (
    start "" /B "venv\Scripts\pythonw.exe" tray_app.py
) else (
    start "DataBridge Tray" /B /MIN cmd /c "python tray_app.py >> %TRAY_LOG% 2>&1"
)
timeout /t 2 /nobreak >nul

REM PID 추출 — Python 안에서 자체 기록함
if exist "%TRAY_PID%" (
    set /p NEW_PID=<"%TRAY_PID%"
    echo   ✓ Tray app 시작됨 (PID=!NEW_PID!)
    echo     작업표시줄 우측 트레이를 확인하세요
) else (
    echo   ✗ Tray app 시작 실패
    type "%TRAY_LOG%" | more
    exit /b 1
)
exit /b 0

:do_stop
if not exist "%TRAY_PID%" (
    echo [INFO] Tray app not running
    exit /b 0
)
set /p PID=<"%TRAY_PID%"
echo [STOP] Tray app 종료 (PID=%PID%)
taskkill /PID %PID% /T 2>nul
timeout /t 2 /nobreak >nul
taskkill /PID %PID% /F /T 2>nul
del "%TRAY_PID%" 2>nul
echo   ✓ Tray app 종료됨
exit /b 0

:do_status
if not exist "%TRAY_PID%" (
    echo ○ Tray app 중지됨
    exit /b 1
)
set /p PID=<"%TRAY_PID%"
tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL
if errorlevel 1 (
    echo ○ Tray app 중지됨
    del "%TRAY_PID%" 2>nul
    exit /b 1
)
echo ● Tray app 실행 중 (PID=%PID%)
exit /b 0

:do_foreground
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] venv not found
    exit /b 1
)
call venv\Scripts\activate.bat
python tray_app.py
exit /b 0

:usage
echo Usage: %0 {start^|stop^|status^|foreground}
exit /b 1
