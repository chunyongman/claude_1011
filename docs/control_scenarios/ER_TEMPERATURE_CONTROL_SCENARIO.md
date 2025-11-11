# E/R 온도 제어 검증 시나리오

## 🎯 시나리오 목적

E/R(Engine Room) 공간의 T6 온도가 다양한 범위에서 변화할 때, E/R 환기팬의 주파수와 대수가 Rule-based AI 제어 로직에 따라 적절히 반응하는지 검증합니다.

---

## 📋 검증 대상

### 1. 온도별 주파수 제어
- **긴급 고온 (T6 > 45°C)**: 60Hz 강제 증속
- **고온 (44-45°C)**: 60Hz 유지
- **정상 (42-44°C)**: 48Hz로 수렴
- **저온 (40-42°C)**: 40Hz로 점진 감속
- **극저온 (T6 < 40°C)**: 40Hz 강제 유지

### 2. 대수 제어
- **60Hz 10초 유지**: 3대 → 4대 증가
- **40Hz 10초 유지**: 4대 → 3대 감소
- **대수 변경 후**: 30초 쿨다운 (안정화 기간)

### 3. 안전 메커니즘
- Safety Layer S5 우선순위 검증
- ML 예측 간섭 차단 확인
- 히스테리시스 (떨림 방지) 작동 확인

---

## 🔧 구현 파일 구조

```
src/
├── control/
│   ├── integrated_controller.py   # E/R 팬 대수 제어 로직
│   └── rule_based_controller.py   # Rule S5: T6 온도 제어
├── simulation/
│   └── scenarios.py                # E/R 시나리오 온도 프로파일
└── hmi/
    └── dashboard.py                # 시나리오 실행 & 시각화
```

---

## 📝 구현 상세

### 1단계: 온도 프로파일 설계 (`scenarios.py`)

#### 설계 원칙
```python
def _er_ventilation_temperature(self, t: float) -> Dict[str, float]:
    """
    E/R 온도 제어 검증 시나리오 (15분, 900초)
    
    목적: T6 온도 변화 시 E/R 팬 주파수/대수 제어 검증
    """
```

#### 타임라인 구성 (900초, 15분)

```
Phase 1 (0-120초): 정상 온도 구간 (42°C 고정)
    ├─ 초기 상태: 48Hz, 3대
    ├─ 목표: 정상 구간에서 48Hz 수렴 확인
    └─ 예상 결과: 48Hz 안정 유지

Phase 2 (120-240초): 온도 상승 (42°C → 46°C)
    ├─ 상승률: 4°C/120초 = 0.033°C/sec
    ├─ 목표: 44°C 넘으면 60Hz, 45°C 넘으면 대수 증가
    └─ 예상 결과:
        * 120-180초: 42-44°C → 48Hz 유지
        * 180-210초: 44-45°C → 60Hz 증속
        * 210-240초: 45-46°C → 60Hz 10초 유지 → 4대 증가

Phase 3 (240-360초): 고온 유지 (46°C)
    ├─ 목표: 4대 60Hz 냉각 효과 확인
    └─ 예상 결과: 60Hz 4대 안정 운전

Phase 4 (360-480초): 온도 하강 (46°C → 42°C)
    ├─ 하강률: -4°C/120초
    ├─ 목표: 정상 범위 복귀 시 48Hz 수렴
    └─ 예상 결과:
        * 360-390초: 46-45°C → 60Hz 유지
        * 390-420초: 45-44°C → 60Hz 유지
        * 420-480초: 44-42°C → 점진 감속 (60→48Hz)

Phase 5 (480-600초): 정상 복귀 (42°C)
    ├─ 목표: 48Hz 안정화
    └─ 예상 결과: 48Hz 4대 유지

Phase 6 (600-720초): 저온 구간 (42°C → 38°C)
    ├─ 하강률: -4°C/120초
    ├─ 목표: 40Hz까지 감속 → 대수 감소
    └─ 예상 결과:
        * 600-660초: 42-40°C → 점진 감속 (48→40Hz)
        * 660-720초: 40-38°C → 40Hz 10초 유지 → 3대 감소

Phase 7 (720-840초): 저온 유지 (38°C)
    ├─ 목표: 3대 40Hz 에너지 절감 확인
    └─ 예상 결과: 40Hz 3대 안정 운전

Phase 8 (840-900초): 정상 복귀 (38°C → 42°C)
    ├─ 상승률: +4°C/60초
    ├─ 목표: 정상 범위 진입 시 48Hz 수렴
    └─ 예상 결과: 점진 증속 (40→48Hz)

시나리오 종료 (900초 초과):
    └─ T6 = 42.0°C 고정 (정상 온도 유지)
```

