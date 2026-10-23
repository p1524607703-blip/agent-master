@echo off
if exist "%LOCALAPPDATA%\CodexDeviceRelay\bound\provider.txt" (notepad "%LOCALAPPDATA%\CodexDeviceRelay\bound\provider.txt") else (echo Run step 1 first. & pause)
