"""
Streamlit 기반 HMI 대시보드
실시간 모니터링 및 제어 인터페이스
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
from src.control.integrated_controller import IntegratedController


class Dashboard:
    """Streamlit 대시보드"""

    def __init__(self):
        """초기화"""
        # Session state 초기화
        if 'hmi_manager' not in st.session_state:
            st.session_state.hmi_manager = HMIStateManager()

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
            # 시뮬레이션: 부산 출발 -> 싱가포르 항로
            gps_data = GPSData(
                timestamp=datetime.now(),
                latitude=35.1,  # 부산 근처
                longitude=129.0,
                speed_knots=15.5,
                heading_degrees=225.0,
                utc_time=datetime.now()
            )
            st.session_state.hmi_manager.update_gps_data(gps_data)
            st.session_state.gps_initialized = True

        # 선택된 탭 인덱스 저장
        if 'selected_tab' not in st.session_state:
            st.session_state.selected_tab = 0

        # 시나리오 엔진 초기화
        if 'scenario_engine' not in st.session_state:
            st.session_state.scenario_engine = SimulationScenarios()
            # 기본 시나리오 시작
            st.session_state.scenario_engine.start_scenario(ScenarioType.NORMAL_OPERATION)

        # 시나리오 모드 플래그 (기본적으로 시나리오 데이터 사용)
        if 'use_scenario_data' not in st.session_state:
            st.session_state.use_scenario_data = True  # 메인 대시보드가 항상 살아있게

        # 현재 선택된 시나리오 추적
        if 'current_scenario_type' not in st.session_state:
            st.session_state.current_scenario_type = ScenarioType.NORMAL_OPERATION

        # IntegratedController 초기화 (Rule-based AI + ML 예측)
        # 강제 재초기화 (코드 수정 반영을 위해)
        if 'controller_version' not in st.session_state or st.session_state.controller_version != 12:
            st.session_state.integrated_controller = IntegratedController(
                enable_predictive_control=True  # ML 활성화 (선제적 온도 예측 제어 - 핵심 기능)
            )
            st.session_state.controller_version = 12  # V12: 온도 우선 대수 증설 (45°C 이상 주파수 무관)

        self.hmi_manager: HMIStateManager = st.session_state.hmi_manager
        self.scenario_engine: SimulationScenarios = st.session_state.scenario_engine
        self.integrated_controller: IntegratedController = st.session_state.integrated_controller

    def run(self):
        """대시보드 실행"""
        # 페이지 설정
        st.set_page_config(
            page_title="ESS AI 제어 시스템 - HMI Dashboard",
            page_icon="⚡",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # 전역 CSS 스타일
        st.markdown("""
            <style>
            /* 제어 패널 버튼 고정 너비 */
            .stButton button {
                width: 85px !important;
                min-width: 85px !important;
                max-width: 85px !important;
            }

            /* 60Hz 선택 버튼 - 회색 */
            button[kind="secondary"]:has(*:contains("◉ 60Hz")) {
                background-color: #78909C !important;
                color: white !important;
                border-color: #78909C !important;
            }

            /* AI 선택 버튼 - 녹색 */
            button[kind="secondary"]:has(*:contains("◉ AI")) {
                background-color: #66BB6A !important;
                color: white !important;
                border-color: #66BB6A !important;
            }

            /* 시나리오 선택 버튼 스타일 */
            button:has(*:contains("기본 제어 검증")),
            button:has(*:contains("고부하 제어 검증")),
            button:has(*:contains("냉각기 과열 보호 검증")),
            button:has(*:contains("압력 안전 제어 검증")) {
                white-space: nowrap !important;
                min-width: 120px !important;
                width: auto !important;
                max-width: none !important;
                min-height: 45px !important;
                height: auto !important;
                padding: 0.5rem 1.5rem !important;
                font-size: 1rem !important;
            }

            /* 탭 중복 렌더링 방지 */
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
            }

            .stTabs [data-baseweb="tab"] {
                height: 50px;
                white-space: pre-wrap;
                background-color: transparent;
            }
            </style>
        """, unsafe_allow_html=True)

        # 제목
        st.title("⚡ ESS Rule-based AI 제어 시스템 - HMI Dashboard")
        st.caption("HMM 16K급 선박 - NVIDIA Jetson Xavier NX 기반 | Rule-based AI + ML 최적화")

        # 사이드바
        self._render_sidebar()


        # 탭 생성
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
            "📊 메인 대시보드",
            "🎛️ 제어 패널",
            "📈 성능 모니터링",
            "🔔 알람 관리",
            "📚 학습 진행",
            "🗺️ GPS & 환경",
            "🔧 VFD 진단",
            "🎬 시나리오 테스트"
        ])

        with tab1:
            self._render_main_dashboard()

        with tab2:
            self._render_control_panel()

        with tab3:
            self._render_performance_monitoring()

        with tab4:
            self._render_alarm_management()

        with tab5:
            self._render_learning_progress()

        with tab6:
            self._render_gps_environment()

        with tab7:
            self._render_vfd_diagnostics()

        with tab8:
            self._render_scenario_testing()

        # 자동 새로고침 (3초 간격으로 변경하여 렌더링 부담 감소)
        st_autorefresh(interval=3000, limit=None, key="auto_refresh_main_dashboard")

    def _render_sidebar(self):
        """사이드바 렌더링"""
        st.sidebar.header("시스템 상태")

        # 현재 시간
        st.sidebar.metric("현재 시간", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # 긴급 정지 버튼
        st.sidebar.markdown("---")
        st.sidebar.subheader("🚨 긴급 제어")

        if st.sidebar.button("🛑 긴급 정지", type="primary", use_container_width=True):
            st.sidebar.error("긴급 정지 활성화!")
            st.sidebar.warning("모든 장비가 정지됩니다.")

        # 활성 알람 개수
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 알람 현황")

        active_alarms = self.hmi_manager.get_active_alarms()
        critical_alarms = [a for a in active_alarms if a.priority == AlarmPriority.CRITICAL]
        warning_alarms = [a for a in active_alarms if a.priority == AlarmPriority.WARNING]
        info_alarms = [a for a in active_alarms if a.priority == AlarmPriority.INFO]

        st.sidebar.metric("🔴 CRITICAL 알람", len(critical_alarms))
        st.sidebar.metric("🟡 WARNING 알람", len(warning_alarms))
        st.sidebar.metric("🔵 INFO 이벤트", len(info_alarms))

    def _render_main_dashboard(self):
        """메인 대시보드 렌더링"""
        st.header("📊 실시간 시스템 모니터링")

        # 핵심 입력 센서 (AI 제어 입력값)
        st.markdown("### 🎯 핵심 입력 센서 (AI 제어)")
        col1, col2, col3, col4, col5 = st.columns(5)

        # 데이터 소스 선택: 시나리오 모드면 시나리오 엔진, 아니면 고정값
        if st.session_state.use_scenario_data:
            values = self.scenario_engine.get_current_values()
            T4 = values['T4']
            T5 = values['T5']
            T6 = values['T6']
            PX1 = values['PX1']
            engine_load = values['engine_load']
            T1 = values['T1']
            T2 = values['T2']
            T3 = values['T3']
            T7 = values['T7']
            
            # IntegratedController를 호출하여 실제 제어 계산
            temperatures = {
                'T1': T1, 'T2': T2, 'T3': T3, 'T4': T4, 
                'T5': T5, 'T6': T6, 'T7': T7
            }
            pressure = PX1
            
            # 온도 시퀀스 업데이트 (예측 제어용)
            self.integrated_controller.update_temperature_sequence(
                temperatures, engine_load
            )
            
            # 제어 결정 계산
            # current_frequencies 준비
            # 시나리오 테스트에서 이미 사용 중인 current_frequencies 재사용
            if 'current_frequencies' not in st.session_state:
                st.session_state.current_frequencies = {
                    'sw_pump': self.hmi_manager.groups["SW_PUMPS"].target_frequency,
                    'fw_pump': self.hmi_manager.groups["FW_PUMPS"].target_frequency,
                    'er_fan': self.hmi_manager.groups["ER_FANS"].target_frequency,
                    'er_fan_count': 3,  # 기본 3대
                    'time_at_max_freq': 0,
                    'time_at_min_freq': 0
                }
            
            current_frequencies = st.session_state.current_frequencies
            
            control_decision = self.integrated_controller.compute_control(
                temperatures=temperatures,
                pressure=pressure,
                engine_load=engine_load,
                current_frequencies=current_frequencies
            )
            
            # HMI 매니저의 목표 주파수 업데이트
            self.hmi_manager.update_target_frequency("SW_PUMPS", control_decision.sw_pump_freq)
            self.hmi_manager.update_target_frequency("FW_PUMPS", control_decision.fw_pump_freq)
            self.hmi_manager.update_target_frequency("ER_FANS", control_decision.er_fan_freq)
            
            # 제어 결정을 세션에 저장 (다른 화면에서 사용)
            st.session_state.last_control_decision = control_decision
        else:
            # 시뮬레이션 데이터 (실제로는 data_collector에서 가져옴)
            T4 = 38.2  # FW 입구 -> FW 펌프 제어 (48°C 이하 유지)
            T5 = 35.2  # FW 출구 -> SW 펌프 제어 (34~36°C 유지)
            T6 = 43.5  # E/R 온도 -> E/R 팬 제어
            PX1 = 2.8  # SW 압력 -> 안전 제약
            engine_load = 75
            T1 = 28.5
            T2 = 32.3
            T3 = 32.2
            T7 = 25.0

        with col1:
            st.metric("⭐ T5 (FW 출구)", f"{T5:.1f}°C", "→ SW 펌프")
        with col2:
            st.metric("⭐ T4 (FW 입구)", f"{T4:.1f}°C", "→ FW 펌프")
        with col3:
            st.metric("⭐ T6 (E/R 온도)", f"{T6:.1f}°C", "→ E/R 팬")
        with col4:
            st.metric("⭐ PX1 (압력)", f"{PX1:.1f} bar", "→ 안전")
        with col5:
            st.metric("⭐ 엔진 부하", f"{engine_load:.1f}%", "→ 전체")

        # 추가 모니터링 센서
        st.markdown("### 📡 추가 모니터링 센서")
        col1, col2, col3, col4 = st.columns(4)

        # 데이터 소스 선택
        if st.session_state.use_scenario_data:
            T1 = values['T1']
            T2 = values['T2']
            T3 = values['T3']
            T7 = values['T7']
        else:
            # 시뮬레이션 데이터
            T1 = 28.5  # SW 입구 온도
            T2 = 32.3  # No.1 Cooler SW 출구
            T3 = 32.2  # No.2 Cooler SW 출구 (T2와 유사)
            T7 = 25.0  # 외기 온도

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
            st.subheader("🌡️ 온도 트렌드 (최근 10분)")
            self._render_temperature_trend()

        with col2:
            st.subheader("⚡ 에너지 절감률")
            self._render_energy_savings_gauge()

        st.markdown("---")

        # 장비 상태 다이어그램
        st.subheader("🔧 장비 운전 상태")
        self._render_equipment_diagram()

    def _render_temperature_trend(self):
        """온도 트렌드 그래프"""
        # 현재 온도 값 가져오기 (시나리오 데이터 또는 기본 시뮬레이션)
        if st.session_state.use_scenario_data:
            values = self.scenario_engine.get_current_values()
            current_T4 = values['T4']
            current_T5 = values['T5']
            current_T6 = values['T6']
        else:
            # 기본 시뮬레이션 데이터
            current_T4 = 38.0 + (len(st.session_state.sensor_history['T4']) % 10) * 0.15
            current_T5 = 35.0 + (len(st.session_state.sensor_history['T5']) % 10) * 0.1
            current_T6 = 43.0 + (len(st.session_state.sensor_history['T6']) % 10) * 0.1
        
        # 데이터 추가
        now = datetime.now()
        if len(st.session_state.sensor_history['timestamps']) == 0 or \
           (now - st.session_state.sensor_history['timestamps'][-1]).seconds >= 1:

            st.session_state.sensor_history['T4'].append(current_T4)
            st.session_state.sensor_history['T5'].append(current_T5)
            st.session_state.sensor_history['T6'].append(current_T6)
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

        # 목표 온도 라인 (라벨 위치 조정하여 그래프와 겹치지 않게)
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

    def _render_energy_savings_gauge(self):
        """에너지 절감률 게이지"""
        # 실제 제어 주파수 가져오기
        if st.session_state.use_scenario_data and hasattr(st.session_state, 'last_control_decision'):
            decision = st.session_state.last_control_decision
            sw_freq = decision.sw_pump_freq
            fw_freq = decision.fw_pump_freq
            er_freq = decision.er_fan_freq
            er_count = decision.er_fan_count
        else:
            sw_freq = self.hmi_manager.groups["SW_PUMPS"].target_frequency
            fw_freq = self.hmi_manager.groups["FW_PUMPS"].target_frequency
            er_freq = self.hmi_manager.groups["ER_FANS"].target_frequency
            er_count = 3
        
        # 실시간 에너지 절감률 계산
        sw_rated = 132.0  # kW
        fw_rated = 75.0
        er_rated = 54.3
        
        sw_running = 2
        fw_running = 2
        er_running = er_count
        
        def calc_power(freq, rated_kw, running_count):
            return rated_kw * ((freq / 60.0) ** 3) * running_count
        
        # 60Hz 기준
        sw_60hz = calc_power(60.0, sw_rated, sw_running)
        fw_60hz = calc_power(60.0, fw_rated, fw_running)
        er_60hz = calc_power(60.0, er_rated, er_running)
        total_60hz = sw_60hz + fw_60hz + er_60hz
        
        # AI 제어
        sw_ai = calc_power(sw_freq, sw_rated, sw_running)
        fw_ai = calc_power(fw_freq, fw_rated, fw_running)
        er_ai = calc_power(er_freq, er_rated, er_running)
        total_ai = sw_ai + fw_ai + er_ai
        
        # 절감률
        sw_savings = ((sw_60hz - sw_ai) / sw_60hz) * 100 if sw_60hz > 0 else 0
        fw_savings = ((fw_60hz - fw_ai) / fw_60hz) * 100 if fw_60hz > 0 else 0
        fan_savings = ((er_60hz - er_ai) / er_60hz) * 100 if er_60hz > 0 else 0
        avg_savings = ((total_60hz - total_ai) / total_60hz) * 100 if total_60hz > 0 else 0

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=avg_savings,
            title={'text': "전체 평균 절감률"},
            delta={'reference': 50.0, 'suffix': '%'},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkgreen"},
                'steps': [
                    {'range': [0, 30], 'color': "lightgray"},
                    {'range': [30, 50], 'color': "yellow"},
                    {'range': [50, 100], 'color': "lightgreen"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 46
                }
            }
        ))

        fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)

        # 상세 절감률
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("SW 펌프", f"{sw_savings:.1f}%")
        with col2:
            st.metric("FW 펌프", f"{fw_savings:.1f}%")
        with col3:
            st.metric("E/R 팬", f"{fan_savings:.1f}%")

    def _render_equipment_diagram(self):
        """장비 상태 다이어그램"""
        col1, col2, col3 = st.columns(3)

        # 각 그룹의 목표 주파수 가져오기
        sw_freq = self.hmi_manager.groups["SW_PUMPS"].target_frequency
        fw_freq = self.hmi_manager.groups["FW_PUMPS"].target_frequency
        er_freq = self.hmi_manager.groups["ER_FANS"].target_frequency
        
        # E/R 팬 운전 대수 (시나리오에서 업데이트될 수 있음)
        if hasattr(st.session_state, 'last_control_decision') and st.session_state.last_control_decision:
            er_fan_count = getattr(st.session_state.last_control_decision, 'er_fan_count', 3)
        else:
            er_fan_count = 3  # 기본값

        with col1:
            st.markdown("**SW 펌프 (132kW x 3대)**")
            for i in range(1, 4):
                status = "🟢 운전 중" if i <= 2 else "⚪ 대기"
                freq = sw_freq if i <= 2 else 0
                st.text(f"SW-P{i}: {status} ({freq:.1f} Hz)")

        with col2:
            st.markdown("**FW 펌프 (75kW x 3대)**")
            for i in range(1, 4):
                status = "🟢 운전 중" if i <= 2 else "⚪ 대기"
                freq = fw_freq if i <= 2 else 0
                st.text(f"FW-P{i}: {status} ({freq:.1f} Hz)")

        with col3:
            st.markdown(f"**E/R 팬 (54.3kW x 4대)** - {er_fan_count}대 운전 중")
            for i in range(1, 5):
                status = "🟢 운전 중" if i <= er_fan_count else "⚪ 대기"
                freq = er_freq if i <= er_fan_count else 0
                st.text(f"ER-F{i}: {status} ({freq:.1f} Hz)")

    def _render_control_panel(self):
        """제어 패널 렌더링"""
        st.header("🎛️ 그룹별 주파수 제어")
        st.info("💡 각 그룹별로 독립적으로 '60Hz 고정' 또는 'AI 제어'를 선택할 수 있습니다. 제어 명령은 운전 중인 장비에만 적용되며, Stand-by 장비는 영향을 받지 않습니다.")

        # 3개 그룹 제어 패널
        col1, col2, col3 = st.columns(3)

        with col1:
            self._render_group_control("SW_PUMPS", "SW 펌프 그룹")

        with col2:
            self._render_group_control("FW_PUMPS", "FW 펌프 그룹")

        with col3:
            self._render_group_control("ER_FANS", "E/R 팬 그룹")

        st.markdown("---")

        # 입력-목표-실제 비교 테이블
        st.subheader("📊 입력 조건 → AI 계산 → 목표 주파수 → 실제 반영")
        self._render_frequency_comparison_table()

    def _render_group_control(self, group_key: str, group_name: str):
        """그룹별 제어 패널"""
        st.subheader(group_name)

        group = self.hmi_manager.groups[group_key]

        st.markdown("**제어 모드**")

        # 버튼 2개를 작게 배치 (1:1:3 비율)
        col1, col2, col3 = st.columns([1, 1, 3])

        is_60hz = group.control_mode == ControlMode.FIXED_60HZ
        is_ai = group.control_mode == ControlMode.AI_CONTROL

        # 목표 주파수를 현재 모드에 맞게 동기화
        ai_frequency = 48.4 if "PUMP" in group_key else 47.3
        expected_target = 60.0 if is_60hz else ai_frequency

        # 목표 주파수가 현재 모드와 맞지 않으면 업데이트
        if abs(group.target_frequency - expected_target) > 0.1:
            self.hmi_manager.update_target_frequency(group_key, expected_target)

        # 60Hz 버튼
        with col1:
            # 선택 여부에 따라 스타일 변경
            if is_60hz:
                # 선택됨: 회색 배경
                st.markdown(f"""
                    <div style="width: 85px;">
                        <button style="
                            width: 100%;
                            height: 38px;
                            background-color: #78909C;
                            color: white;
                            border: 2px solid #78909C;
                            border-radius: 0.375rem;
                            font-size: 14px;
                            font-weight: 500;
                            cursor: default;
                        ">◉ 60Hz</button>
                    </div>
                """, unsafe_allow_html=True)
            else:
                # 선택 안 됨: 클릭 가능한 Streamlit 버튼
                if st.button("○ 60Hz", key=f"btn_60hz_{group_key}", type="secondary"):
                    self.hmi_manager.set_control_mode(group_key, ControlMode.FIXED_60HZ)
                    self.hmi_manager.update_target_frequency(group_key, 60.0)
                    st.rerun()

        # AI 버튼
        with col2:
            if is_ai:
                # 선택됨: 녹색 배경
                st.markdown(f"""
                    <div style="width: 85px;">
                        <button style="
                            width: 100%;
                            height: 38px;
                            background-color: #66BB6A;
                            color: white;
                            border: 2px solid #66BB6A;
                            border-radius: 0.375rem;
                            font-size: 14px;
                            font-weight: 500;
                            cursor: default;
                        ">◉ AI</button>
                    </div>
                """, unsafe_allow_html=True)
            else:
                # 선택 안 됨: 클릭 가능한 Streamlit 버튼
                if st.button("○ AI", key=f"btn_ai_{group_key}", type="secondary"):
                    self.hmi_manager.set_control_mode(group_key, ControlMode.AI_CONTROL)
                    self.hmi_manager.update_target_frequency(group_key, ai_frequency)
                    st.rerun()

        # 시뮬레이션: 실제 주파수 업데이트 (실제 시스템에서는 PLC/VFD에서 읽어옴)
        # 목표 주파수와 동일하게 설정 (시뮬레이션)
        simulated_actual_freq = group.target_frequency
        if "PUMP" in group_key:
            # 펌프는 2대 운전 가정
            self.hmi_manager.update_actual_frequency(group_key, f"{group_key}_1", simulated_actual_freq)
            self.hmi_manager.update_actual_frequency(group_key, f"{group_key}_2", simulated_actual_freq)
        else:
            # 팬은 3대 운전 가정
            self.hmi_manager.update_actual_frequency(group_key, f"{group_key}_1", simulated_actual_freq)
            self.hmi_manager.update_actual_frequency(group_key, f"{group_key}_2", simulated_actual_freq)
            self.hmi_manager.update_actual_frequency(group_key, f"{group_key}_3", simulated_actual_freq)

        # 현재 상태 표시
        st.metric("목표 주파수", f"{group.target_frequency:.1f} Hz")
        st.metric("실제 평균", f"{group.get_avg_actual_frequency():.1f} Hz")

        deviation = group.get_max_deviation()
        deviation_status = self.hmi_manager.get_deviation_status(group_key)

        if deviation_status == "Green":
            st.success(f"✅ 편차: {deviation:.2f} Hz (정상)")
        elif deviation_status == "Yellow":
            st.warning(f"⚠️ 편차: {deviation:.2f} Hz (주의)")
        else:
            st.error(f"🔴 편차: {deviation:.2f} Hz (경고)")

    def _render_frequency_comparison_table(self):
        """주파수 비교 테이블"""
        # 시뮬레이션 데이터
        data = []

        for group_key, group_name in [
            ("SW_PUMPS", "SW 펌프"),
            ("FW_PUMPS", "FW 펌프"),
            ("ER_FANS", "E/R 팬")
        ]:
            group = self.hmi_manager.groups[group_key]

            # 입력 조건 (시뮬레이션)
            input_condition = "엔진 75%, T5=35.2°C, T6=43.5°C"

            # AI 계산 주파수
            ai_frequency = 48.4 if "PUMP" in group_key else 47.3

            # 목표 주파수 - group.target_frequency 사용 (HMI 매니저가 관리)
            target_freq = group.target_frequency

            # 실제 주파수 - HMI 매니저에서 읽어오기
            # (실제 시스템에서는 PLC/VFD에서 읽어온 값이 저장되어 있음)
            actual_freq = group.get_avg_actual_frequency()

            # 만약 실제 주파수가 없으면 (아직 업데이트 안 됨) 목표 주파수로 가정
            if actual_freq == 0.0:
                actual_freq = target_freq

            # 편차
            deviation = abs(target_freq - actual_freq)

            # 편차 상태
            if deviation < 0.3:
                status = "🟢 정상"
            elif deviation < 0.5:
                status = "🟡 주의"
            else:
                status = "🔴 경고"

            data.append({
                "그룹": group_name,
                "제어 모드": group.control_mode.value,
                "입력 조건": input_condition,
                "AI 계산": f"{ai_frequency:.1f} Hz",
                "목표 주파수": f"{target_freq:.1f} Hz",
                "실제 주파수": f"{actual_freq:.1f} Hz",
                "편차": f"{deviation:.2f} Hz",
                "상태": status
            })

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.caption("💡 ±0.3Hz 이내 편차는 기계적 특성으로 정상 범위입니다.")

    def _render_performance_monitoring(self):
        """성능 모니터링 렌더링"""
        st.header("📈 실시간 성능 분석")

        # 에너지 절감 비교
        st.subheader("⚡ AI 제어 vs 60Hz 고정 운전 - 에너지 절감 효과")
        self._render_energy_savings_comparison()

        st.markdown("---")

        # 운전 시간 균등화 모니터링
        st.subheader("⏱️ 운전 시간 균등화 모니터링")
        self._render_runtime_equalization()

    def _render_energy_savings_trend(self):
        """에너지 절감률 추이"""
        # 시뮬레이션 데이터 추가
        now = datetime.now()
        if len(st.session_state.energy_history['timestamps']) == 0 or \
           (now - st.session_state.energy_history['timestamps'][-1]).seconds >= 1:

            st.session_state.energy_history['sw_pumps'].append(47.5 + (len(st.session_state.energy_history['sw_pumps']) % 20) * 0.1)
            st.session_state.energy_history['fw_pumps'].append(47.5 + (len(st.session_state.energy_history['fw_pumps']) % 15) * 0.1)
            st.session_state.energy_history['er_fans'].append(51.0 + (len(st.session_state.energy_history['er_fans']) % 10) * 0.1)
            st.session_state.energy_history['timestamps'].append(now)

            # 최근 3600개만 유지 (1시간)
            if len(st.session_state.energy_history['timestamps']) > 3600:
                st.session_state.energy_history['sw_pumps'] = st.session_state.energy_history['sw_pumps'][-3600:]
                st.session_state.energy_history['fw_pumps'] = st.session_state.energy_history['fw_pumps'][-3600:]
                st.session_state.energy_history['er_fans'] = st.session_state.energy_history['er_fans'][-3600:]
                st.session_state.energy_history['timestamps'] = st.session_state.energy_history['timestamps'][-3600:]

        # 그래프 생성
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=st.session_state.energy_history['timestamps'],
            y=st.session_state.energy_history['sw_pumps'],
            name='SW 펌프',
            line=dict(color='blue', width=2)
        ))

        fig.add_trace(go.Scatter(
            x=st.session_state.energy_history['timestamps'],
            y=st.session_state.energy_history['fw_pumps'],
            name='FW 펌프',
            line=dict(color='green', width=2)
        ))

        fig.add_trace(go.Scatter(
            x=st.session_state.energy_history['timestamps'],
            y=st.session_state.energy_history['er_fans'],
            name='E/R 팬',
            line=dict(color='red', width=2)
        ))

        # 목표 절감률 라인
        fig.add_hrect(y0=46, y1=52, line_width=0, fillcolor="green", opacity=0.1,
                     annotation_text="펌프 목표 범위", annotation_position="top left")
        fig.add_hrect(y0=50, y1=58, line_width=0, fillcolor="red", opacity=0.1,
                     annotation_text="팬 목표 범위", annotation_position="bottom left")

        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=20, b=90),
            xaxis_title="시간",
            yaxis_title="절감률 (%)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.35,
                xanchor="center",
                x=0.5
            )
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_energy_savings_comparison(self):
        """60Hz vs AI 제어 에너지 절감 비교"""
        # 시뮬레이션 데이터: 실제 주파수
        sw_freq = self.hmi_manager.groups["SW_PUMPS"].target_frequency  # 예: 48.4 Hz
        fw_freq = self.hmi_manager.groups["FW_PUMPS"].target_frequency  # 예: 48.4 Hz
        er_freq = self.hmi_manager.groups["ER_FANS"].target_frequency   # 예: 47.3 Hz

        # 정격 출력 (kW)
        sw_rated = 132.0
        fw_rated = 75.0
        er_rated = 54.3

        # 운전 대수
        sw_running = 2
        fw_running = 2
        er_running = 3

        # 전력 계산 (세제곱 법칙: P ∝ (f/60)³)
        def calc_power(freq, rated_kw, running_count):
            return rated_kw * ((freq / 60.0) ** 3) * running_count

        # 60Hz 고정 운전 시 전력
        sw_60hz = calc_power(60.0, sw_rated, sw_running)
        fw_60hz = calc_power(60.0, fw_rated, fw_running)
        er_60hz = calc_power(60.0, er_rated, er_running)
        total_60hz = sw_60hz + fw_60hz + er_60hz

        # AI 제어 운전 시 전력
        sw_ai = calc_power(sw_freq, sw_rated, sw_running)
        fw_ai = calc_power(fw_freq, fw_rated, fw_running)
        er_ai = calc_power(er_freq, er_rated, er_running)
        total_ai = sw_ai + fw_ai + er_ai

        # 절감량
        sw_saved = sw_60hz - sw_ai
        fw_saved = fw_60hz - fw_ai
        er_saved = er_60hz - er_ai
        total_saved = total_60hz - total_ai

        # 절감률
        sw_ratio = (sw_saved / sw_60hz) * 100
        fw_ratio = (fw_saved / fw_60hz) * 100
        er_ratio = (er_saved / er_60hz) * 100
        total_ratio = (total_saved / total_60hz) * 100

        # 상단: 전체 절감 요약
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("💡 60Hz 고정 운전", f"{total_60hz:.1f} kW", help="모든 장비를 60Hz로 운전할 때 소비 전력")
        with col2:
            st.metric("🤖 AI 제어 운전", f"{total_ai:.1f} kW", help="AI가 최적화한 주파수로 운전할 때 소비 전력")
        with col3:
            st.metric("💰 절감 전력", f"{total_saved:.1f} kW", f"-{total_ratio:.1f}%", delta_color="inverse")
        with col4:
            st.metric("📊 절감률", f"{total_ratio:.1f}%", help="에너지 절감 비율")

        st.markdown("---")

        # 그룹별 비교 바 차트
        st.markdown("### 그룹별 상세 비교")

        # 데이터 준비
        groups = ['SW 펌프', 'FW 펌프', 'E/R 팬']
        power_60hz = [sw_60hz, fw_60hz, er_60hz]
        power_ai = [sw_ai, fw_ai, er_ai]

        fig = go.Figure()

        # 60Hz 바
        fig.add_trace(go.Bar(
            name='60Hz 고정',
            x=groups,
            y=power_60hz,
            marker_color='lightcoral',
            text=[f"{p:.1f} kW" for p in power_60hz],
            textposition='auto',
        ))

        # AI 제어 바
        fig.add_trace(go.Bar(
            name='AI 제어',
            x=groups,
            y=power_ai,
            marker_color='lightgreen',
            text=[f"{p:.1f} kW" for p in power_ai],
            textposition='auto',
        ))

        fig.update_layout(
            barmode='group',
            height=400,
            yaxis_title='소비 전력 (kW)',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=80, b=20)
        )

        st.plotly_chart(fig, use_container_width=True)

        # 하단: 상세 테이블
        st.markdown("### 📋 상세 데이터")

        comparison_data = [
            {
                "그룹": "SW 펌프",
                "운전 대수": f"{sw_running}대",
                "AI 주파수": f"{sw_freq:.1f} Hz",
                "60Hz 전력": f"{sw_60hz:.1f} kW",
                "AI 전력": f"{sw_ai:.1f} kW",
                "절감량": f"{sw_saved:.1f} kW",
                "절감률": f"{sw_ratio:.1f}%"
            },
            {
                "그룹": "FW 펌프",
                "운전 대수": f"{fw_running}대",
                "AI 주파수": f"{fw_freq:.1f} Hz",
                "60Hz 전력": f"{fw_60hz:.1f} kW",
                "AI 전력": f"{fw_ai:.1f} kW",
                "절감량": f"{fw_saved:.1f} kW",
                "절감률": f"{fw_ratio:.1f}%"
            },
            {
                "그룹": "E/R 팬",
                "운전 대수": f"{er_running}대",
                "AI 주파수": f"{er_freq:.1f} Hz",
                "60Hz 전력": f"{er_60hz:.1f} kW",
                "AI 전력": f"{er_ai:.1f} kW",
                "절감량": f"{er_saved:.1f} kW",
                "절감률": f"{er_ratio:.1f}%"
            }
        ]

        df = pd.DataFrame(comparison_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.info("💡 **계산 기준**: 전력 = 정격출력 × (주파수/60)³ × 운전대수 (세제곱 법칙 적용)")

    def _render_runtime_equalization(self):
        """운전 시간 균등화 모니터링"""
        # 시뮬레이션 데이터
        runtime_data = [
            {"장비": "SW-P1", "총 운전 시간": 1250, "금일 운전 시간": 18.5, "연속 운전 시간": 6.2, "정비 예정": "250시간 후"},
            {"장비": "SW-P2", "총 운전 시간": 1180, "금일 운전 시간": 5.5, "연속 운전 시간": 0.0, "정비 예정": "320시간 후"},
            {"장비": "SW-P3", "총 운전 시간": 1220, "금일 운전 시간": 0.0, "연속 운전 시간": 0.0, "정비 예정": "280시간 후"},
            {"장비": "FW-P1", "총 운전 시간": 1270, "금일 운전 시간": 18.5, "연속 운전 시간": 6.2, "정비 예정": "230시간 후"},
            {"장비": "FW-P2", "총 운전 시간": 1190, "금일 운전 시간": 5.5, "연속 운전 시간": 0.0, "정비 예정": "310시간 후"},
            {"장비": "FW-P3", "총 운전 시간": 1230, "금일 운전 시간": 0.0, "연속 운전 시간": 0.0, "정비 예정": "270시간 후"},
            {"장비": "ER-F1", "총 운전 시간": 1100, "금일 운전 시간": 5.2, "연속 운전 시간": 2.1, "정비 예정": "400시간 후"},
            {"장비": "ER-F2", "총 운전 시간": 1050, "금일 운전 시간": 5.3, "연속 운전 시간": 2.1, "정비 예정": "450시간 후"},
            {"장비": "ER-F3", "총 운전 시간": 1075, "금일 운전 시간": 5.1, "연속 운전 시간": 2.1, "정비 예정": "425시간 후"},
            {"장비": "ER-F4", "총 운전 시간": 1080, "금일 운전 시간": 0.0, "연속 운전 시간": 0.0, "정비 예정": "420시간 후"},
        ]

        df = pd.DataFrame(runtime_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 수동 개입 옵션
        st.markdown("---")
        st.subheader("🔧 수동 개입")

        col1, col2 = st.columns(2)

        with col1:
            selected_equipment = st.selectbox(
                "장비 선택",
                options=["SW-P1", "SW-P2", "SW-P3", "FW-P1", "FW-P2", "FW-P3",
                        "ER-F1", "ER-F2", "ER-F3", "ER-F4"]
            )

        with col2:
            action = st.selectbox(
                "동작",
                options=["강제 운전", "강제 대기", "자동 모드"]
            )

        if st.button("적용", type="primary"):
            st.success(f"✅ {selected_equipment}을(를) {action}으로 설정했습니다.")

    def _render_alarm_management(self):
        """알람 관리 렌더링"""
        st.header("🔔 알람 관리")

        # 알람 필터 스타일 (부드러운 파스텔 톤)
        st.markdown("""
            <style>
            /* Multiselect 선택된 항목 스타일 */
            .stMultiSelect span[data-baseweb="tag"] {
                background-color: #E8EAF6 !important;
                color: #3F51B5 !important;
                border: 1px solid #C5CAE9 !important;
            }

            /* X 버튼 색상 */
            .stMultiSelect span[data-baseweb="tag"] button {
                color: #5C6BC0 !important;
            }
            </style>
        """, unsafe_allow_html=True)

        # 알람 필터
        col1, col2 = st.columns([3, 1])

        with col1:
            filter_priority = st.multiselect(
                "우선순위 필터",
                options=["🔴 CRITICAL", "🟡 WARNING", "🔵 INFO"],
                default=["🔴 CRITICAL", "🟡 WARNING", "🔵 INFO"],
                format_func=lambda x: x  # 이모지 포함해서 표시
            )

        with col2:
            show_acknowledged = st.checkbox("확인된 알람 표시", value=False)

        # 알람 리스트
        alarms = self.hmi_manager.alarms

        # 필터에서 이모지 제거하여 비교
        filter_priority_clean = [f.split(" ")[1] if " " in f else f for f in filter_priority]

        # 필터 적용
        filtered_alarms = [
            alarm for alarm in alarms
            if alarm.priority.value in filter_priority_clean and
            (show_acknowledged or not alarm.acknowledged)
        ]

        if not filtered_alarms:
            st.info("📭 표시할 알람이 없습니다.")
        else:
            for idx, alarm in enumerate(filtered_alarms):
                # 알람 색상
                if alarm.priority == AlarmPriority.CRITICAL:
                    color = "🔴"
                    bg_color = "#ffcccc"
                elif alarm.priority == AlarmPriority.WARNING:
                    color = "🟡"
                    bg_color = "#fff4cc"
                else:
                    color = "🔵"
                    bg_color = "#cce5ff"

                # 알람 카드
                with st.container():
                    col1, col2, col3 = st.columns([1, 6, 2])

                    with col1:
                        st.markdown(f"<h2>{color}</h2>", unsafe_allow_html=True)

                    with col2:
                        st.markdown(f"**{alarm.equipment}** - {alarm.message}")
                        st.caption(alarm.timestamp.strftime("%Y-%m-%d %H:%M:%S"))

                    with col3:
                        if not alarm.acknowledged:
                            if st.button("확인", key=f"ack_{idx}"):
                                self.hmi_manager.acknowledge_alarm(
                                    self.hmi_manager.alarms.index(alarm)
                                )
                                st.rerun()
                        else:
                            st.success("✅ 확인됨")

                    st.markdown("---")

        # 알람 통계
        st.subheader("📊 알람 통계")
        col1, col2, col3 = st.columns(3)

        with col1:
            critical_count = len([a for a in alarms if a.priority == AlarmPriority.CRITICAL])
            st.metric("🔴 CRITICAL", critical_count)

        with col2:
            warning_count = len([a for a in alarms if a.priority == AlarmPriority.WARNING])
            st.metric("🟡 WARNING", warning_count)

        with col3:
            info_count = len([a for a in alarms if a.priority == AlarmPriority.INFO])
            st.metric("🔵 INFO", info_count)

    def _render_learning_progress(self):
        """학습 진행 렌더링"""
        st.header("📚 AI 학습 진행 상태")

        # 학습 진행 정보
        progress = self.hmi_manager.get_learning_progress()

        # 주요 지표
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "온도 예측 정확도",
                f"{progress['temperature_prediction_accuracy']:.1f}%"
            )

        with col2:
            st.metric(
                "최적화 정확도",
                f"{progress['optimization_accuracy']:.1f}%"
            )

        with col3:
            st.metric(
                "평균 에너지 절감률",
                f"{progress['average_energy_savings']:.1f}%"
            )

        with col4:
            st.metric(
                "총 학습 시간",
                f"{progress['total_learning_hours']:.1f}h"
            )

        # 마지막 학습 시간
        if progress['last_learning_time']:
            st.info(f"📅 마지막 학습: {progress['last_learning_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.warning("⚠️ 아직 학습이 수행되지 않았습니다.")

        st.markdown("---")

        # 주간 개선 추이 (시뮬레이션)
        st.subheader("📈 주간 개선 추이")

        weeks = list(range(1, 9))
        temp_accuracy = [72.0, 74.5, 76.2, 77.8, 79.1, 80.3, 81.4, 82.5]
        energy_savings = [42.0, 44.5, 46.2, 47.5, 48.5, 49.0, 49.5, 49.8]

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=weeks,
            y=temp_accuracy,
            name='온도 예측 정확도 (%)',
            line=dict(color='blue', width=3),
            marker=dict(size=8)
        ))

        fig.add_trace(go.Scatter(
            x=weeks,
            y=energy_savings,
            name='에너지 절감률 (%)',
            line=dict(color='green', width=3),
            marker=dict(size=8),
            yaxis='y2'
        ))

        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=20, b=90),
            xaxis_title="주차",
            yaxis_title="온도 예측 정확도 (%)",
            yaxis2=dict(
                title="에너지 절감률 (%)",
                overlaying='y',
                side='right'
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.35,
                xanchor="center",
                x=0.5
            )
        )

        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # AI 진화 단계
        st.subheader("🚀 AI 진화 단계")

        # 시뮬레이션: 현재 8개월 운영 (Stage 2)
        months_running = 8

        col1, col2, col3 = st.columns(3)

        with col1:
            if months_running < 6:
                st.success("✅ **Stage 1: 규칙 기반** (현재)")
                st.caption("규칙 80% + ML 20%")
            else:
                st.info("✅ Stage 1: 규칙 기반 (완료)")

        with col2:
            if 6 <= months_running < 12:
                st.success("✅ **Stage 2: 패턴 학습** (현재)")
                st.caption("규칙 70% + ML 30%")
            elif months_running >= 12:
                st.info("✅ Stage 2: 패턴 학습 (완료)")
            else:
                st.warning("⏳ Stage 2: 패턴 학습")

        with col3:
            if months_running >= 12:
                st.success("✅ **Stage 3: 적응형** (현재)")
                st.caption("규칙 60% + ML 40%")
            else:
                st.warning("⏳ Stage 3: 적응형")

        # 진행률 바
        st.markdown("---")
        st.markdown("**📊 전체 진행률**")

        progress_pct = min(100, (months_running / 12) * 100)
        st.progress(progress_pct / 100)

        # 상세 정보
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("현재 운영 기간", f"{months_running}개월")
        with col2:
            st.metric("Stage 3 완료까지", f"{max(0, 12-months_running)}개월")
        with col3:
            st.metric("진행률", f"{progress_pct:.0f}%")

        st.info("""
        💡 **AI 진화 단계 안내**
        - **Stage 1 (0-6개월)**: 규칙 기반 제어 위주, AI 학습 시작
        - **Stage 2 (6-12개월)**: 패턴 학습 단계, AI 비중 증가
        - **Stage 3 (12개월 이후)**: 완전 적응형 AI, 최적화 완성

        현재 시스템은 **{months_running}개월** 운영 중으로, **Stage 2 단계**에 있습니다.
        """.format(months_running=months_running))

    def _render_gps_environment(self):
        """GPS & 환경 정보 렌더링"""
        st.header("🗺️ GPS & 환경 정보")

        env = self.hmi_manager.get_gps_info()

        if env is None:
            st.warning("⚠️ GPS 데이터가 없습니다.")
            return

        # 상단: 주요 정보 카드
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("위도", f"{env.latitude:.4f}°")
            st.caption("Latitude")

        with col2:
            st.metric("경도", f"{env.longitude:.4f}°")
            st.caption("Longitude")

        with col3:
            st.metric("선속", f"{env.speed_knots:.1f} knots")
            st.caption(f"≈ {env.speed_knots * 1.852:.1f} km/h")

        with col4:
            # 운항 상태
            if env.navigation_state == NavigationState.NAVIGATING:
                st.metric("운항 상태", "⛴️ 운항 중")
            else:
                st.metric("운항 상태", "⚓ 정박")

        st.markdown("---")

        # 중간: 환경 분류
        st.subheader("🌍 환경 분류")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**해역**")
            if env.sea_region == SeaRegion.TROPICAL:
                st.success("🌴 열대 (Tropical)")
                st.caption("위도 ±23.5° 이내")
            elif env.sea_region == SeaRegion.TEMPERATE:
                st.info("🌊 온대 (Temperate)")
                st.caption("위도 23.5° ~ 66.5°")
            else:
                st.error("❄️ 극지 (Polar)")
                st.caption("위도 66.5° 이상")

        with col2:
            st.markdown("**계절**")
            season_emoji = {
                Season.SPRING: "🌸 봄",
                Season.SUMMER: "☀️ 여름",
                Season.AUTUMN: "🍂 가을",
                Season.WINTER: "❄️ 겨울"
            }
            st.info(season_emoji.get(env.season, "Unknown"))

        with col3:
            st.markdown("**추정 해수 온도**")
            st.metric("해수 온도", f"{env.estimated_seawater_temp:.1f}°C")
            st.caption("AI 최적화에 반영")

        st.markdown("---")

        # 환경 보정 계수
        st.subheader("⚙️ 환경 보정 계수")

        col1, col2 = st.columns([1, 2])

        with col1:
            factor_pct = (env.ambient_correction_factor - 1.0) * 100
            if factor_pct > 0:
                st.metric("보정 계수", f"+{factor_pct:.1f}%", delta=f"{factor_pct:.1f}%")
                st.caption("냉각 부하 증가")
            elif factor_pct < 0:
                st.metric("보정 계수", f"{factor_pct:.1f}%", delta=f"{factor_pct:.1f}%")
                st.caption("냉각 부하 감소")
            else:
                st.metric("보정 계수", "0.0%")
                st.caption("기준 상태")

        with col2:
            st.info(f"""
            **현재 환경 특성:**
            - 해역: {env.sea_region.value.upper()}
            - 계절: {env.season.value.upper()}
            - 추정 해수온: {env.estimated_seawater_temp:.1f}°C
            - 보정계수: {env.ambient_correction_factor:.3f}

            이 보정 계수는 AI 최적화 시 자동으로 반영됩니다.
            """)

        st.markdown("---")

        # 하단: 위치 지도 (간단한 좌표 표시)
        st.subheader("📍 현재 위치")

        # Plotly로 간단한 지도 표시
        import plotly.graph_objects as go

        fig = go.Figure(go.Scattergeo(
            lon=[env.longitude],
            lat=[env.latitude],
            text=[f"선속: {env.speed_knots:.1f} knots"],
            mode='markers+text',
            marker=dict(size=15, color='red', symbol='circle'),
            textposition='top center'
        ))

        fig.update_layout(
            title=f"위치: {env.latitude:.4f}°, {env.longitude:.4f}°",
            geo=dict(
                scope='asia',
                projection_type='natural earth',
                showland=True,
                landcolor='rgb(243, 243, 243)',
                coastlinecolor='rgb(204, 204, 204)',
                center=dict(lat=env.latitude, lon=env.longitude),
                projection_scale=3
            ),
            height=400
        )

        st.plotly_chart(fig, use_container_width=True)

        # 마지막 업데이트 시간
        if self.hmi_manager.last_gps_update:
            st.caption(f"마지막 GPS 업데이트: {self.hmi_manager.last_gps_update.strftime('%Y-%m-%d %H:%M:%S')}")

    def _render_vfd_diagnostics(self):
        """VFD 진단 정보 렌더링"""
        st.header("🔧 VFD 상태 진단")

        # 시뮬레이션: VFD 데이터 생성 (초기화 시에만)
        if 'vfd_initialized' not in st.session_state:
            self._initialize_vfd_simulation()
            st.session_state.vfd_initialized = True

        diagnostics = self.hmi_manager.get_vfd_diagnostics()

        if not diagnostics:
            st.warning("⚠️ VFD 진단 데이터가 없습니다.")
            return

        # 상단: 상태 요약
        summary = self.hmi_manager.get_vfd_summary()

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("전체 VFD", summary["total"])

        with col2:
            st.metric("🟢 정상", summary["normal"])

        with col3:
            st.metric("🟡 주의", summary["caution"])

        with col4:
            st.metric("🟠 경고", summary["warning"])

        with col5:
            st.metric("🔴 위험", summary["critical"])

        st.markdown("---")

        # VFD 그룹별 표시
        st.subheader("📊 VFD 상태 상세")

        # SW 펌프
        st.markdown("**SW 펌프 (132kW x 3대)**")
        col1, col2, col3 = st.columns(3)
        for i, col in enumerate([col1, col2, col3], 1):
            vfd_id = f"SW_PUMP_{i}"
            if vfd_id in diagnostics:
                self._render_vfd_card(col, diagnostics[vfd_id])

        st.markdown("---")

        # FW 펌프
        st.markdown("**FW 펌프 (75kW x 3대)**")
        col1, col2, col3 = st.columns(3)
        for i, col in enumerate([col1, col2, col3], 1):
            vfd_id = f"FW_PUMP_{i}"
            if vfd_id in diagnostics:
                self._render_vfd_card(col, diagnostics[vfd_id])

        st.markdown("---")

        # E/R 팬
        st.markdown("**E/R 팬 (54.3kW x 4대)**")
        col1, col2, col3, col4 = st.columns(4)
        for i, col in enumerate([col1, col2, col3, col4], 1):
            vfd_id = f"ER_FAN_{i}"
            if vfd_id in diagnostics:
                self._render_vfd_card(col, diagnostics[vfd_id])

        st.markdown("---")

        # 상세 진단 정보 (선택한 VFD)
        st.subheader("🔍 상세 진단")

        selected_vfd = st.selectbox(
            "VFD 선택",
            options=list(diagnostics.keys()),
            format_func=lambda x: x.replace("_", " ")
        )

        if selected_vfd in diagnostics:
            diag = diagnostics[selected_vfd]

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**{selected_vfd.replace('_', ' ')}**")

                # 운전 데이터
                data_col1, data_col2, data_col3, data_col4 = st.columns(4)

                with data_col1:
                    st.metric("주파수", f"{diag.current_frequency_hz:.1f} Hz")

                with data_col2:
                    st.metric("출력 전류", f"{diag.output_current_a:.1f} A")

                with data_col3:
                    st.metric("모터 온도", f"{diag.motor_temperature_c:.1f}°C")

                with data_col4:
                    st.metric("히트싱크 온도", f"{diag.heatsink_temperature_c:.1f}°C")

                st.markdown("---")

                # 이상 패턴
                if diag.anomaly_patterns:
                    st.markdown("**감지된 이상 패턴:**")
                    for pattern in diag.anomaly_patterns:
                        st.warning(f"⚠️ {pattern}")
                else:
                    st.success("✅ 이상 패턴 없음")

                st.markdown("---")

                # 권고사항
                st.info(f"**권고사항:** {diag.recommendation}")

            with col2:
                # 상태 등급
                status_color = {
                    VFDStatus.NORMAL: "🟢",
                    VFDStatus.CAUTION: "🟡",
                    VFDStatus.WARNING: "🟠",
                    VFDStatus.CRITICAL: "🔴"
                }

                st.markdown(f"### {status_color.get(diag.status_grade, '⚪')} {diag.status_grade.value.upper()}")
                st.metric("심각도 점수", f"{diag.severity_score}/100")

                st.markdown("---")

                # 통계
                st.markdown("**누적 통계:**")
                st.text(f"운전 시간: {diag.cumulative_runtime_hours:.1f}h")
                st.text(f"Trip 횟수: {diag.trip_count}")
                st.text(f"Error 횟수: {diag.error_count}")
                st.text(f"Warning 횟수: {diag.warning_count}")

                st.markdown("---")

                # StatusBits
                st.markdown("**Status Bits:**")
                bits = diag.status_bits
                st.text(f"{'✅' if bits.control_ready else '❌'} Control Ready")
                st.text(f"{'✅' if bits.drive_ready else '❌'} Drive Ready")
                st.text(f"{'✅' if bits.in_operation else '❌'} In Operation")
                st.text(f"{'❌' if bits.trip else '✅'} No Trip")
                st.text(f"{'❌' if bits.error else '✅'} No Error")
                st.text(f"{'❌' if bits.warning else '✅'} No Warning")

    def _render_vfd_card(self, col, diagnostic):
        """VFD 카드 렌더링"""
        with col:
            # 상태 색상
            if diagnostic.status_grade == VFDStatus.NORMAL:
                status_emoji = "🟢"
                status_text = "정상"
            elif diagnostic.status_grade == VFDStatus.CAUTION:
                status_emoji = "🟡"
                status_text = "주의"
            elif diagnostic.status_grade == VFDStatus.WARNING:
                status_emoji = "🟠"
                status_text = "경고"
            else:
                status_emoji = "🔴"
                status_text = "위험"

            st.markdown(f"**{diagnostic.vfd_id.replace('_', ' ')}**")
            st.markdown(f"{status_emoji} {status_text}")
            st.metric("주파수", f"{diagnostic.current_frequency_hz:.1f} Hz")
            st.metric("모터 온도", f"{diagnostic.motor_temperature_c:.1f}°C")
            st.caption(f"운전: {diagnostic.cumulative_runtime_hours:.1f}h")

    def _initialize_vfd_simulation(self):
        """VFD 시뮬레이션 데이터 초기화"""
        import random

        # 그룹별 주파수 설정 (같은 그룹은 동일한 주파수)
        group_frequencies = {
            'SW_PUMP': self.hmi_manager.groups['SW_PUMPS'].target_frequency,
            'FW_PUMP': self.hmi_manager.groups['FW_PUMPS'].target_frequency,
            'ER_FAN': self.hmi_manager.groups['ER_FANS'].target_frequency
        }

        # 10개 VFD에 대한 시뮬레이션 데이터 생성
        vfd_list = [
            *[f"SW_PUMP_{i}" for i in range(1, 4)],
            *[f"FW_PUMP_{i}" for i in range(1, 4)],
            *[f"ER_FAN_{i}" for i in range(1, 5)]
        ]

        for vfd_id in vfd_list:
            # 대부분 정상, 일부 주의/경고
            is_running = vfd_id.endswith("1") or vfd_id.endswith("2") or (vfd_id.startswith("ER") and vfd_id.endswith("3"))

            # 그룹명 추출
            group_name = '_'.join(vfd_id.split('_')[:-1])

            if is_running:
                # 그룹별 목표 주파수 사용 (±0.5Hz 오차 허용)
                freq = group_frequencies[group_name] + random.uniform(-0.5, 0.5)
                current = random.uniform(100.0, 150.0)
                motor_temp = random.uniform(55.0, 75.0)
                heatsink_temp = random.uniform(45.0, 60.0)

                # 일부 VFD에 경고 상태 부여
                has_warning = vfd_id == "SW_PUMP_2"

                status_bits = DanfossStatusBits(
                    trip=False,
                    error=False,
                    warning=has_warning,
                    voltage_exceeded=False,
                    torque_exceeded=False,
                    thermal_exceeded=False,
                    control_ready=True,
                    drive_ready=True,
                    in_operation=True,
                    speed_equals_reference=True,
                    bus_control=True
                )
            else:
                # Stand-by 상태
                freq = 0.0
                current = 0.0
                motor_temp = 35.0
                heatsink_temp = 30.0

                status_bits = DanfossStatusBits(
                    trip=False,
                    error=False,
                    warning=False,
                    voltage_exceeded=False,
                    torque_exceeded=False,
                    thermal_exceeded=False,
                    control_ready=True,
                    drive_ready=True,
                    in_operation=False,
                    speed_equals_reference=False,
                    bus_control=True
                )

            diagnostic = self.hmi_manager.vfd_monitor.diagnose_vfd(
                vfd_id=vfd_id,
                status_bits=status_bits,
                frequency_hz=freq,
                output_current_a=current,
                output_voltage_v=400.0,
                dc_bus_voltage_v=540.0,
                motor_temp_c=motor_temp,
                heatsink_temp_c=heatsink_temp,
                runtime_seconds=random.uniform(1000.0, 5000.0)
            )

            self.hmi_manager.update_vfd_diagnostic(vfd_id, diagnostic)

    def _render_scenario_testing(self):
        """시나리오 테스트 렌더링"""
        st.header("🎬 시나리오 테스트")

        st.info("""
        **시나리오 모드**에서는 다양한 운항 조건을 시뮬레이션할 수 있습니다.
        시나리오를 활성화하면 **메인 대시보드의 센서 값이 시나리오 데이터로 변경**되며,
        **Rule-based AI 시스템**이 실시간으로 어떤 규칙을 적용하는지 확인할 수 있습니다.
        """)

        # 시나리오 모드 ON/OFF
        col1, col2 = st.columns([1, 3])

        with col1:
            use_scenario = st.checkbox(
                "시나리오 모드 활성화",
                value=st.session_state.use_scenario_data,
                key="scenario_mode_toggle"
            )

            if use_scenario != st.session_state.use_scenario_data:
                st.session_state.use_scenario_data = use_scenario
                st.rerun()

        with col2:
            if st.session_state.use_scenario_data:
                st.success("✅ 시나리오 모드 활성화됨 - 메인 대시보드에서 실시간 변화를 확인하세요!")
            else:
                st.warning("⚪ 시나리오 모드 비활성화됨 - 고정 시뮬레이션 데이터 사용 중")

        st.markdown("---")

        # 시나리오 선택 버튼
        st.subheader("🎯 시나리오 선택")

        # 시나리오 속도 조절
        col_speed1, col_speed2, col_speed3 = st.columns([2, 3, 6])

        with col_speed1:
            st.markdown("**⚡ 재생 속도**")

        with col_speed2:
            speed_options = {
                "0.5배속 (느림)": 0.5,
                "1배속 (정상)": 1.0,
                "2배속": 2.0,
                "5배속": 5.0,
                "10배속 (빠름)": 10.0
            }

            # 최초 렌더링 시 기본값을 10배속으로 설정
            if "speed_selector" not in st.session_state:
                st.session_state.speed_selector = "10배속 (빠름)"
                st.session_state.speed_multiplier = 10.0
                self.scenario_engine.set_time_multiplier(10.0)

            selected_speed = st.selectbox(
                "속도 선택",
                options=list(speed_options.keys()),
                key="speed_selector",
                label_visibility="collapsed"
            )

            new_speed = speed_options[selected_speed]
            previous_speed = st.session_state.get("speed_multiplier", new_speed)
            if abs(new_speed - previous_speed) > 0.001:
                self.scenario_engine.set_time_multiplier(new_speed)
                st.session_state.speed_multiplier = new_speed
                st.rerun()  # 즉시 화면 새로고침

        with col_speed3:
            display_speed = st.session_state.get("speed_multiplier", speed_options[selected_speed])
            if display_speed > 1.0:
                st.info(f"⏩ {display_speed:.1f}배 빠른 속도로 진행 중")
            elif display_speed < 1.0:
                st.info(f"⏪ {display_speed:.1f}배 느린 속도로 진행 중")
            else:
                st.info("▶️ 정상 속도로 진행 중")

        st.markdown("---")

        # 현재 선택된 시나리오 타입
        current = st.session_state.current_scenario_type

        # 라디오 버튼으로 변경 (한 줄 표시 보장)
        scenario_options = {
            "기본 제어 검증": ScenarioType.NORMAL_OPERATION,
            "SW 펌프 제어 검증": ScenarioType.HIGH_LOAD,
            "FW 펌프 제어 검증": ScenarioType.COOLING_FAILURE,
            "압력 안전 제어 검증": ScenarioType.PRESSURE_DROP,
            "E/R 온도 제어 검증": ScenarioType.ER_VENTILATION
        }

        # 현재 선택된 옵션 찾기
        current_label = None
        for label, stype in scenario_options.items():
            if current == stype:
                current_label = label
                break

        # 세션 상태 초기화 또는 유효성 검증
        if 'selected_scenario_label' not in st.session_state or st.session_state.selected_scenario_label not in scenario_options:
            st.session_state.selected_scenario_label = current_label

        # 라디오 버튼으로 시나리오 선택
        selected_index = list(scenario_options.keys()).index(st.session_state.selected_scenario_label) if st.session_state.selected_scenario_label in scenario_options else 0

        col_radio, col_button = st.columns([4, 1])
        
        with col_radio:
            selected = st.radio(
                "시나리오를 선택하세요",
                options=list(scenario_options.keys()),
                index=selected_index,
                horizontal=True,
                label_visibility="collapsed"
            )
        
        with col_button:
            st.write("")  # 버튼 정렬을 위한 공백
            start_button = st.button("🚀 시작", type="primary", use_container_width=True)

        # 선택이 변경되면 선택만 업데이트 (시작 버튼으로 실행)
        if selected != st.session_state.selected_scenario_label:
            st.session_state.selected_scenario_label = selected
        
        # 시작 버튼 클릭 시 시나리오 시작
        if start_button:
            self.scenario_engine.start_scenario(scenario_options[selected])
            st.session_state.use_scenario_data = True
            st.session_state.current_scenario_type = scenario_options[selected]
            # 주파수 및 대수 초기화
            st.session_state.current_frequencies = {
                'sw_pump': 48.0,
                'fw_pump': 48.0,
                'er_fan': 48.0,  # 47.0 → 48.0 (일관성)
                'er_fan_count': 3,  # 2 → 3 (E/R 팬 기본 3대)
                'time_at_max_freq': 0,  # 60Hz 유지 시간 (초)
                'time_at_min_freq': 0   # 40Hz 유지 시간 (초)
            }
            # RuleBasedController 리셋
            self.integrated_controller.rule_controller.reset()
            st.rerun()

        # 선택 안내 메시지
        if current == ScenarioType.NORMAL_OPERATION:
            st.info("✅ 기본 제어 검증 시나리오 실행 중")
        elif current == ScenarioType.HIGH_LOAD:
            st.info("✅ SW 펌프 제어 검증 시나리오 실행 중")
        elif current == ScenarioType.COOLING_FAILURE:
            st.warning("⚠️ FW 펌프 제어 검증 시나리오 실행 중")
        elif current == ScenarioType.PRESSURE_DROP:
            st.warning("⚠️ 압력 안전 제어 검증 시나리오 실행 중")
        elif current == ScenarioType.ER_VENTILATION:
            st.warning("⚠️ E/R 온도 제어 검증 시나리오 실행 중")

        st.markdown("---")

        # 현재 시나리오 정보
        st.subheader("📊 현재 시나리오 상태")

        info = self.scenario_engine.get_scenario_info()

        if info:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("시나리오", info['name'])
                st.caption(info['description'])

            with col2:
                progress_pct = float(info['progress'].replace('%', ''))
                st.metric("진행률", info['progress'])
                st.progress(progress_pct / 100.0)

            with col3:
                st.metric("경과 시간", f"{info['elapsed_seconds']:.0f}초")
                remaining = info['duration_minutes'] * 60 - info['elapsed_seconds']
                st.caption(f"남은 시간: {remaining:.0f}초")

            # 완료 여부
            if info['is_complete']:
                st.success("✅ 시나리오 완료!")
                st.info("👆 상단에서 다른 시나리오를 선택하거나 '기본 제어 검증'을 선택하세요.")
        else:
            st.info("시나리오를 선택해주세요.")

        st.markdown("---")

        # 현재 센서 값 (시나리오 활성화 시)
        if st.session_state.use_scenario_data:
            st.subheader("🌡️ 현재 센서 값 & AI 판단")

            values = self.scenario_engine.get_current_values()

            # 메인 대시보드와 동일한 IntegratedController 사용
            controller = self.integrated_controller

            # 현재 주파수 및 대수 (세션 상태에 저장하여 추적)
            # 강제로 er_fan_count를 3대로 리셋 (기존 2대 세션 상태 무시)
            if 'current_frequencies' not in st.session_state:
                st.session_state.current_frequencies = {
                    'sw_pump': 48.0,
                    'fw_pump': 48.0,
                    'er_fan': 47.0,
                    'er_fan_count': 3,  # E/R 팬 작동 대수 (기본 3대)
                    'time_at_max_freq': 0,  # 60Hz 유지 시간 (초)
                    'time_at_min_freq': 0   # 40Hz 유지 시간 (초)
                }

            # 기존 세션에서 er_fan_count가 2대로 설정되어 있으면 3대로 강제 변경
            if st.session_state.current_frequencies.get('er_fan_count', 3) == 2:
                st.session_state.current_frequencies['er_fan_count'] = 3

            current_freqs = st.session_state.current_frequencies

            # AI 판단 실행
            temperatures = {
                'T1': values['T1'],
                'T2': values['T2'],
                'T3': values['T3'],
                'T4': values['T4'],
                'T5': values['T5'],
                'T6': values['T6'],
                'T7': values['T7']
            }
            
            # 온도 시퀀스 업데이트 (예측 제어용)
            controller.update_temperature_sequence(temperatures, values['engine_load'])

            # 디버깅: 입력 값 출력
            st.info(f"🔍 디버그: T6={values['T6']:.1f}°C, 현재 E/R 팬={current_freqs['er_fan']:.1f}Hz ({current_freqs.get('er_fan_count', 3)}대)")

            decision = controller.compute_control(
                temperatures=temperatures,
                pressure=values['PX1'],
                engine_load=values['engine_load'],
                current_frequencies=current_freqs
            )

            # 디버깅: 출력 값 확인
            st.info(f"🔍 AI 판단 결과: E/R 팬={decision.er_fan_freq:.1f}Hz → Reason: {decision.reason}")
            
            # 예측 제어 정보 표시
            if decision.use_predictive_control and decision.temperature_prediction:
                pred = decision.temperature_prediction
                # 디버그: 타입 확인
                try:
                    t4_val = float(pred.t4_pred_10min)
                    t5_val = float(pred.t5_pred_10min)
                    t6_val = float(pred.t6_pred_10min)
                    conf_val = float(pred.confidence * 100)
                    st.success(f"🔮 예측 제어 활성: T4={t4_val:.1f}°C, T5={t5_val:.1f}°C, T6={t6_val:.1f}°C (10분 후 예측, 신뢰도: {conf_val:.0f}%)")
                except Exception as e:
                    st.error(f"❌ 예측 값 포맷팅 오류: {e}")
                    st.write(f"Debug - T4 type: {type(pred.t4_pred_10min)}, value: {pred.t4_pred_10min}")

            # AI 판단을 현재 주파수 및 대수에 반영
            st.session_state.current_frequencies['sw_pump'] = decision.er_fan_freq
            st.session_state.current_frequencies['fw_pump'] = decision.fw_pump_freq
            st.session_state.current_frequencies['er_fan'] = decision.er_fan_freq
            st.session_state.current_frequencies['er_fan_count'] = getattr(decision, 'er_fan_count', 3)
            # 타이머는 integrated_controller가 current_freqs에 직접 업데이트했으므로 이미 반영됨
            
            # 디버깅: 타이머 상태 표시
            timer_max = current_freqs.get('time_at_max_freq', 0)
            timer_min = current_freqs.get('time_at_min_freq', 0)
            st.info(f"🕐 타이머 상태: 최대={timer_max}s, 최소={timer_min}s")

            # 시나리오별 강조 표시 플래그
            is_er_scenario = (st.session_state.current_scenario_type == ScenarioType.ER_VENTILATION)
            is_sw_scenario = (st.session_state.current_scenario_type == ScenarioType.HIGH_LOAD)
            is_fw_scenario = (st.session_state.current_scenario_type == ScenarioType.COOLING_FAILURE)
            is_pressure_scenario = (st.session_state.current_scenario_type == ScenarioType.PRESSURE_DROP)
            
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                delta_t5 = values['T5'] - 35.0
                if is_sw_scenario:
                    # SW 펌프 시나리오에서 T5 강조
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                padding: 20px; border-radius: 10px; text-align: center; 
                                box-shadow: 0 8px 16px rgba(102,126,234,0.3);'>
                        <p style='color: white; font-size: 14px; margin: 0; font-weight: 600;'>⭐ T5 (FW 출구)</p>
                        <p style='color: white; font-size: 36px; margin: 10px 0; font-weight: 700;'>{:.1f}°C</p>
                        <p style='color: {}; font-size: 16px; margin: 0; font-weight: 600;'>{:+.1f}°C</p>
                    </div>
                    """.format(values['T5'], 
                              '#ff6b6b' if delta_t5 > 0 else '#51cf66',
                              delta_t5), unsafe_allow_html=True)
                else:
                    st.metric("T5 (FW 출구)", f"{values['T5']:.1f}°C",
                             f"{delta_t5:+.1f}°C",
                             delta_color="inverse" if delta_t5 > 0 else "normal")

            with col2:
                delta_t4 = values['T4'] - 43.0  # T4 정상 범위 중심
                if is_fw_scenario:
                    # FW 펌프 시나리오에서 T4 강조
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                padding: 20px; border-radius: 10px; text-align: center; 
                                box-shadow: 0 8px 16px rgba(102,126,234,0.3);'>
                        <p style='color: white; font-size: 14px; margin: 0; font-weight: 600;'>⭐ T4 (FW 입구)</p>
                        <p style='color: white; font-size: 36px; margin: 10px 0; font-weight: 700;'>{:.1f}°C</p>
                        <p style='color: {}; font-size: 16px; margin: 0; font-weight: 600;'>{:+.1f}°C</p>
                    </div>
                    """.format(values['T4'], 
                              '#ff6b6b' if delta_t4 > 0 else '#51cf66',
                              delta_t4), unsafe_allow_html=True)
                else:
                    st.metric("T4 (FW 입구)", f"{values['T4']:.1f}°C",
                             f"{delta_t4:+.1f}°C",
                             delta_color="inverse" if delta_t4 > 0 else "normal")

            with col3:
                delta_t6 = values['T6'] - 43.0
                if is_er_scenario:
                    # E/R 시나리오에서 T6 강조
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                padding: 20px; border-radius: 10px; text-align: center; 
                                box-shadow: 0 8px 16px rgba(102,126,234,0.3);'>
                        <p style='color: white; font-size: 14px; margin: 0; font-weight: 600;'>⭐ T6 (E/R 온도)</p>
                        <p style='color: white; font-size: 36px; margin: 10px 0; font-weight: 700;'>{:.1f}°C</p>
                        <p style='color: {}; font-size: 16px; margin: 0; font-weight: 600;'>{:+.1f}°C</p>
                    </div>
                    """.format(values['T6'], 
                              '#ff6b6b' if delta_t6 > 0 else '#51cf66',
                              delta_t6), unsafe_allow_html=True)
                else:
                    st.metric("T6 (E/R 온도)", f"{values['T6']:.1f}°C",
                             f"{delta_t6:+.1f}°C",
                             delta_color="inverse" if delta_t6 > 0 else "normal")

            with col4:
                delta_px = values['PX1'] - 2.0
                if is_pressure_scenario:
                    # 압력 시나리오에서 PX1 강조
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                                padding: 20px; border-radius: 10px; text-align: center; 
                                box-shadow: 0 8px 16px rgba(240,147,251,0.3);'>
                        <p style='color: white; font-size: 14px; margin: 0; font-weight: 600;'>⭐ PX1 (압력)</p>
                        <p style='color: white; font-size: 36px; margin: 10px 0; font-weight: 700;'>{:.2f} bar</p>
                        <p style='color: {}; font-size: 16px; margin: 0; font-weight: 600;'>{:+.2f} bar</p>
                    </div>
                    """.format(values['PX1'], 
                              '#51cf66' if delta_px > 0 else '#ff6b6b',
                              delta_px), unsafe_allow_html=True)
                else:
                    st.metric("PX1 (압력)", f"{values['PX1']:.2f} bar",
                             f"{delta_px:+.2f}",
                             delta_color="inverse" if delta_px < 0 else "normal")

            with col5:
                st.metric("엔진 부하", f"{values['engine_load']:.1f}%")

            # Rule-based AI 제어 판단 표시
            st.markdown("---")
            st.markdown("### 🤖 Rule-based AI 제어 판단")
            
            # 제어 상태 표시 (시나리오별)
            if is_sw_scenario:
                ml_used = hasattr(decision, 'ml_prediction_used') and decision.ml_prediction_used
                if ml_used:
                    st.success("🤖 **제어 방식**: ML 온도 예측 (T5 선제 대응) + Rule R1 강화 보정 (60Hz/40Hz 가속) - 핵심 에너지 절감 기능!")
                else:
                    st.warning("📐 **제어 방식**: Rule 기반 제어 (ML 데이터 축적 중...)")
            elif is_fw_scenario:
                ml_used = hasattr(decision, 'ml_prediction_used') and decision.ml_prediction_used
                if ml_used:
                    st.success("🤖 **제어 방식**: ML 온도 예측 + Rule R2 3단계 제어 (극한 에너지 절감) - T4<48°C일 때 최대한 40Hz 운전!")
                else:
                    st.warning("📐 **제어 방식**: Rule 기반 제어 (ML 데이터 축적 중...)")
            elif is_pressure_scenario:
                if decision.control_mode == "pressure_constraint":
                    st.error("⛔ **제어 방식**: Safety Layer S3 압력 보호 - PX1 < 1.0 bar → SW 펌프 감속 차단!")
                else:
                    st.info("📊 **제어 방식**: 압력 모니터링 중 (PX1 ≥ 1.0 bar → 정상)")
            
            # 적용된 규칙 표시
            if hasattr(decision, 'applied_rules') and decision.applied_rules:
                with st.expander("📋 적용된 규칙 보기", expanded=False):
                    for rule in decision.applied_rules:
                        if rule.startswith('S'):  # Safety rules
                            st.error(f"🚨 {rule}")
                        elif rule.startswith('R'):  # Optimization rules
                            st.info(f"⚙️ {rule}")
                        elif rule == 'ML_PREDICTION':
                            st.success(f"🤖 {rule}: ML 모델 예측 사용 (선제적 주파수 조정)")
                        else:
                            st.text(f"• {rule}")

            # 제어 모드에 따른 알림 표시
            if decision.emergency_action:
                st.error(f"🚨 긴급 제어 발동: {decision.reason}")
            elif decision.control_mode == "pressure_constraint":
                st.warning(f"⚠️ 압력 제약 활성: {decision.reason}")
            elif values['T5'] > 37.0 or values['T6'] > 45.0:
                st.warning(f"⚠️ 온도 상승 감지: {decision.reason}")
            else:
                st.success(f"✅ 정상 제어: {decision.reason}")

            # AI 판단 결과 (목표 주파수)
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                freq_change = decision.sw_pump_freq - current_freqs['sw_pump']
                if is_sw_scenario or is_pressure_scenario:
                    # SW 펌프 시나리오 또는 압력 시나리오에서 주파수 강조
                    change_color = '#ff6b6b' if freq_change > 0 else ('#51cf66' if freq_change < 0 else '#ffd93d')
                    gradient_bg = 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)' if is_sw_scenario else 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'
                    text_color = '#333' if is_sw_scenario else 'white'
                    change_text_color = change_color if is_sw_scenario else 'white'
                    st.markdown(f"""
                    <div style='background: {gradient_bg}; 
                                padding: 20px; border-radius: 10px; text-align: center; 
                                box-shadow: 0 8px 16px rgba(250,112,154,0.3);'>
                        <p style='color: {text_color}; font-size: 14px; margin: 0; font-weight: 600;'>⭐ SW 펌프 목표</p>
                        <p style='color: {text_color}; font-size: 36px; margin: 10px 0; font-weight: 700;'>{decision.sw_pump_freq:.1f} Hz</p>
                        <p style='color: {change_text_color}; font-size: 16px; margin: 0; font-weight: 600;'>{freq_change:+.1f} Hz</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # 압력 제약이 활성화된 경우 특별 표시
                    if decision.control_mode == "pressure_constraint":
                        st.metric("SW 펌프 목표", f"{decision.sw_pump_freq:.1f} Hz",
                                 "⛔ 감소 제한", delta_color="off")
                    elif decision.sw_pump_freq >= 60.0 and decision.emergency_action:
                        st.metric("SW 펌프 목표", f"{decision.sw_pump_freq:.1f} Hz",
                                 "🚨 최대!", delta_color="inverse")
                    elif abs(freq_change) >= 0.1:
                        st.metric("SW 펌프 목표", f"{decision.sw_pump_freq:.1f} Hz", f"{freq_change:+.1f} Hz")
                    else:
                        st.metric("SW 펌프 목표", f"{decision.sw_pump_freq:.1f} Hz")

            with col2:
                freq_change = decision.fw_pump_freq - current_freqs['fw_pump']
                if is_fw_scenario:
                    # FW 펌프 시나리오에서 주파수 강조
                    change_color = '#ff6b6b' if freq_change > 0 else ('#51cf66' if freq_change < 0 else '#ffd93d')
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); 
                                padding: 20px; border-radius: 10px; text-align: center; 
                                box-shadow: 0 8px 16px rgba(250,112,154,0.3);'>
                        <p style='color: #333; font-size: 14px; margin: 0; font-weight: 600;'>⭐ FW 펌프 목표</p>
                        <p style='color: #333; font-size: 36px; margin: 10px 0; font-weight: 700;'>{:.1f} Hz</p>
                        <p style='color: {}; font-size: 16px; margin: 0; font-weight: 600;'>{:+.1f} Hz</p>
                    </div>
                    """.format(decision.fw_pump_freq, change_color, freq_change), unsafe_allow_html=True)
                else:
                    if decision.fw_pump_freq >= 60.0 and decision.emergency_action:
                        st.metric("FW 펌프 목표", f"{decision.fw_pump_freq:.1f} Hz",
                                 "🚨 최대!", delta_color="inverse")
                    elif abs(freq_change) >= 0.1:
                        st.metric("FW 펌프 목표", f"{decision.fw_pump_freq:.1f} Hz", f"{freq_change:+.1f} Hz")
                    else:
                        st.metric("FW 펌프 목표", f"{decision.fw_pump_freq:.1f} Hz")

            with col3:
                freq_change = decision.er_fan_freq - current_freqs['er_fan']
                fan_count = getattr(decision, 'er_fan_count', 2)
                
                if is_er_scenario:
                    # E/R 시나리오에서 팬 목표 강조
                    change_color = '#ff6b6b' if freq_change > 0 else ('#51cf66' if freq_change < 0 else '#ffd93d')
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); 
                                padding: 20px; border-radius: 10px; text-align: center; 
                                box-shadow: 0 8px 16px rgba(250,112,154,0.3);'>
                        <p style='color: #333; font-size: 14px; margin: 0; font-weight: 600;'>⭐ E/R 팬 목표</p>
                        <p style='color: #333; font-size: 36px; margin: 10px 0; font-weight: 700;'>{:.1f} Hz</p>
                        <p style='color: #333; font-size: 20px; margin: 5px 0; font-weight: 600;'>({:}대)</p>
                        <p style='color: {}; font-size: 16px; margin: 0; font-weight: 600;'>{:+.1f} Hz</p>
                    </div>
                    """.format(decision.er_fan_freq, fan_count, change_color, freq_change), unsafe_allow_html=True)
                else:
                    if abs(freq_change) >= 0.1:
                        st.metric("E/R 팬 목표", f"{decision.er_fan_freq:.1f} Hz ({fan_count}대)", f"{freq_change:+.1f} Hz")
                    else:
                        st.metric("E/R 팬 목표", f"{decision.er_fan_freq:.1f} Hz ({fan_count}대)")

            with col4:
                st.metric("제어 모드", decision.control_mode)

            # 압력 제약 특별 표시
            if values['PX1'] < 1.0:
                st.error("⛔ **압력 제약 조건 활성**: PX1 < 1.0 bar → SW 펌프 주파수 감소 제한")
                st.info(f"현재 압력: {values['PX1']:.2f} bar → AI가 SW 펌프 주파수를 {decision.sw_pump_freq:.1f} Hz로 유지 (감소 불가)")

            # 대수 변경 메시지
            if hasattr(decision, 'count_change_reason') and decision.count_change_reason:
                st.info(f"🔄 **대수 제어**: {decision.count_change_reason}")

            # 추가 센서
            st.markdown("### 추가 센서")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("T1 (SW 입구)", f"{values['T1']:.1f}°C")
            with col2:
                st.metric("T2 (SW 출구 1)", f"{values['T2']:.1f}°C")
            with col3:
                st.metric("T3 (SW 출구 2)", f"{values['T3']:.1f}°C")
            with col4:
                st.metric("T7 (외기)", f"{values['T7']:.1f}°C")

        st.markdown("---")

        # 시나리오 설명
        st.subheader("📖 시나리오 설명")

        scenario_descriptions = {
            "기본 제어 검증": {
                "조건": "열대 해역, 75% 엔진 부하",
                "예상 온도": "T5=33°C, T6=43°C (정상 범위)",
                "예상 압력": "PX1=2.0 bar (정상)",
                "AI 대응": "현재 상태 유지, 효율 최적화"
            },
            "고부하 제어 검증": {
                "조건": "고속 항해, 95% 엔진 부하",
                "예상 온도": "T5=35°C, T6=46°C (점진적 상승)",
                "예상 압력": "PX1=2.0 bar",
                "AI 대응": "펌프/팬 증속으로 냉각 강화"
            },
            "냉각기 과열 보호 검증": {
                "조건": "냉각 성능 저하",
                "예상 온도": "T5=40°C, T6=52°C (급격한 상승)",
                "예상 압력": "PX1=2.0 bar",
                "AI 대응": "최대 냉각, 알람 발생"
            },
            "압력 안전 제어 검증": {
                "조건": "SW 펌프 압력 저하 (2분간 2.0→0.7bar)",
                "예상 온도": "T5=33°C (낮음, 정상이면 감속 가능)",
                "예상 압력": "PX1: 2.0 → 1.5 (1분) → 0.7 (2분)",
                "AI 대응": "1.0bar 통과 후 주파수 감소 금지 (안전 제약)"
            },
            "E/R 온도 제어 검증": {
                "조건": "기관실 환기 불량 (T6만 상승)",
                "예상 온도": "T6: 43°C → 48°C (7분간 점진적 상승), 기타 온도 정상",
                "예상 압력": "PX1=2.0 bar (정상)",
                "AI 대응": "E/R 팬 주파수/대수 증가로 기관실 냉각"
            }
        }

        for scenario_name, desc in scenario_descriptions.items():
            with st.expander(f"📌 {scenario_name}"):
                st.write(f"**조건**: {desc['조건']}")
                st.write(f"**예상 온도**: {desc['예상 온도']}")
                st.write(f"**예상 압력**: {desc['예상 압력']}")
                st.write(f"**AI 대응**: {desc['AI 대응']}")


def main():
    """메인 함수"""
    dashboard = Dashboard()
    dashboard.run()


if __name__ == "__main__":
    main()
