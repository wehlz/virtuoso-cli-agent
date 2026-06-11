@echo off
cd /d %~dp0\..
REM Build the standalone executable and embed the custom icon if assets\icons\virtuoso.ico exists.
set ICON_ARG=
if exist assets\icons\virtuoso.ico (
    set ICON_ARG=--icon=assets/icons/virtuoso.ico
) else if exist asset\icons\virtuoso.ico (
    set ICON_ARG=--icon=asset/icons/virtuoso.ico
)
python scripts\build_standalone.py %ICON_ARG%
