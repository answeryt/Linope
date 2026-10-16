@echo off
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
python -m tui.launch %*
exit /b %ERRORLEVEL%
