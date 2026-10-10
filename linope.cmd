@echo off
cd /d "%~dp0"
if /I "%~1"=="terminal" goto titled
if not "%~1"=="" goto once

:titled
for /f "usebackq delims=" %%T in (`python -c "import ctypes; b=ctypes.create_unicode_buffer(1024); ctypes.windll.kernel32.GetConsoleTitleW(b,1024); print(b.value)"`) do set "LINOPE_PREVIOUS_TITLE=%%T"
title linope
if "%~1"=="" goto interactive
python -m kernel.command %*
exit /b %ERRORLEVEL%

:interactive
python -m kernel.command terminal
set "LINOPE_EXIT=%ERRORLEVEL%"
if not "%LINOPE_EXIT%"=="0" pause
exit /b %LINOPE_EXIT%

:once
python -m kernel.command %*
exit /b %ERRORLEVEL%
