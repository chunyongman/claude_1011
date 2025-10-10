"""
Streamlit 기반 HMI 대시보드
실시간 모니터링 및 제어 인터페이스
"""

import streamlit as st
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


class Dashboard:
    """Streamlit 대시보드"""

    def __init__(self):
        """초기화"""
        # Session state 초기화
        if 'hmi_manager' not in st.session_state:
            st.session_state.hmi_manager = HMIStateManager()

        if 'sensor_history' not in st.session_state:
            st.session_state.sensor_history = {
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

        self.hmi_manager: HMIStateManager = st.session_state.hmi_manager

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
            </style>
        """, unsafe_allow_html=True)

        # 제목
        st.title("⚡ ESS AI 제어 시스템 - HMI Dashboard")
        st.caption("HMM 16K급 선박 - NVIDIA Jetson Xavier NX 기반 에너지 절감 시스템")

        # 사이드바
        self._render_sidebar()


        # 탭 생성
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📊 메인 대시보드",
            "🎛️ 제어 패널",
            "📈 성능 모니터링",
            "🔔 알람 관리",
            "📚 학습 진행",
            "🗺️ GPS & 환경",
            "🔧 VFD 진단"
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

        # 자동 새로고침 (1초) - 진행률 업데이트를 위해 필수
        # 주의: st.rerun() 호출 시 탭이 메인 대시보드로 초기화됨
        time.sleep(1)
        st.rerun()

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
        active_alarms = self.hmi_manager.get_active_alarms()
        critical_alarms = [a for a in active_alarms if a.priority == AlarmPriority.CRITICAL]
        warning_alarms = [a for a in active_alarms if a.priority == AlarmPriority.WARNING]

        st.sidebar.metric("🔴 CRITICAL 알람", len(critical_alarms))
        st.sidebar.metric("🟡 WARNING 알람", len(warning_alarms))
        st.sidebar.metric("🔵 INFO 알람", len(active_alarms) - len(critical_alarms) - len(warning_alarms))

    def _render_main_dashboard(self):
        """메인 대시보드 렌더링"""
        st.header("📊 실시간 시스템 모니터링")

        # 4개 컬럼으로 주요 센서 표시
        col1, col2, col3, col4 = st.columns(4)

        # 시뮬레이션 데이터 (실제로는 data_collector에서 가져옴)
        T5 = 35.2
        T6 = 43.5
        PX1 = 2.8
        engine_load = 75

        with col1:
            st.metric("T5 (FW 출구)", f"{T5:.1f}°C", f"{T5-35:.1f}°C")
        with col2:
            st.metric("T6 (E/R 온도)", f"{T6:.1f}°C", f"{T6-43:.1f}°C")
        with col3:
            st.metric("PX1 (압력)", f"{PX1:.1f} bar", "정상")
        with col4:
            st.metric("엔진 부하", f"{engine_load}%", "")

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
        # 시뮬레이션 데이터 추가
        now = datetime.now()
        if len(st.session_state.sensor_history['timestamps']) == 0 or \
           (now - st.session_state.sensor_history['timestamps'][-1]).seconds >= 1:

            st.session_state.sensor_history['T5'].append(35.0 + (len(st.session_state.sensor_history['T5']) % 10) * 0.1)
            st.session_state.sensor_history['T6'].append(43.0 + (len(st.session_state.sensor_history['T6']) % 10) * 0.1)
            st.session_state.sensor_history['timestamps'].append(now)

            # 최근 600개만 유지 (10분)
            if len(st.session_state.sensor_history['timestamps']) > 600:
                st.session_state.sensor_history['T5'] = st.session_state.sensor_history['T5'][-600:]
                st.session_state.sensor_history['T6'] = st.session_state.sensor_history['T6'][-600:]
                st.session_state.sensor_history['timestamps'] = st.session_state.sensor_history['timestamps'][-600:]

        # 그래프 생성
        fig = go.Figure()

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
                     annotation_text="T5 목표 (35°C)")
        fig.add_hline(y=43.0, line_dash="dash", line_color="red",
                     annotation_text="T6 목표 (43°C)")

        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis_title="시간",
            yaxis_title="온도 (°C)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_energy_savings_gauge(self):
        """에너지 절감률 게이지"""
        # 시뮬레이션 데이터
        sw_savings = 47.5
        fw_savings = 47.5
        fan_savings = 51.0

        avg_savings = (sw_savings + fw_savings + fan_savings) / 3

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
            st.markdown("**E/R 팬 (54.3kW x 4대)**")
            for i in range(1, 5):
                status = "🟢 운전 중" if i <= 3 else "⚪ 대기"
                freq = er_freq if i <= 3 else 0
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

        # 에너지 절감 추이
        st.subheader("⚡ 에너지 절감률 추이 (최근 1시간)")
        self._render_energy_savings_trend()

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
            margin=dict(l=20, r=20, t=50, b=20),
            xaxis_title="시간",
            yaxis_title="절감률 (%)",
            legend=dict(
                orientation="h",
                yanchor="top",
                y=1.15,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255, 255, 255, 0.8)"
            )
        )

        st.plotly_chart(fig, use_container_width=True)

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
        energy_savings = [42.0, 44.5, 46.2, 47.5, 48.8, 49.5, 49.8, 50.1]

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
            xaxis_title="주차",
            yaxis_title="온도 예측 정확도 (%)",
            yaxis2=dict(
                title="에너지 절감률 (%)",
                overlaying='y',
                side='right'
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
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


def main():
    """메인 함수"""
    dashboard = Dashboard()
    dashboard.run()


if __name__ == "__main__":
    main()
