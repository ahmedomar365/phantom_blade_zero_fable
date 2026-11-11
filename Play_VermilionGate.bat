@echo off
rem Vermilion Gate: starts the local server and opens the game as a full-screen desktop window.
rem The window uses its own browser profile so that sound and controller rumble work without a mouse click.
cd /d "%~dp0"
set PORT=5260
set URL=http://localhost:%PORT%/
set PROFILE=%LOCALAPPDATA%\VermilionGate\profile

rem start the server only if nothing answers on the port yet
powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient('127.0.0.1', %PORT%)).Close(); exit 0 } catch { exit 1 }"
if errorlevel 1 start "Vermilion Gate server" /min node server.js %PORT%

set FLAGS=--app=%URL% --start-fullscreen --autoplay-policy=no-user-gesture-required --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check
set CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe
if exist "%CHROME%" (
  start "" "%CHROME%" %FLAGS%
) else (
  start "" msedge %FLAGS%
)
