@echo off
setlocal
REM ============================================================
REM  Skill installer for this project folder
REM    1) taste-skill  + mcp-builder  ->  .claude\skills\
REM    2) GSD (Get Shit Done)         ->  .claude\  (via npm)
REM  Double-click this file, or run it from a terminal.
REM ============================================================

cd /d "%~dp0"
set "STAGE=%~dp0_skills-install"
set "DEST=%~dp0.claude\skills"

echo.
echo === Step 1/3: copying taste-skill and mcp-builder into .claude\skills ===
echo.
if not exist "%STAGE%" (
  echo [!] Staging folder not found: %STAGE%
  echo     Skipping step 1.
) else (
  if not exist "%DEST%" mkdir "%DEST%"
  xcopy "%STAGE%\*" "%DEST%\" /E /I /Y >nul
  if errorlevel 1 (
    echo [!] Copy failed.
    pause
    exit /b 1
  )
  echo     Copied.
  rmdir /S /Q "%STAGE%"
  echo     Staging folder removed.
)

echo.
echo === Step 2/3: installing gsd-sdk globally (required by all /gsd:* skills) ===
echo.
call npm install -g get-shit-done-cc@latest
if errorlevel 1 (
  echo.
  echo [!] npm install failed. Is Node.js installed?  https://nodejs.org
  pause
  exit /b 1
)

echo.
echo === Step 3/3: installing GSD into this project (.claude\) ===
echo.
call npx get-shit-done-cc@latest --claude --local
if errorlevel 1 (
  echo.
  echo [!] GSD install failed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  Done. Restart Claude Code in this folder, then try:
echo    /gsd:help
echo    "use the taste skill to redesign the landing page"
echo    "use mcp-builder to scaffold an MCP server"
echo ============================================================
echo.
pause
