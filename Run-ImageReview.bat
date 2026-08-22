@echo off
pushd "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set "PYLAUNCHER=1"
) else (
  set "PYLAUNCHER=0"
)

echo Checking Python...
if "%PYLAUNCHER%"=="1" (
  py -3 -c "import sys; print(sys.version)"
) else (
  python -c "import sys; print(sys.version)"
)
if errorlevel 1 (
  echo ERROR: Python 3 not found. Install Python 3.7+ and try again.
  popd
  pause
  exit /b 1
)

echo Installing dependencies compatible with this Python...
if "%PYLAUNCHER%"=="1" (
  py -3 -m pip install "flask>=2.0.0,<3.0.0" "pillow>=8.0.0,<10.0.0"
) else (
  python -m pip install "flask>=2.0.0,<3.0.0" "pillow>=8.0.0,<10.0.0"
)
if errorlevel 1 (
  echo ERROR: pip install failed. See messages above.
  popd
  pause
  exit /b 1
)

echo Verifying imports...
if "%PYLAUNCHER%"=="1" (
  py -3 -c "import flask, PIL; print('flask', flask.__version__, '| pillow', PIL.__version__)"
) else (
  python -c "import flask, PIL; print('flask', flask.__version__, '| pillow', PIL.__version__)"
)
if errorlevel 1 (
  echo ERROR: Flask/Pillow still not importable.
  popd
  pause
  exit /b 1
)

if not "%~1"=="" (
  set "IMAGE_FOLDER=%~1"
) else if exist "%~dp0combined\" (
  set "IMAGE_FOLDER=%~dp0combined"
) else (
  set "IMAGE_FOLDER=%~dp0."
)

echo.
echo Starting Image Review Tool on http://localhost:5055
echo Image folder: %IMAGE_FOLDER%
echo Also reachable on this PC's LAN IP:5055 (printed when ready).
echo Keep this window open while reviewing. Browser opens when the server is ready.
echo.

if "%PYLAUNCHER%"=="1" (
  py -3 "%~dp0image_review\app.py" "%IMAGE_FOLDER%"
) else (
  python "%~dp0image_review\app.py" "%IMAGE_FOLDER%"
)

popd
pause
