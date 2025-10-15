@echo off
echo ================================================
echo  E/R Fan Control System - Dashboard Launcher
echo ================================================
echo.

echo [1/3] Killing all Python processes...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo      Done!

echo [2/3] Clearing Python cache...
python -Bc "import pathlib; import shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]" 2>nul
echo      Done!

echo [3/3] Starting dashboard...
echo.
echo ================================================
echo  Dashboard starting on http://localhost:8501
echo ================================================
echo.
set PYTHONIOENCODING=utf-8
streamlit run src/hmi/dashboard.py --server.port 8501

pause
