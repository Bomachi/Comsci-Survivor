@echo off
setlocal
cd /d "%~dp0"
title Comsci Survivor - hand control setup
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0..\Comsci-Survivor\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Python environment not found. Run setup_comsci.bat first.
    pause & exit /b 1
)
echo [1/2] Installing MediaPipe and OpenCV...
"%PY%" -m pip install -r requirements-hand.txt
if errorlevel 1 ( echo pip install failed. & pause & exit /b 1 )
echo [2/2] Downloading the hand model (about 8 MB)...
if not exist "assets\models" mkdir "assets\models"
curl.exe -L --retry 3 -o "assets\models\hand_landmarker.task" "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
if errorlevel 1 ( echo Download failed. Check your internet and run this file again. & pause & exit /b 1 )
echo.
echo Done. Start the game and press F7 to steer with your hand.
pause