#### 실제 코드 구현

```python
def _er_ventilation_temperature(self, t: float) -> Dict[str, float]:
    """E/R 온도 제어 검증 - T6 온도 프로파일"""
    
    # 노이즈 추가 (센서 현실성)
    noise = np.random.normal(0, 0.2)
    
    # Phase 1: 정상 온도 (0-120초)
    if t < 120:
        t6_temp = 42.0
    
    # Phase 2: 온도 상승 (120-240초)
    elif 120 <= t < 240:
        t6_temp = 42.0 + ((t - 120) / 120.0) * 4.0  # 42 → 46°C
    
    # Phase 3: 고온 유지 (240-360초)
    elif 240 <= t < 360:
        t6_temp = 46.0
    
    # Phase 4: 온도 하강 (360-480초)
    elif 360 <= t < 480:
        t6_temp = 46.0 - ((t - 360) / 120.0) * 4.0  # 46 → 42°C
    
    # Phase 5: 정상 복귀 (480-600초)
    elif 480 <= t < 600:
        t6_temp = 42.0
    
    # Phase 6: 저온 구간 (600-720초)
    elif 600 <= t < 720:
        t6_temp = 42.0 - ((t - 600) / 120.0) * 4.0  # 42 → 38°C
    
    # Phase 7: 저온 유지 (720-840초)
    elif 720 <= t < 840:
        t6_temp = 38.0
    
    # Phase 8: 정상 복귀 (840-900초)
    elif 840 <= t < 900:
        t6_temp = 38.0 + ((t - 840) / 60.0) * 4.0   # 38 → 42°C
    
    # 시나리오 종료 후
    else:
        t6_temp = 42.0
    
    return {
        'T1': 25.0 + noise,  # 해수 입구 (온대 - Rule R5 영향 제거)
        'T2': 42.0 + noise,  # SW 출구 1 (정상)
        'T3': 43.0 + noise,  # SW 출구 2 (정상)
        'T4': 44.0 + noise,  # FW 입구 (정상)
        'T5': 35.0 + noise,  # FW 출구 (정상)
        'T6': t6_temp + noise,  # E/R 온도 (시나리오 주인공!)
        'T7': 32.0 + noise   # 외기 (정상)
    }
```

#### 핵심 설계 포인트

1. **간섭 제거**
   - `T1 = 25°C` (온대 해역) → Rule R5 (해수 온도 보정) 영향 제거
   - `engine_load = 50%` → Rule R4 (엔진 부하 보정) 영향 제거
   - **오직 T6 온도만 변화** → Rule S5만 작동하도록 격리

2. **현실성 확보**
   - 노이즈 추가 (`±0.2°C`) → 실제 센서 특성 반영
   - 점진적 온도 변화 → 급격한 점프 없음

3. **검증 완전성**
   - 모든 온도 구간 커버 (38-46°C)
   - 대수 증가/감소 모두 테스트
   - 쿨다운 메커니즘 검증

---

### 2단계: Rule S5 제어 로직 (`rule_based_controller.py`)

#### Safety Layer 구조

```python
def compute_control(
    self,
    temperatures: Dict[str, float],
    pressures: Dict[str, float],
    engine_load: float,
    seawater_temp: float,
    current_frequencies: Dict[str, float],
    ml_prediction: Optional[Dict] = None
) -> RuleDecision:
    """Rule 기반 제어 계산"""
    
    # T6 온도 추출
    t6_temp = temperatures.get('T6', 43.0)
    
    # 기본값: ML 예측 또는 이전값
    if ml_prediction:
        er_freq = ml_prediction.get('er_fan_freq', self.prev_er_freq)
    else:
        er_freq = self.prev_er_freq
    
    # ===== Safety Layer: Rule S5 (T6 온도 제어) =====
    safety_override = False
    applied_rules = []
    reason_parts = []
```

