@echo off
REM ESS AI System - Streamlit HMI Dashboard Launcher
REM
REM Usage: run_dashboard.bat
REM
REM This script launches the Streamlit-based HMI dashboard
REM for the ESS AI Control System.

echo ================================================================================
echo ESS AI 제어 시스템 - HMI Dashboard
echo ================================================================================
echo.
echo Starting Streamlit dashboard...
echo Dashboard will be available at: http://localhost:8501
echo.
echo Press Ctrl+C to stop the dashboard
echo.

streamlit run src\hmi\dashboard.py --server.port 8501 --server.address localhost

pause
