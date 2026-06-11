@echo off
cd /d %~dp0\..
set ICON_ARG=
if exist assets\icons\virtuoso.ico (
    set ICON_ARG=--icon=assets/icons/virtuoso.ico
) else if exist asset\icons\virtuoso.ico (
    set ICON_ARG=--icon=asset/icons/virtuoso.ico
)
python scripts\build_standalone.py %ICON_ARG%