#### Rule S5: 6단계 온도 제어

##### 1️⃣ 긴급 고온 (T6 > 45°C)

```python
# Rule S5_T6_EMERGENCY_HIGH
if t6_temp > 45.0:
    er_freq = self.freq_max  # 60Hz 강제!
    safety_override = True   # ML 무시!
    applied_rules.append("S5_T6_EMERGENCY_HIGH")
    reason_parts.append(
        f"[EMERGENCY] T6={t6_temp:.1f}°C > 45°C → 강제 60Hz"
    )
    
    # 상태 업데이트 (다음 사이클용)
    self.prev_er_freq = er_freq
    
    # 즉시 반환 (하위 Layer 무시!)
    return RuleDecision(
        sw_pump_freq=sw_freq,
        fw_pump_freq=fw_freq,
        er_fan_freq=er_freq,
        active_rules=applied_rules,
        reason="; ".join(reason_parts),
        safety_override=True
    )
```

**핵심:**
- `safety_override = True` → ML 완전 차단
- 즉시 `return` → Fine-tuning Layer 도달 안 함
- 최우선 안전 보장!

---

##### 2️⃣ 고온 (44-45°C)

```python
# Rule S5_T6_HIGH
elif 44.0 < t6_temp <= 45.0:
    er_freq = self.freq_max  # 60Hz 유지
    safety_override = True
    applied_rules.append("S5_T6_HIGH")
    reason_parts.append(
        f"[HIGH] T6={t6_temp:.1f}°C (44-45°C) → 60Hz 유지"
    )
    
    self.prev_er_freq = er_freq
    return RuleDecision(...)
```

**핵심:**
- 45°C 진입 전 예방적 최대 냉각
- 대수 증가 준비 구간

---

##### 3️⃣ 정상 고온부 (42-44°C) - 48Hz 수렴

```python
# Rule S5_T6_NORMAL_CONVERGE
elif 42.0 <= t6_temp <= 44.0:
    target_freq = 48.0
    
    # 48Hz로 수렴 중
    if abs(self.prev_er_freq - target_freq) > 0.5:
        if self.prev_er_freq > target_freq:
            er_freq = max(target_freq, self.prev_er_freq - 2.0)
            applied_rules.append("S5_T6_NORMAL_DECREASE")
            reason_parts.append(
                f"[정상] T6={t6_temp:.1f}°C → 48Hz 수렴 중 ({er_freq:.0f}Hz)"
            )
        else:
            er_freq = min(target_freq, self.prev_er_freq + 2.0)
            applied_rules.append("S5_T6_NORMAL_INCREASE")
            reason_parts.append(
                f"[정상] T6={t6_temp:.1f}°C → 48Hz 수렴 중 ({er_freq:.0f}Hz)"
            )
        safety_override = True
    
    # 48Hz 도달 → ML 허용!
    else:
        er_freq = target_freq
        applied_rules.append("S5_T6_NORMAL_HOLD")
        reason_parts.append(
            f"[정상] T6={t6_temp:.1f}°C → 48Hz 안정 (ML 가능)"
        )
        safety_override = False  # ML 미세 조정 허용
    
    self.prev_er_freq = er_freq
    
    if safety_override:
        return RuleDecision(...)  # 수렴 중이면 즉시 반환
    # safety_override=False면 계속 진행 (Fine-tuning Layer)
```

**핵심:**
- 정상 범위에서는 48Hz로 수렴
- 수렴 완료 후에만 `safety_override = False` → ML 허용
- ML이 미세 조정 가능 (±2Hz 정도)

---

##### 4️⃣ 저온 (40-42°C) - 40Hz로 감속

