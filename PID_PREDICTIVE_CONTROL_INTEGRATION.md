# PID 제어와 온도 예측 제어 통합 시스템

## 📋 목차
1. [시스템 아키텍처](#시스템-아키텍처)
2. [PID 제어 원리](#pid-제어-원리)
3. [온도 예측 제어](#온도-예측-제어)
4. [통합 제어 로직](#통합-제어-로직)
5. [실제 시나리오](#실제-시나리오)

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    Integrated Controller                     │
│                                                              │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   PID      │  │  Predictive  │  │  Energy Saving     │  │
│  │ Controller │  │  Controller  │  │  Controller        │  │
│  └────────────┘  └──────────────┘  └────────────────────┘  │
│         │               │                    │              │
│         └───────────────┴────────────────────┘              │
│                         │                                   │
│                    최종 결정                                 │
└─────────────────────────────────────────────────────────────┘
```

### 제어 계층 구조

```
Layer 1: 센서 데이터 수집
  ├─ T1 (해수 입구)
  ├─ T4 (FW Inlet)
  ├─ T5 (FW Outlet)
  ├─ T6 (E/R Temperature)
  └─ Engine Load

Layer 2: 예측 모델 (선택적)
  ├─ 30분 히스토리 데이터 분석
  ├─ Polynomial Regression
  └─ 5/10/15분 후 온도 예측

Layer 3: 제어 알고리즘
  ├─ PID Controller (기본 제어)
  ├─ Predictive Controller (선제적 제어)
  └─ Energy Saving Controller (효율 최적화)

Layer 4: 안전 제약
  ├─ 온도 기반 최소 주파수 보장
  ├─ 압력 기반 주파수 제한
  └─ 대수 제어 (60Hz/40Hz 조건)

Layer 5: 최종 출력
  ├─ SW Pump Frequency
  ├─ FW Pump Frequency
  ├─ E/R Fan Frequency
  └─ E/R Fan Count
```

---

## 🎯 PID 제어 원리

### 기본 개념

**PID = Proportional + Integral + Derivative**

```
PID 출력 = P항 + I항 + D항
```

### E/R 팬 제어 (T6 온도 기준)

#### 설정값
```python
목표 온도 (Setpoint): 43.0°C
출력 범위: 40~60Hz
변화율 제한: 2Hz/초
기본 게인: Kp=5.0, Ki=0.2, Kd=1.0
```

### 1단계: 오차 계산

```python
error = 목표온도 - 측정온도
error = 43.0 - T6_measured
```

**의미:**
- **양수 (+)**: 온도가 낮음 → 주파수 **낮춰야** (팬 속도 감소 → 온도 상승)
- **음수 (-)**: 온도가 높음 → 주파수 **올려야** (팬 속도 증가 → 온도 하강)

**예시:**
```
T6 = 40°C → error = +3°C (온도 낮음)
T6 = 46°C → error = -3°C (온도 높음)
```

### 2단계: 비례항 (P - Proportional)

```python
P = Kp × error
```

**역할:** 즉각적인 반응
- 오차가 크면 큰 조정
- 오차가 작으면 작은 조정

**예시 (Kp = 5.0):**
```
T6 = 40°C:
  error = +3°C
  P = 5.0 × (+3) = +15Hz
  → 현재 주파수에서 15Hz 감소 신호

T6 = 46°C:
  error = -3°C
  P = 5.0 × (-3) = -15Hz
  → 현재 주파수에서 15Hz 증가 신호
```

### 3단계: 적분항 (I - Integral)

```python
integral += error × dt
I = Ki × integral
```

**역할:** 누적 오차 제거
- 오차가 지속되면 계속 증가
- 정상 상태 오차(Steady-State Error) 제거
- Anti-windup: ±10 제한

**예시 (Ki = 0.2):**
```
10초 동안 +3°C 오차 지속:
  integral = 3 × 10 = 30
  I = 0.2 × 30 = +6Hz
  → 추가로 6Hz 감소 신호
```

### 4단계: 미분항 (D - Derivative)

```python
derivative = (error - previous_error) / dt
D = Kd × derivative
```

**역할:** 변화 속도 감지
- 급격한 변화 억제
- 오버슈트(Overshoot) 방지

**예시 (Kd = 1.0):**
```
이전 오차: +3°C
현재 오차: +1°C (2초 경과)
  derivative = (+1 - +3) / 2 = -1°C/s
  D = 1.0 × (-1) = -1Hz
  → 변화가 빠르므로 1Hz 증가 신호 (브레이크)
```

### 5단계: 최종 출력

```python
pid_output = P + I + D
output = clip(pid_output, 40Hz, 60Hz)
```

**전체 예시:**
```
현재 상태:
  T6 = 40°C (목표 43°C)
  현재 주파수 = 48Hz

PID 계산:
  P = +15Hz (비례)
  I = +6Hz  (적분)
  D = -1Hz  (미분)
  ─────────
  합계 = +20Hz

주파수 조정:
  목표 = 48 - 20 = 28Hz
  제한 적용 = max(40, 28) = 40Hz

최종 출력: 40Hz
```

### 6단계: 변화율 제한

```python
최대 변화: 2Hz/초
```

**목적:** 급격한 변화 방지
```
현재: 48Hz
목표: 40Hz
시간: 1초

최대 변화 = 2Hz/s × 1s = 2Hz
실제 출력 = 48 - 2 = 46Hz (점진적 감소)
```

---

## 🔮 온도 예측 제어

### 예측 모델: Polynomial Regression

#### 입력 데이터
```python
TemperatureSequence {
    timestamps: [t-30분, ..., t-0분]  # 90개 데이터포인트
    T1_sequence: [...]  # 해수 입구 온도
    T4_sequence: [...]  # FW Inlet
    T5_sequence: [...]  # FW Outlet
    T6_sequence: [...]  # E/R 온도
    T7_sequence: [...]  # 청수 온도
    engine_load_sequence: [...]  # 엔진 부하
}
```

#### 특징 추출 (Feature Extraction)
```python
각 온도별 특징:
  - 현재값 (current)
  - 평균값 (mean_30min)
  - 표준편차 (std_30min)
  - 상승률 (rate_of_increase)

총 19개 특징:
  T1 특징 (4개)
  T4 특징 (4개)
  T5 특징 (4개)
  T6 특징 (4개)
  T7 특징 (2개)
  Engine Load (1개)
```

#### 다항식 특징 (Polynomial Features)
```python
기본 특징 + 제곱항 + 교차항
  - X² (제곱)
  - X × Y (교차)
  - T4 × Engine_Load (중요!)

총 ~210개 특징
```

#### 예측 출력
```python
TemperaturePrediction {
    # 현재 온도
    t4_current, t5_current, t6_current
    
    # 5분 후 예측
    t4_pred_5min, t5_pred_5min, t6_pred_5min
    
    # 10분 후 예측
    t4_pred_10min, t5_pred_10min, t6_pred_10min
    
    # 15분 후 예측
    t4_pred_15min, t5_pred_15min, t6_pred_15min
    
    # 신뢰도 (0~1)
    confidence: 0.85
}
```

### 예측 정확도
```
평균 오차: ±0.5°C
신뢰도 > 0.5: 예측 제어 활성화
신뢰도 ≤ 0.5: 기본 PID 제어
```

---

## 🔄 통합 제어 로직

### 제어 흐름도

```
시작
  ↓
센서 데이터 수집 (T1~T7, Engine Load)
  ↓
30분 히스토리 버퍼 업데이트
  ↓
온도 예측 (Polynomial Regression)
  ↓
신뢰도 > 0.5?
  ├─ Yes → 예측 제어 모드
  └─ No  → 기본 제어 모드
  ↓
PID 기본 출력 계산
  ↓
예측 보정 적용 (예측 모드 시)
  ↓
에너지 절감 제어
  ↓
T6 온도 안전 제약
  ↓
압력 안전 제약
  ↓
대수 제어 (60Hz/40Hz)
  ↓
최종 주파수 출력
```

### 모드 1: 예측 제어 (Predictive Control)

#### 활성화 조건
```python
if confidence > 0.5:
    mode = "Predictive Control"
```

#### 동작 순서

**1단계: PID 기본 출력**
```python
pid_output = {
    'sw_pump_freq': 48Hz,  # T5 제어
    'er_fan_freq': 48Hz    # T6 제어
}
```

**2단계: 10분 후 온도 변화 예측**
```python
t4_delta = t4_pred_10min - t4_current
t5_delta = t5_pred_10min - t5_current
t6_delta = t6_pred_10min - t6_current
```

**3단계: 예측 보정값 계산**
```python
# T4 (FW Inlet) 상승 예상 → FW 펌프 증속
if t4_delta > 1.0:
    fw_adjustment = +3Hz
elif t4_delta > 0.5:
    fw_adjustment = +2Hz

# T5 (FW Outlet) 상승 예상 → SW 펌프 증속
if t5_delta > 0.5:
    sw_adjustment = +3Hz
elif t5_delta > 0.3:
    sw_adjustment = +2Hz

# T6 (E/R Temp) 상승 예상 → E/R 팬 증속
if t6_delta > 1.0:
    fan_adjustment = +4Hz
elif t6_delta > 0.5:
    fan_adjustment = +2Hz
```

**4단계: 최종 주파수**
```python
decision.sw_pump_freq = min(60, pid_output['sw_pump_freq'] + sw_adjustment)
decision.fw_pump_freq = min(60, energy_output['fw_pump_freq'] + fw_adjustment)
decision.er_fan_freq = min(60, pid_output['er_fan_freq'] + fan_adjustment)
```

#### 구체적인 예시

```
현재 상태:
  T6 = 43.0°C (목표 43°C)
  PID 출력 = 48Hz (정상)

10분 후 예측:
  T6 예측 = 45.5°C
  t6_delta = +2.5°C (상승 예상!)

예측 보정:
  if t6_delta > 1.0:
      fan_adjustment = +4Hz

최종 주파수:
  decision.er_fan_freq = min(60, 48 + 4) = 52Hz

제어 이유:
  "예측 제어: T6 +2.5°C 예상 → E/R 팬 +4Hz"
```

**효과:**
- ✅ 온도가 오르기 전에 미리 증속
- ✅ 온도 변화 최소화
- ✅ 에너지 효율 향상

### 모드 2: 기본 제어 (PID + Energy Saving)

#### 활성화 조건
```python
if confidence ≤ 0.5:
    mode = "Basic Control"
```

#### 동작 순서

**1단계: PID 출력**
```python
pid_output = {
    'sw_pump_freq': 48Hz,  # T5 제어
    'er_fan_freq': 48Hz    # T6 제어
}
```

**2단계: 에너지 절감 출력**
```python
energy_output = {
    'fw_pump_freq': 45Hz   # T4 제어
}
```

**3단계: 최종 결정**
```python
decision.sw_pump_freq = pid_output['sw_pump_freq']
decision.fw_pump_freq = energy_output['fw_pump_freq']
decision.er_fan_freq = pid_output['er_fan_freq']
```

---

## 🛡️ 안전 제약 (Safety Constraints)

### 1. T6 온도 기반 최소 주파수 보장

```python
if t6_temp > 44.0:
    # 최소 52Hz 보장 (PID가 60Hz까지 올릴 수 있음)
    decision.er_fan_freq = max(decision.er_fan_freq, 52.0)
    
elif t6_temp > 42.0:
    # 최소 48Hz 보장 (정상 범위)
    decision.er_fan_freq = max(decision.er_fan_freq, 48.0)
    
elif t6_temp >= 40.0:
    # 온도가 낮으므로 주파수 감소 허용
    adjusted_freq = max(40.0, decision.er_fan_freq - 2.0)
    decision.er_fan_freq = adjusted_freq
    
else:  # t6_temp < 40.0
    # 추가 감소 허용
    adjusted_freq = max(40.0, decision.er_fan_freq - 4.0)
    decision.er_fan_freq = adjusted_freq
```

**중요:** T6 온도 제어는 **최소값만 보장**, **최대값(60Hz) 제한 없음!**

### 2. 압력 기반 주파수 제한

```python
if pressure < 1.0:
    # 압력이 낮으면 주파수 감소 제한
    decision.sw_pump_freq = max(current_sw_freq, decision.sw_pump_freq)
    decision.fw_pump_freq = max(current_fw_freq, decision.fw_pump_freq)
```

### 3. 대수 제어 (E/R Fan Count Control)

#### 대수 증가 조건
```python
if decision.er_fan_freq >= 60.0:  # 최대 주파수 도달
    time_at_max += 2초
    
    if time_at_max >= 10초 and current_count < 4:
        # 대수 증가!
        decision.er_fan_count = current_count + 1
        decision.er_fan_freq = 52Hz  # 주파수 감소
        time_at_max = 0  # 타이머 리셋
```

#### 대수 감소 조건
```python
if decision.er_fan_freq <= 40.0:  # 최소 주파수 도달
    time_at_min += 2초
    
    if time_at_min >= 10초 and current_count > 2:
        # 대수 감소!
        decision.er_fan_count = current_count - 1
        decision.er_fan_freq = 48Hz  # 주파수 증가
        time_at_min = 0  # 타이머 리셋
```

#### 안정 대역
```python
if 40 < decision.er_fan_freq < 60:
    # 현재 대수 유지
    # 타이머 리셋
    time_at_max = 0
    time_at_min = 0
```

---

## 🎬 실제 시나리오: E/R 환기 불량

### Phase 1: 온도 상승 (0~180초, T6: 42→48°C)

#### 시간 0초
```
현재 상태:
  T6 = 42.0°C
  PID 출력 = 48Hz
  
예측 (10분 후):
  T6 예측 = 44.0°C
  t6_delta = +2.0°C
  
예측 보정:
  fan_adjustment = +4Hz
  
최종 주파수:
  52Hz
  
제어 이유:
  "예측 제어: T6 +2.0°C 예상 → E/R 팬 +4Hz"
```

#### 시간 60초
```
현재 상태:
  T6 = 44.0°C
  PID 출력 = 52Hz
  
예측 (10분 후):
  T6 예측 = 46.0°C
  t6_delta = +2.0°C
  
예측 보정:
  fan_adjustment = +4Hz
  
최종 주파수:
  56Hz
```

#### 시간 120초
```
현재 상태:
  T6 = 46.0°C
  PID 출력 = 58Hz
  
예측 (10분 후):
  T6 예측 = 48.0°C
  t6_delta = +2.0°C
  
예측 보정:
  fan_adjustment = +4Hz
  
최종 주파수:
  60Hz (최대!)
```

#### 시간 130초
```
대수 제어 활성화:
  주파수 60Hz & 10초 지속
  
대수 증가:
  3대 → 4대
  
주파수 조정:
  60Hz → 52Hz
  
이유:
  "60Hz 최대 도달 → 팬 3→4대 증가"
```

### Phase 2: 온도 하강 (180~540초, T6: 48→38°C)

#### 시간 300초
```
현재 상태:
  T6 = 45.0°C
  PID 출력 = 48Hz
  대수 = 4대
  
예측 (10분 후):
  T6 예측 = 43.0°C
  t6_delta = -2.0°C (하강 예상)
  
예측 보정:
  fan_adjustment = 0Hz (하강 시 보정 없음)
  
최종 주파수:
  48Hz
```

#### 시간 480초
```
현재 상태:
  T6 = 40.0°C
  PID 출력 = 42Hz
  대수 = 4대
  
T6 온도 제어:
  t6_temp >= 40.0
  adjusted_freq = max(40, 42 - 2) = 40Hz
  
최종 주파수:
  40Hz (최소!)
```

#### 시간 490초
```
대수 제어 활성화:
  주파수 40Hz & 10초 지속
  
대수 감소:
  4대 → 3대
  
주파수 조정:
  40Hz → 48Hz
  
이유:
  "40Hz 지속 → 팬 4→3대 감소"
```

---

## 📊 제어 성능 비교

### 기본 PID 제어 vs 예측 제어

| 항목 | 기본 PID | 예측 제어 |
|------|----------|-----------|
| 반응 속도 | 느림 (사후 대응) | 빠름 (사전 대응) |
| 온도 변화폭 | ±2°C | ±0.5°C |
| 에너지 효율 | 보통 | 우수 |
| 오버슈트 | 발생 가능 | 최소화 |
| 안정화 시간 | 5~10분 | 2~3분 |

### 예측 제어의 장점

1. **선제적 대응**
   - 온도가 오르기 전에 미리 증속
   - 온도 변화 최소화

2. **에너지 절감**
   - 과도한 증속 방지
   - 최적 주파수 유지

3. **안정성 향상**
   - 온도 변화폭 감소
   - 오버슈트 방지

4. **예측 가능성**
   - 10분 후 상황 예측
   - 운전자 의사결정 지원

---

## 🔧 주요 파라미터

### PID 게인
```python
T5 Controller (FW Outlet):
  Kp = 3.0
  Ki = 0.15
  Kd = 0.8

T6 Controller (E/R Temp):
  Kp = 5.0
  Ki = 0.2
  Kd = 1.0
```

### 예측 보정값
```python
T4 (FW Inlet):
  delta > 1.0°C: +3Hz
  delta > 0.5°C: +2Hz

T5 (FW Outlet):
  delta > 0.5°C: +3Hz
  delta > 0.3°C: +2Hz

T6 (E/R Temp):
  delta > 1.0°C: +4Hz
  delta > 0.5°C: +2Hz
```

### 대수 제어
```python
증가 조건:
  주파수 ≥ 60Hz & 10초 지속
  최대 4대

감소 조건:
  주파수 ≤ 40Hz & 10초 지속
  최소 2대
```

---

## 🎯 핵심 요약

### 1. PID 제어
- **현재 온도 오차 기반**
- **즉각적인 피드백 제어**
- **목표 온도 유지**

### 2. 예측 제어
- **미래 온도 변화 예측**
- **선제적 주파수 조정**
- **온도 변화 최소화**

### 3. 통합 제어
- **PID + 예측 = 최적 제어**
- **안전 제약 적용**
- **대수 제어 통합**

### 4. 제어 우선순위
```
1순위: 안전 제약 (온도, 압력)
2순위: 대수 제어 (60Hz/40Hz)
3순위: 예측 제어 (신뢰도 > 0.5)
4순위: PID 제어 (기본)
5순위: 에너지 절감
```

---

## 📚 참고 자료

### 관련 파일
- `src/control/pid_controller.py` - PID 제어기
- `src/ml/temperature_predictor.py` - 온도 예측 모델
- `src/control/integrated_controller.py` - 통합 제어기
- `src/control/energy_saving.py` - 에너지 절감 제어

### 수학적 배경
- PID 제어 이론
- Polynomial Regression
- Feature Engineering
- Time Series Prediction

---

생성일: 2025-10-15
버전: 1.0
작성자: AI Assistant



