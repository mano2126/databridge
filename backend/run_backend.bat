@echo off
REM ============================================================
REM DataBridge Backend Launcher (Unified)
REM ------------------------------------------------------------
REM Location: D:\project\databridge_full\backend\run_backend.bat
REM Usage   : Double-click. Select mode by number. Stop with Ctrl+C.
REM
REM Replaces: run_backend.bat (old safe-only)
REM           run_backend_experiment.bat (Phase 2 thread)
REM           run_backend_mp.bat (Phase 3a process)
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

:MENU
cls
echo ============================================================
echo   DataBridge Backend -- Mode Selection
echo ============================================================
echo.
echo   Select execution mode:
echo.
echo   [1] SAFE          -- Single thread, proven stable
echo                        Use for: Production, real customer DB (first time)
echo                        Speed  : ~4,800 rows/s baseline
echo                        Risk   : Lowest
echo.
echo   [2] MULTIPROCESS  -- 4 worker processes (Phase 3a)
echo                        Use for: Large tables (1M+ rows), after validation
echo                        Speed  : ~9,300 rows/s (2x baseline)
echo                        Risk   : Medium -- requires ~4x memory
echo.
echo   [3] THREAD        -- 4 worker threads (Phase 2, diagnostic only)
echo                        Use for: Comparison/diagnostic only
echo                        Speed  : ~3,700 rows/s (slower than safe!)
echo                        Risk   : Known slow due to GIL
echo.
echo   [4] CUSTOM        -- Manual environment variable setup
echo                        Advanced users only
echo.
echo   [Q] Quit
echo.
echo ------------------------------------------------------------
echo   Recommendation:
echo     * First run / production  -^> [1] SAFE
echo     * Large dataset + tested  -^> [2] MULTIPROCESS
echo     * Just pressing Enter     -^> [1] SAFE (default)
echo ------------------------------------------------------------
echo.

set "MODE_CHOICE="
set /p "MODE_CHOICE=Enter choice [1/2/3/4/Q] (default=1): "

REM Default = 1 (Safe)
if "!MODE_CHOICE!"=="" set "MODE_CHOICE=1"

REM Normalize lowercase q
if /i "!MODE_CHOICE!"=="q" goto QUIT

if "!MODE_CHOICE!"=="1" goto MODE_SAFE
if "!MODE_CHOICE!"=="2" goto MODE_MP
if "!MODE_CHOICE!"=="3" goto MODE_THREAD
if "!MODE_CHOICE!"=="4" goto MODE_CUSTOM

echo.
echo Invalid choice: !MODE_CHOICE!
echo.
pause
goto MENU


REM ============================================================
REM MODE 1: SAFE
REM ============================================================
:MODE_SAFE
set "MODE_NAME=SAFE (single thread)"
set "DATABRIDGE_DEV_MODE=1"
set "DATABRIDGE_CHUNK_EXPERIMENT="
set "DATABRIDGE_CHUNK_MODE="
goto LAUNCH


REM ============================================================
REM MODE 2: MULTIPROCESS (Phase 3a)
REM ============================================================
:MODE_MP
set "MODE_NAME=MULTIPROCESS (4 worker processes, Phase 3a)"
set "DATABRIDGE_DEV_MODE=1"
set "DATABRIDGE_CHUNK_EXPERIMENT=1"
set "DATABRIDGE_CHUNK_MODE=process"
goto LAUNCH


REM ============================================================
REM MODE 3: THREAD (Phase 2 diagnostic)
REM ============================================================
:MODE_THREAD
echo.
echo WARNING: THREAD mode is known to be SLOWER than SAFE mode
echo          due to Python GIL limitation. Use for diagnostic only.
echo.
set "CONFIRM="
set /p "CONFIRM=Continue anyway? [y/N]: "
if /i not "!CONFIRM!"=="y" goto MENU

set "MODE_NAME=THREAD (4 worker threads, diagnostic)"
set "DATABRIDGE_DEV_MODE=1"
set "DATABRIDGE_CHUNK_EXPERIMENT=1"
set "DATABRIDGE_CHUNK_MODE=thread"
goto LAUNCH


REM ============================================================
REM MODE 4: CUSTOM
REM ============================================================
:MODE_CUSTOM
echo.
echo Custom mode - set environment variables manually:
echo.
set "DEV="
set /p "DEV=DATABRIDGE_DEV_MODE [1/0] (default=1): "
if "!DEV!"=="" set "DEV=1"

set "EXP="
set /p "EXP=DATABRIDGE_CHUNK_EXPERIMENT [1/empty] (default=empty): "

set "CM="
set /p "CM=DATABRIDGE_CHUNK_MODE [process/thread/empty] (default=empty): "

set "MODE_NAME=CUSTOM (user-defined)"
set "DATABRIDGE_DEV_MODE=!DEV!"
set "DATABRIDGE_CHUNK_EXPERIMENT=!EXP!"
set "DATABRIDGE_CHUNK_MODE=!CM!"
goto LAUNCH


REM ============================================================
REM LAUNCH
REM ============================================================
:LAUNCH
cls
echo ============================================================
echo   DataBridge Backend -- Starting
echo ============================================================
echo.
echo   Mode      : !MODE_NAME!
echo   Location  : %CD%
echo   Date      : %date% %time%
echo.
echo   Environment:
echo     DATABRIDGE_DEV_MODE         = !DATABRIDGE_DEV_MODE!
if defined DATABRIDGE_CHUNK_EXPERIMENT (
    if not "!DATABRIDGE_CHUNK_EXPERIMENT!"=="" (
        echo     DATABRIDGE_CHUNK_EXPERIMENT = !DATABRIDGE_CHUNK_EXPERIMENT!
    ) else (
        echo     DATABRIDGE_CHUNK_EXPERIMENT = ^(disabled^)
    )
) else (
    echo     DATABRIDGE_CHUNK_EXPERIMENT = ^(disabled^)
)
if defined DATABRIDGE_CHUNK_MODE (
    if not "!DATABRIDGE_CHUNK_MODE!"=="" (
        echo     DATABRIDGE_CHUNK_MODE       = !DATABRIDGE_CHUNK_MODE!
    ) else (
        echo     DATABRIDGE_CHUNK_MODE       = ^(default^)
    )
) else (
    echo     DATABRIDGE_CHUNK_MODE       = ^(default^)
)
echo.
echo ------------------------------------------------------------

REM Check venv
if not exist "venv\Scripts\activate.bat" (
    echo.
    echo [ERROR] venv not found at: %CD%\venv\Scripts\activate.bat
    echo.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate venv
    pause
    exit /b 1
)

echo   venv      : activated
echo   Python    :
python --version 2>&1
echo.
echo ------------------------------------------------------------
echo.
echo   Starting uvicorn... (press Ctrl+C to stop)
echo.
echo ============================================================
echo.

python -m uvicorn main:app --port 8000 --reload

echo.
echo ============================================================
echo   Backend stopped (exit code: %errorlevel%)
echo ============================================================
echo.

set "AGAIN="
set /p "AGAIN=Launch again? [y/N]: "
if /i "!AGAIN!"=="y" goto MENU

goto QUIT


:QUIT
echo.
echo Goodbye.
timeout /t 2 >nul
endlocal
exit /b 0