```python
# Rule S5_T6_LOW
elif 40.0 <= t6_temp < 42.0:
    target_freq = self.freq_min  # 40Hz
    
    # 40Hz로 점진 감속 중
    if self.prev_er_freq > target_freq + 0.5:
        er_freq = max(target_freq, self.prev_er_freq - 2.0)
        safety_override = True  # 감속 중에는 ML 차단
        applied_rules.append("S5_T6_LOW_DECREASE")
        reason_parts.append(
            f"[저온] T6={t6_temp:.1f}°C (40-42°C) → 40Hz 감속 ({er_freq:.0f}Hz)"
        )
    
    # 40Hz 도달 → 대수 제어 허용!
    else:
        er_freq = target_freq
        safety_override = False  # 대수 제어 로직 실행 허용!
        applied_rules.append("S5_T6_LOW_HOLD")
        reason_parts.append(
            f"[저온] T6={t6_temp:.1f}°C → 40Hz 도달 (대수 감소 대기)"
        )
    
    # 상태 업데이트 (safety_override와 무관하게 항상 업데이트!)
    self.prev_er_freq = er_freq
    
    if safety_override:
        return RuleDecision(...)  # 감속 중이면 즉시 반환
    # safety_override=False면 계속 → integrated_controller의 대수 제어
```

**핵심:**
- 40Hz 도달 전: `safety_override = True` (ML 차단)
- 40Hz 도달 후: `safety_override = False` (대수 제어 허용)
- **대수 감소 조건 충족**을 위해 필수!

---

##### 5️⃣ 극저온 (T6 < 40°C)

```python
# Rule S5_T6_VERY_LOW
elif t6_temp < 40.0:
    target_freq = self.freq_min  # 40Hz
    
    if self.prev_er_freq > target_freq + 0.5:
        er_freq = max(target_freq, self.prev_er_freq - 2.0)
        safety_override = True
        applied_rules.append("S5_T6_VERY_LOW_DECREASE")
        reason_parts.append(
            f"[극저온] T6={t6_temp:.1f}°C < 40°C → 40Hz 감속 ({er_freq:.0f}Hz)"
        )
    else:
        er_freq = target_freq
        safety_override = False  # 대수 제어 허용
        applied_rules.append("S5_T6_VERY_LOW_HOLD")
        reason_parts.append(
            f"[극저온] T6={t6_temp:.1f}°C → 40Hz 유지 (대수 감소 대기)"
        )
    
    self.prev_er_freq = er_freq
    
    if safety_override:
        return RuleDecision(...)
```

---

### 3단계: 대수 제어 로직 (`integrated_controller.py`)

#### 대수 제어가 실행되는 조건

```python
# integrated_controller.py: compute_control()

# Rule 기반 제어 실행
decision = self.rule_controller.compute_control(...)

# safety_override=True면 여기서 대수 제어 SKIP!
# safety_override=False일 때만 대수 제어 실행
```

#### 대수 증가 로직 (60Hz → 4대)

```python
# 현재 대수
current_count = current_frequencies.get('er_fan_count', 3)

# 시간 추적
time_at_max = current_frequencies.get('time_at_max_freq', 0)  # 60Hz 유지 시간
count_change_cooldown = current_frequencies.get('count_change_cooldown', 0)  # 쿨다운

# 쿨다운 감소 (2초/cycle)
if count_change_cooldown > 0:
    current_frequencies['count_change_cooldown'] = count_change_cooldown - 2

# 대수 증가 조건: 60Hz & 10초 유지 & 쿨다운 종료
if decision.er_fan_freq >= 60.0 and count_change_cooldown <= 0:
    
    # 10초 이상 유지 & 현재 4대 미만
    if time_at_max >= 10 and current_count < 4:
        decision.er_fan_count = current_count + 1  # 3 → 4대
        decision.count_change_reason = (
            f"60Hz 최대 도달 (T6={t6:.1f}°C) → "
            f"팬 {current_count}->{current_count + 1}대 증가"
        )
        
        # 타이머 & 쿨다운 리셋
        current_frequencies['time_at_max_freq'] = 0
        current_frequencies['count_change_cooldown'] = 30  # 30초 쿨다운!
        
        # 대수 증가 후 주파수 감소 (Rule S5가 다시 제어)
        decision.er_fan_freq = max(50.0, decision.er_fan_freq - 8.0)
    
    # 아직 10초 미만 → 타이머 증가
    else:
        decision.er_fan_count = current_count
        new_time = time_at_max + 2  # 2초 증가
        current_frequencies['time_at_max_freq'] = new_time
        
        if current_count >= 4:
            decision.count_change_reason = f"[최대] {current_count}대 운전 중 (Max 4대)"
        else:
            decision.count_change_reason = (
                f"[증가 대기] {decision.er_fan_freq:.1f}Hz 지속, "
                f"Timer={new_time}s/10s"
            )
```

