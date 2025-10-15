"""
Streamlit 기반 HMI 대시보드 (시나리오 통합 버전)
실시간 모니터링 및 제어 인터페이스 + 시나리오 시뮬레이션
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import time
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.hmi.hmi_state_manager import (
    HMIStateManager,
    ControlMode,
    AlarmPriority,
    ForceMode60HzState
)
from src.gps.gps_processor import GPSData, SeaRegion, Season, NavigationState
from src.diagnostics.vfd_monitor import DanfossStatusBits, VFDStatus
from src.simulation.scenarios import SimulationScenarios, ScenarioType


class DashboardWithScenario:
    """Streamlit 대시보드 (시나리오 통합)"""

    def __init__(self):
        """초기화"""
        # Session state 초기화
        if 'hmi_manager' not in st.session_state:
            st.session_state.hmi_manager = HMIStateManager()

        if 'scenario_engine' not in st.session_state:
            st.session_state.scenario_engine = SimulationScenarios()

        if 'sensor_history' not in st.session_state:
            st.session_state.sensor_history = {
                'T4': [],
                'T5': [],
                'T6': [],
                'timestamps': []
            }

        if 'energy_history' not in st.session_state:
            st.session_state.energy_history = {
                'sw_pumps': [],
                'fw_pumps': [],
                'er_fans': [],
                'timestamps': []
            }

        # GPS 시뮬레이션 데이터 초기화
        if 'gps_initialized' not in st.session_state:
            gps_data = GPSData(
                timestamp=datetime.now(),
                latitude=35.1,
                longitude=129.0,
                speed_knots=15.5,
                heading_degrees=225.0,
                utc_time=datetime.now()
            )
            st.session_state.hmi_manager.update_gps_data(gps_data)
            st.session_state.gps_initialized = True

        self.hmi_manager: HMIStateManager = st.session_state.hmi_manager
        self.scenario_engine: SimulationScenarios = st.session_state.scenario_engine

    def run(self):
        """대시보드 실행"""
        # 페이지 설정
        st.set_page_config(
            page_title="ESS AI 제어 시스템 - 시나리오 대시보드",
            page_icon="⚡",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # 전역 CSS 스타일
        st.markdown("""
            <style>
            .stButton button {
                width: 85px !important;
                min-width: 85px !important;
                max-width: 85px !important;
            }
            </style>
        """, unsafe_allow_html=True)

        # 제목
        st.title("⚡ ESS AI 제어 시스템 - 시나리오 대시보드")
        st.caption("HMM 16K급 선박 - 시나리오 기반 시뮬레이션")

        # 사이드바
        self._render_sidebar()

        # 시나리오 제어 패널
        self._render_scenario_control()

        # 탭 생성
        tab1, tab2 = st.tabs([
            "📊 메인 대시보드",
            "📈 성능 모니터링"
        ])

        with tab1:
            self._render_main_dashboard()

        with tab2:
            self._render_performance_monitoring()

        # 자동 새로고침 (3초 간격)
        st_autorefresh(interval=3000, limit=None, key="auto_refresh_dashboard_with_scenario")

    def _render_sidebar(self):
        """사이드바 렌더링"""
        st.sidebar.header("시스템 상태")
        st.sidebar.metric("현재 시간", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # 시나리오 정보
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎬 시나리오 상태")

        info = self.scenario_engine.get_scenario_info()
        if info:
            st.sidebar.success(f"**{info['name']}**")
            st.sidebar.caption(info['description'])
            st.sidebar.progress(float(info['progress'].replace('%', '')) / 100.0)
            st.sidebar.metric("경과 시간", f"{info['elapsed_seconds']:.0f}초")

            if info['is_complete']:
                st.sidebar.warning("⚠️ 시나리오 완료됨")

    def _render_scenario_control(self):
        """시나리오 제어 패널"""
        st.markdown("### 🎬 시나리오 제어")

        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 3])

        with col1:
            if st.button("1️⃣ 정상 운전", use_container_width=True):
                self.scenario_engine.start_scenario(ScenarioType.NORMAL_OPERATION)
                st.rerun()

        with col2:
            if st.button("2️⃣ 고부하", use_container_width=True):
                self.scenario_engine.start_scenario(ScenarioType.HIGH_LOAD)
                st.rerun()

        with col3:
            if st.button("3️⃣ 냉각 실패", use_container_width=True):
                self.scenario_engine.start_scenario(ScenarioType.COOLING_FAILURE)
                st.rerun()

        with col4:
            if st.button("4️⃣ 압력 저하", use_container_width=True):
                self.scenario_engine.start_scenario(ScenarioType.PRESSURE_DROP)
                st.rerun()

        with col5:
            info = self.scenario_engine.get_scenario_info()
            if info:
                st.info(f"📊 {info['name']} - {info['progress']}")

        st.markdown("---")

    def _render_main_dashboard(self):
        """메인 대시보드 렌더링"""
        st.header("📊 실시간 시스템 모니터링")

        # 시나리오 엔진에서 실시간 데이터 가져오기
        values = self.scenario_engine.get_current_values()

        # 핵심 입력 센서 (AI 제어 입력값)
        st.markdown("### 🎯 핵심 입력 센서 (실시간)")
        col1, col2, col3, col4, col5 = st.columns(5)

        T4 = values['T4']
        T5 = values['T5']
        T6 = values['T6']
        PX1 = values['PX1']
        engine_load = values['engine_load']

        with col1:
            delta_t5 = T5 - 35.0
            st.metric("⭐ T5 (FW 출구)", f"{T5:.1f}°C",
                     f"{delta_t5:+.1f}°C",
                     delta_color="inverse" if delta_t5 > 0 else "normal")
        with col2:
            delta_t4 = T4 - 45.0
            st.metric("⭐ T4 (FW 입구)", f"{T4:.1f}°C",
                     f"{delta_t4:+.1f}°C",
                     delta_color="inverse" if delta_t4 > 0 else "normal")
        with col3:
            delta_t6 = T6 - 43.0
            st.metric("⭐ T6 (E/R 온도)", f"{T6:.1f}°C",
                     f"{delta_t6:+.1f}°C",
                     delta_color="inverse" if delta_t6 > 0 else "normal")
        with col4:
            delta_px = PX1 - 2.0
            st.metric("⭐ PX1 (압력)", f"{PX1:.2f} bar",
                     f"{delta_px:+.2f}",
                     delta_color="inverse" if delta_px < 0 else "normal")
        with col5:
            st.metric("⭐ 엔진 부하", f"{engine_load:.0f}%")

        # 추가 모니터링 센서
        st.markdown("### 📡 추가 모니터링 센서")
        col1, col2, col3, col4 = st.columns(4)

        T1 = values['T1']
        T2 = values['T2']
        T3 = values['T3']
        T7 = values['T7']

        with col1:
            st.metric("T1 (SW 입구)", f"{T1:.1f}°C")
        with col2:
            st.metric("T2 (No.1 SW 출구)", f"{T2:.1f}°C")
        with col3:
            st.metric("T3 (No.2 SW 출구)", f"{T3:.1f}°C")
        with col4:
            st.metric("T7 (외기 온도)", f"{T7:.1f}°C")

        st.markdown("---")

        # 온도 트렌드 그래프
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🌡️ 온도 트렌드")
            self._render_temperature_trend(T4, T5, T6)

        with col2:
            st.subheader("📊 시나리오 진행")
            self._render_scenario_progress()

    def _render_temperature_trend(self, T4, T5, T6):
        """온도 트렌드 그래프"""
        now = datetime.now()

        # 데이터 추가
        if len(st.session_state.sensor_history['timestamps']) == 0 or \
           (now - st.session_state.sensor_history['timestamps'][-1]).seconds >= 1:

            st.session_state.sensor_history['T4'].append(T4)
            st.session_state.sensor_history['T5'].append(T5)
            st.session_state.sensor_history['T6'].append(T6)
            st.session_state.sensor_history['timestamps'].append(now)

            # 최근 600개만 유지 (10분)
            if len(st.session_state.sensor_history['timestamps']) > 600:
                st.session_state.sensor_history['T4'] = st.session_state.sensor_history['T4'][-600:]
                st.session_state.sensor_history['T5'] = st.session_state.sensor_history['T5'][-600:]
                st.session_state.sensor_history['T6'] = st.session_state.sensor_history['T6'][-600:]
                st.session_state.sensor_history['timestamps'] = st.session_state.sensor_history['timestamps'][-600:]

        # 그래프 생성
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=st.session_state.sensor_history['timestamps'],
            y=st.session_state.sensor_history['T4'],
            name='T4 (FW 입구)',
            line=dict(color='green', width=2)
        ))

        fig.add_trace(go.Scatter(
            x=st.session_state.sensor_history['timestamps'],
            y=st.session_state.sensor_history['T5'],
            name='T5 (FW 출구)',
            line=dict(color='blue', width=2)
        ))

        fig.add_trace(go.Scatter(
            x=st.session_state.sensor_history['timestamps'],
            y=st.session_state.sensor_history['T6'],
            name='T6 (E/R 온도)',
            line=dict(color='red', width=2)
        ))

        # 목표 온도 라인
        fig.add_hline(y=35.0, line_dash="dash", line_color="blue",
                     annotation_text="T5 목표 (35°C)",
                     annotation_position="right")
        fig.add_hline(y=43.0, line_dash="dash", line_color="red",
                     annotation_text="T6 목표 (43°C)",
                     annotation_position="right")
        fig.add_hline(y=48.0, line_dash="dash", line_color="orange",
                     annotation_text="T4 한계 (48°C)",
                     annotation_position="right")

        fig.update_layout(
            height=350,
            margin=dict(l=20, r=120, t=50, b=90),
            xaxis_title="시간",
            yaxis_title="온도 (°C)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.45,
                xanchor="center",
                x=0.5
            )
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_scenario_progress(self):
        """시나리오 진행 상태"""
        info = self.scenario_engine.get_scenario_info()

        if not info:
            st.info("시나리오를 선택해주세요")
            return

        # 진행률
        progress_pct = float(info['progress'].replace('%', ''))
        st.metric("진행률", info['progress'])
        st.progress(progress_pct / 100.0)

        # 시간 정보
        col1, col2 = st.columns(2)
        with col1:
            st.metric("경과 시간", f"{info['elapsed_seconds']:.0f}초")
        with col2:
            remaining = info['duration_minutes'] * 60 - info['elapsed_seconds']
            st.metric("남은 시간", f"{remaining:.0f}초")

        # 완료 여부
        if info['is_complete']:
            st.success("✅ 시나리오 완료!")
        else:
            st.info(f"🎬 {info['name']} 실행 중...")

    def _render_performance_monitoring(self):
        """성능 모니터링"""
        st.header("📈 성능 분석")

        # 현재 센서 값
        values = self.scenario_engine.get_current_values()

        # 에너지 절감 비교
        st.subheader("⚡ 에너지 절감 효과")

        sw_freq = 48.4
        fw_freq = 48.4
        er_freq = 47.3

        # 정격 출력
        sw_rated = 132.0
        fw_rated = 75.0
        er_rated = 54.3

        # 운전 대수
        sw_running = 2
        fw_running = 2
        er_running = 3

        # 전력 계산
        def calc_power(freq, rated_kw, running_count):
            return rated_kw * ((freq / 60.0) ** 3) * running_count

        # 60Hz vs AI
        sw_60hz = calc_power(60.0, sw_rated, sw_running)
        fw_60hz = calc_power(60.0, fw_rated, fw_running)
        er_60hz = calc_power(60.0, er_rated, er_running)
        total_60hz = sw_60hz + fw_60hz + er_60hz

        sw_ai = calc_power(sw_freq, sw_rated, sw_running)
        fw_ai = calc_power(fw_freq, fw_rated, fw_running)
        er_ai = calc_power(er_freq, er_rated, er_running)
        total_ai = sw_ai + fw_ai + er_ai

        total_saved = total_60hz - total_ai
        total_ratio = (total_saved / total_60hz) * 100

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("60Hz 고정 운전", f"{total_60hz:.1f} kW")
        with col2:
            st.metric("AI 제어 운전", f"{total_ai:.1f} kW")
        with col3:
            st.metric("절감 전력", f"{total_saved:.1f} kW", f"-{total_ratio:.1f}%", delta_color="inverse")
        with col4:
            st.metric("절감률", f"{total_ratio:.1f}%")


def main():
    """메인 함수"""
    dashboard = DashboardWithScenario()
    dashboard.run()


if __name__ == "__main__":
    main()
