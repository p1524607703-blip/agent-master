@echo off
cd /d "%~dp0"
py -3 device_connector.py install
if errorlevel 1 echo Installation stopped. Original Codex was not changed.
pause