**핵심:**
- **10초 카운트**: `time_at_max >= 10`
- **최대 4대 제한**: `current_count < 4`
- **30초 쿨다운**: 대수 변경 후 안정화 기간
- **주파수 감소**: 대수 증가 후 -8Hz (Rule S5가 다시 제어)

---

#### 대수 감소 로직 (40Hz → 3대)

```python
# 대수 감소 조건: 40Hz & 10초 유지 & 쿨다운 종료
elif decision.er_fan_freq <= 40.0 and count_change_cooldown <= 0:
    
    if time_at_min >= 10 and current_count > 2:
        decision.er_fan_count = current_count - 1  # 4 → 3대
        decision.count_change_reason = (
            f"40Hz 지속 (T6={t6:.1f}°C) → "
            f"팬 {current_count}->{current_count - 1}대 감소"
        )
        
        current_frequencies['time_at_min_freq'] = 0
        current_frequencies['count_change_cooldown'] = 30  # 30초 쿨다운
        
        # 주파수는 40Hz 유지 (Rule S5가 온도에 따라 조정)
    
    else:
        decision.er_fan_count = current_count
        new_time = time_at_min + 2
        current_frequencies['time_at_min_freq'] = new_time
        
        if current_count <= 2:
            decision.count_change_reason = f"[최소] {current_count}대 운전 중 (Min 2대)"
        else:
            decision.count_change_reason = (
                f"[감소 대기] {decision.er_fan_freq:.1f}Hz 지속, "
                f"Timer={new_time}s/10s"
            )

# 중간 대역 (40-60Hz) 또는 쿨다운 중
else:
    decision.er_fan_count = current_count
    current_frequencies['time_at_max_freq'] = 0
    current_frequencies['time_at_min_freq'] = 0
    
    if count_change_cooldown > 0:
        decision.count_change_reason = (
            f"[안정화] {decision.er_fan_freq:.1f}Hz, T6={t6:.1f}°C, "
            f"{current_count}대 (쿨다운 {count_change_cooldown}초)"
        )
    else:
        decision.count_change_reason = (
            f"[안정] {decision.er_fan_freq:.1f}Hz, T6={t6:.1f}°C, "
            f"{current_count}대 운전"
        )
```

**핵심:**
- **최소 2대 유지**: `current_count > 2`
- **쿨다운 중 변경 불가**: 떨림 방지
- **주파수는 40Hz 유지**: Rule S5가 온도에 따라 재조정

---

### 4단계: 대시보드 시각화 (`dashboard.py`)

#### 시나리오 선택 & 실행

```python
# 시나리오 옵션
scenario_options = {
    "기본 제어 검증": ScenarioType.NORMAL_OPERATION,
    "SW 펌프 제어 검증": ScenarioType.HIGH_LOAD,
    "FW 펌프 제어 검증": ScenarioType.COOLING_FAILURE,
    "압력 안전 제어 검증": ScenarioType.PRESSURE_DROP,
    "E/R 온도 제어 검증": ScenarioType.ER_VENTILATION  # 이것!
}

# 라디오 버튼
selected_label = st.radio(
    "🎮 시나리오 선택",
    options=list(scenario_options.keys()),
    index=selected_index
)

# 시작 버튼
if st.button("🚀 시작", key="start_scenario"):
    # 시나리오 엔진 초기화
    st.session_state.scenario_engine = ScenarioEngine()
    st.session_state.scenario_engine.start_scenario(
        scenario_type=selected_scenario,
        speed_multiplier=speed_multiplier
    )
    
    # Controller 상태 리셋!
    st.session_state.integrated_controller.rule_controller.reset()
    
    # 초기 주파수 설정
    st.session_state.current_frequencies = {
        'sw_pump': 48.0,
        'fw_pump': 48.0,
        'er_fan': 48.0,      # 48Hz 시작
        'er_fan_count': 3,   # 3대 시작
        'time_at_max_freq': 0,
        'time_at_min_freq': 0,
        'count_change_cooldown': 0
    }
```

---

#### T6 & E/R 팬 시각화 강조

