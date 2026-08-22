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

echo Starting PhotogramQC...
if "%PYLAUNCHER%"=="1" (
  py -3 "%~dp0photogramqc.py" %*
) else (
  python "%~dp0photogramqc.py" %*
)

popd
