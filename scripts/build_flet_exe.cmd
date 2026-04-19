@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_flet_exe.ps1" %*
exit /b %ERRORLEVEL%
