@echo off
chcp 65001 >nul
title Google Form Bot Dashboard
echo ========================================================
echo    🤖 Google Form Automation Bot - Web Dashboard
echo ========================================================
echo.
echo กำลังเปิดเบราว์เซอร์และเริ่มการทำงานของเซิร์ฟเวอร์...
echo คุณสามารถเข้าใช้งานได้ที่: http://127.0.0.1:5000
echo.
start http://127.0.0.1:5000
python src\web_server.py
pause
