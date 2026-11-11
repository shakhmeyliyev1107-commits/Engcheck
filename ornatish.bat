@echo off
title EngCheck - o'rnatish
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\ornatish.ps1"
if errorlevel 1 echo. & echo O'rnatishda xato chiqdi. Yuqoridagi matnni nusxalab yuboring.
pause
