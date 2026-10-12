@echo off
rem Start YetAnotherStuffApp (text menus). Needs Python 3 from python.org or the Microsoft Store.
cd /d "%~dp0"
title Stuff App
set PYTHONUTF8=1
chcp 65001 >nul
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 main.py %*
    goto end
)
where python >nul 2>nul
if %errorlevel%==0 (
    python main.py %*
    goto end
)
echo.
echo Python 3 is not installed (or not on the PATH).
echo Install it from https://www.python.org/downloads/windows/
echo (tick "Add python.exe to PATH") or from the Microsoft Store, then start this file again.
echo.
pause
exit /b 1
:end
if errorlevel 1 pause
