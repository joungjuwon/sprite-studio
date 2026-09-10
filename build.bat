@echo off
REM Sprite Studio build launcher (ASCII only - do not add non-English text here)
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 goto NOPY

python build.py
goto END

:NOPY
echo [ERROR] Python not found in PATH.
echo Install from python.org and check "Add python.exe to PATH".
pause

:END
