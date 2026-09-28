@echo off
setlocal

REM Stop any process currently listening on port 3130.
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":3130 .*LISTENING"') do (
    echo Stopping PID %%P listening on port 3130...
    taskkill /F /PID %%P >nul 2>&1
)

REM Stop any process currently listening on port 3131.
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":3131 .*LISTENING"') do (
    echo Stopping PID %%P listening on port 3131...
    taskkill /F /PID %%P >nul 2>&1
)

start "AirThink" cmd /k "cd /d AirThink && run.bat"
start "AirCode" cmd /k "cd /d AirCode && run.bat"

echo Waiting for services to start...
:wait
timeout /t 1 /nobreak >nul
netstat -ano -p tcp | findstr "LISTENING" | findstr ":3130 " >nul
if errorlevel 1 goto wait

start "" "http://127.0.0.1:3130/index.html"

endlocal
