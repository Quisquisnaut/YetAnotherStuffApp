@echo off
rem Start the Tkinter GUI (or pass --console for text menus). Requires Python 3.
setlocal
cd /d "%~dp0"
title Stuff App
set PYTHONUTF8=1
chcp 65001 >nul
where py >nul 2>nul
if %errorlevel%==0 goto run_py
where python >nul 2>nul
if %errorlevel%==0 goto run_python
echo.
echo Python 3 is not installed (or not on the PATH).
echo Install it from https://www.python.org/downloads/windows/
echo (tick "Add python.exe to PATH") or from the Microsoft Store, then start this file again.
echo.
if not defined STUFFAPP_NO_PAUSE pause
exit /b 1
:run_py
py -3 main.py %*
goto end
:run_python
python main.py %*
goto end
:end
set "STUFFAPP_EXIT=%errorlevel%"
if not "%STUFFAPP_EXIT%"=="0" if not defined STUFFAPP_NO_PAUSE pause
exit /b %STUFFAPP_EXIT%
