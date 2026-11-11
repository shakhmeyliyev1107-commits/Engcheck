@echo off
title EngCheck
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\ishga-tushirish.ps1"
if errorlevel 1 echo. & echo Xato chiqdi. Yuqoridagi matnni nusxalab yuboring. & pause
