@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  规则的起点 — 财税政策搜索引擎（本地版）
echo ============================================
echo.

echo 检查 Python…
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3
    pause
    exit /b 1
)

echo 安装 / 检查依赖…
python -m pip install flask requests urllib3 -q

echo.
echo 启动服务器（端口 5080）…
echo 浏览器打开：http://localhost:5080
echo.
start http://localhost:5080
python scripts\tax_server.py

pause
