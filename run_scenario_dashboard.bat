@echo off
REM ESS AI System - Scenario Dashboard Launcher
REM
REM 시나리오 시뮬레이션과 통합된 대시보드

echo ================================================================================
echo ESS AI 제어 시스템 - 시나리오 대시보드
echo ================================================================================
echo.
echo 시나리오를 실시간으로 볼 수 있는 대시보드입니다.
echo.
echo 대시보드 상단에서 시나리오를 선택하세요:
echo   1. 정상 운전 (Normal Operation)
echo   2. 고부하 운전 (High Load)
echo   3. 냉각 실패 (Cooling Failure)
echo   4. 압력 저하 (Pressure Drop)
echo.
echo Dashboard URL: http://localhost:8502
echo.
echo Press Ctrl+C to stop
echo.

streamlit run src\hmi\dashboard_with_scenario.py --server.port 8502 --server.address localhost

pause
