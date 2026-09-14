@echo off
setlocal
if exist "%~dp0local.cmd" call "%~dp0local.cmd"
if not defined LO_CONVERTER_PYTHON set "LO_CONVERTER_PYTHON=python.exe"
"%LO_CONVERTER_PYTHON%" "%~dp0pipeline.py" %*
exit /b %errorlevel%
