@echo off
pushd "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

echo Installing app and build dependencies...
%PY% -m pip install -r "%~dp0requirements.txt" "pyinstaller>=5.13.2,<6.0.0"
if errorlevel 1 (
  echo ERROR: pip install failed.
  popd
  exit /b 1
)

echo Building PhotogramQC.exe...
%PY% -m PyInstaller --noconfirm --clean "%~dp0PhotogramQC.spec"
if errorlevel 1 (
  echo ERROR: PyInstaller failed.
  popd
  exit /b 1
)

echo.
echo Built: %~dp0dist\PhotogramQC.exe
popd
