@echo off
cd /d "%~dp0"
echo Starting Scratch Cookie Cottage...
echo.
echo Open in your browser:  http://127.0.0.1:5000
echo Admin (this PC):       http://127.0.0.1:5000/admin
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
  echo Admin (phone Wi-Fi):   http://%%A:5000/admin
)
echo.
echo Press Ctrl+C to stop the server.
echo.
".venv\Scripts\python.exe" app.py
pause