```python
# E/R 온도 제어 검증 시나리오인지 확인
is_er_scenario = (
    st.session_state.use_scenario_data and 
    st.session_state.scenario_engine and
    st.session_state.scenario_engine.current_scenario == ScenarioType.ER_VENTILATION
)

# 시각화 강조 CSS
if is_er_scenario:
    st.markdown(f"""
        <div style='
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
            margin: 10px 0;
        '>
            <div style='font-size: 48px; margin-bottom: 10px;'>🌡️</div>
            <div style='color: white; font-size: 18px; font-weight: bold;'>
                E/R 온도 (T6)
            </div>
            <div style='color: white; font-size: 56px; font-weight: bold; 
                        margin: 15px 0; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);'>
                {current_temp:.1f}°C
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
        <div style='
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 8px 32px rgba(240, 147, 251, 0.4);
            margin: 10px 0;
        '>
            <div style='font-size: 48px; margin-bottom: 10px;'>💨</div>
            <div style='color: white; font-size: 18px; font-weight: bold;'>
                E/R 팬 목표 주파수
            </div>
            <div style='color: white; font-size: 56px; font-weight: bold; 
                        margin: 15px 0; text-shadow: 2px 2px 4px rgba(0,0,0,0,0.3);'>
                {decision.er_fan_freq:.1f} Hz
            </div>
            <div style='color: white; font-size: 24px;'>
                {decision.er_fan_count}대 운전
            </div>
        </div>
    """, unsafe_allow_html=True)
```

---

#### 제어 로직 표시

```python
# 적용된 규칙 표시
with st.expander("📋 적용된 규칙 보기", expanded=False):
    if decision.active_rules:
        st.write("**활성 규칙:**")
        for rule in decision.active_rules:
            if "S5_T6" in rule:  # T6 관련 규칙 강조
                st.success(f"✅ {rule}")
            else:
                st.info(f"• {rule}")
    
    st.write("**제어 근거:**")
    st.write(decision.reason)
    
    # 대수 제어 상태
    st.write("**대수 제어:**")
    st.write(decision.count_change_reason)

# 제어 모드 표시
if decision.safety_override:
    st.error("🛡️ **제어 방식**: Safety Layer 강제 제어 (Rule S5)")
else:
    st.success("🤖 **제어 방식**: Rule-based AI (ML 협업 가능)")
```

---

## 📊 실제 시나리오 실행 결과

### 예상 시나리오 진행

```
시간 (초) | T6 (°C) | 주파수 (Hz) | 대수 | 적용 규칙 | 상태
----------|---------|-------------|------|----------|------
0         | 42.0    | 48.0        | 3    | S5_NORMAL_HOLD | 정상 안정
60        | 42.0    | 48.0        | 3    | S5_NORMAL_HOLD | 정상 유지
120       | 42.0    | 48.0        | 3    | S5_NORMAL_HOLD | Phase 2 시작
150       | 43.0    | 48.0        | 3    | S5_NORMAL_HOLD | 정상 범위
180       | 44.0    | 48.0        | 3    | S5_NORMAL_HOLD | 정상 상한
185       | 44.2    | 60.0        | 3    | S5_T6_HIGH | 60Hz 증속!
200       | 44.7    | 60.0        | 3    | S5_T6_HIGH | 60Hz 유지
210       | 45.0    | 60.0        | 3    | S5_T6_HIGH | 대기 중 (8s)
220       | 45.3    | 60.0        | 4    | S5_T6_EMERGENCY | 4대 증가! ⬆️
240       | 46.0    | 52.0        | 4    | S5_T6_EMERGENCY | 주파수 감소
300       | 46.0    | 60.0        | 4    | S5_T6_EMERGENCY | 60Hz 재증속
360       | 46.0    | 60.0        | 4    | S5_T6_EMERGENCY | Phase 4 시작
390       | 45.0    | 60.0        | 4    | S5_T6_HIGH | 하강 중
420       | 44.0    | 58.0        | 4    | S5_NORMAL_DECREASE | 감속 시작
450       | 43.0    | 52.0        | 4    | S5_NORMAL_DECREASE | 점진 감속
480       | 42.0    | 48.0        | 4    | S5_NORMAL_HOLD | 48Hz 도달
600       | 42.0    | 48.0        | 4    | S5_NORMAL_HOLD | Phase 6 시작
630       | 41.3    | 46.0        | 4    | S5_T6_LOW_DECREASE | 감속 중
660       | 40.7    | 42.0        | 4    | S5_T6_LOW_DECREASE | 계속 감속
690       | 40.0    | 40.0        | 4    | S5_T6_LOW_HOLD | 40Hz 도달
700       | 39.3    | 40.0        | 4    | S5_VERY_LOW_HOLD | 대기 중 (8s)
710       | 38.7    | 40.0        | 3    | S5_VERY_LOW_HOLD | 3대 감소! ⬇️
720       | 38.0    | 40.0        | 3    | S5_VERY_LOW_HOLD | 안정화
840       | 38.0    | 40.0        | 3    | S5_VERY_LOW_HOLD | Phase 8 시작
870       | 40.0    | 44.0        | 3    | S5_NORMAL_INCREASE | 증속 시작
900       | 42.0    | 48.0        | 3    | S5_NORMAL_HOLD | 정상 복귀 ✅
```

