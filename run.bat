@echo off
chcp 65001 >nul
echo [房产监控] 开始执行日报采集...
cd /d "%~dp0"
python main.py
echo [房产监控] 执行完成
pause
