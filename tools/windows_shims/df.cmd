@echo off
setlocal
set TARGET=%~1
if /I "%~1"=="-T" set TARGET=%~2
if "%TARGET%"=="" set TARGET=%CD%
echo Filesystem     Type 1K-blocks Used Available Use%% Mounted on
echo %TARGET%       ntfs 1 1 1 1%% %TARGET%
exit /b 0