---

## ✅ 검증 체크리스트

### 주파수 제어 검증
- [ ] T6 > 45°C: 60Hz 강제 증속 확인
- [ ] 44-45°C: 60Hz 유지 확인
- [ ] 42-44°C: 48Hz 수렴 확인
- [ ] 40-42°C: 40Hz로 점진 감속 확인
- [ ] T6 < 40°C: 40Hz 강제 유지 확인

### 대수 제어 검증
- [ ] 60Hz 10초 유지 → 3대에서 4대 증가 확인
- [ ] 40Hz 10초 유지 → 4대에서 3대 감소 확인
- [ ] 대수 변경 후 30초 쿨다운 작동 확인
- [ ] 최대 4대, 최소 2대 제한 확인

### 안전 메커니즘 검증
- [ ] Safety Layer S5 최우선 작동 확인
- [ ] `safety_override=True` 시 ML 차단 확인
- [ ] 쿨다운 중 대수 변경 불가 확인
- [ ] 떨림 현상 없음 확인

### 실선 적용 검증
- [ ] 시나리오용 모듈 = 실선용 모듈 확인
- [ ] Rule 로직 변경 없음 확인
- [ ] 데이터만 임시 변경 확인

---

## 🚨 주의사항

### 1. 절대 금지 사항
```
❌ 시나리오 구현을 위해 기본 제어 로직 변경
❌ IntegratedController 로직 수정
❌ RuleBasedController Rule S5 로직 변경
```

**이유:** 시나리오용 모듈 = 실선용 모듈이므로, 로직 변경은 실선에 직접 영향!

---

### 2. 허용되는 수정
```
✅ scenarios.py의 온도 프로파일 수정
✅ dashboard.py의 시각화 CSS 수정
✅ 재생 속도 조정
✅ 시나리오 설명 텍스트 수정
```

**이유:** 이것들은 테스트용 데이터/UI일 뿐, 제어 로직과 무관!

---

### 3. Controller 상태 리셋 필수
```python
# 시나리오 시작 시 반드시!
st.session_state.integrated_controller.rule_controller.reset()
```

**이유:** `prev_er_freq` 등 내부 상태가 이전 시나리오 영향을 받지 않도록!

---

## 📚 관련 문서

- [ML_SAFETY_MECHANISM.md](ML_SAFETY_MECHANISM.md) - ML 예측 제어 안전 메커니즘
- [INTEGRATION_COMPLETE_SUMMARY.md](INTEGRATION_COMPLETE_SUMMARY.md) - 전체 시스템 통합 요약
- [PID_PREDICTIVE_CONTROL_INTEGRATION.md](PID_PREDICTIVE_CONTROL_INTEGRATION.md) - Rule 기반 제어 설명

---

## 🎯 결론

E/R 온도 제어 검증 시나리오는 다음을 완벽히 검증합니다:

1. ✅ **Safety Layer S5의 최우선 작동**
2. ✅ **온도별 6단계 주파수 제어**
3. ✅ **대수 증가/감소 로직 (10초 타이머, 30초 쿨다운)**
4. ✅ **ML 간섭 차단 메커니즘**
5. ✅ **실선 적용 시 동일한 로직 보장**

이 시나리오를 통해 **Rule-based AI 제어 시스템의 안정성과 효율성**을 명확히 확인할 수 있습니다! 🚀


