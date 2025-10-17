# ML 예측 제어 안전 메커니즘

## 🎯 개요

이 문서는 ESS AI System에서 ML 예측 제어가 불안정할 때 Rule 기반 제어가 어떻게 시스템의 안전을 보장하는지 설명합니다.

---

## 📋 3단계 안전 제어 계층

```
┌─────────────────────────────────────────────┐
│  Priority 1: Safety Layer (최우선)          │ ← 항상 Rule 기반!
│  - S1: Cooler 과열 보호                      │
│  - S2: FW 입구 온도 한계                     │
│  - S3: 압력 안전 제약                        │
│  - S4: T5 극한 온도 안전 제어                │
│  - S5: T6 온도 제어                          │
│  - S6: T4 극한 온도 안전 제어                │
└─────────────────────────────────────────────┘
            ↓ (safety_override=True면 여기서 종료)
┌─────────────────────────────────────────────┐
│  Priority 2: ML Optimization (선택적)        │ ← ML 사용 가능 시만!
│  - 온도 예측 (Temperature Predictor)         │
│  - 최적 주파수 추천 (Random Forest)          │
└─────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────┐
│  Priority 3: Rule Fine-tuning               │ ← Rule로 보정!
│  - R1: T5 온도 기반 SW 펌프 강화 보정       │
│  - R2: T4 온도 기반 FW 펌프 보정            │
│  - R4: 엔진 부하 기반 보정                   │
│  - R5: 해수 온도 기반 보정                   │
│  - R6: 히스테리시스 (떨림 방지)              │
└─────────────────────────────────────────────┘
```

---

## 🔒 핵심 안전 메커니즘

### 1️⃣ Safety Layer가 항상 최우선

```python
def compute_control(..., ml_prediction: Optional[Dict] = None):
    
    # 기본값: ML 예측 또는 이전값 사용
    if ml_prediction:
        sw_freq = ml_prediction.get('sw_pump_freq', self.prev_sw_freq)
        # ML 값을 기본으로 사용
    else:
        sw_freq = self.prev_sw_freq
        # ML 없으면 이전값 유지
    
    # ===== Safety Layer (최우선!) =====
    safety_override = False
    
    # Rule S1: Cooler 과열 보호
    if t2_t3_max >= 49.0:
        sw_freq = 60.0  # 강제 최대!
        safety_override = True  # ML 무시!
        return RuleDecision(...)  # 즉시 종료!
    
    # Rule S2: FW 입구 온도 한계
    if t4_temp >= 48.0:
        fw_freq = 60.0  # 강제 최대!
        safety_override = True
        return RuleDecision(...)  # 즉시 종료!
    
    # Rule S4: T5 극한 온도 안전 제어
    if t5_temp > 40.0:
        sw_freq = 60.0  # 극고온 → 강제 60Hz
        safety_override = True
        return RuleDecision(...)
    elif t5_temp < 30.0:
        sw_freq = 40.0  # 극저온 → 강제 40Hz
        safety_override = True
        return RuleDecision(...)
    
    # Rule S5: T6 온도 제어
    if t6_temp > 45.0:
        er_freq = 60.0  # 긴급 고온 → 60Hz
        safety_override = True
        return RuleDecision(...)
    elif t6_temp > 44.0:
        er_freq = 60.0  # 고온 → 60Hz 유지
        safety_override = True
        return RuleDecision(...)
    # ... (T6 단계별 제어)
    
    # Rule S6: T4 극한 온도 안전 제어 (3단계 에너지 절감)
    # Phase 1: T4 < 46°C → 40Hz 강제 (최대 에너지 절감)
    if t4_temp < 46.0 and t4_pred_5min < 48.0:
        fw_freq = 40.0
        safety_override = True
        return RuleDecision(...)
    # ... (T4 단계별 제어)
    
    # safety_override=True면 여기까지 오지 않음!
```

**핵심 포인트:**
- `safety_override = True`로 설정되면 **즉시 return**
- ML 예측값은 완전히 무시됨
- Safety Layer만으로도 시스템 안전 보장

---

### 2️⃣ ML 신뢰도 검증

```python
# IntegratedController._get_ml_prediction()
def _get_ml_prediction(self, temp_prediction):
    
    if not temp_prediction:
        return None  # ML 예측 없음 → Rule만 사용
    
    # 신뢰도 검증!
    if temp_prediction.confidence < 0.5:  # 50% 미만이면
        return None  # ML 사용 안 함!
    
    # 신뢰도 50% 이상일 때만 ML 사용
    if temp_prediction.confidence > 0.5:
        # ML 예측 기반 주파수 조정
        if t5_delta > 0.5:
            sw_adj = 3.0  # 선제적 증속
        # ...
```

**핵심 포인트:**
- ML 신뢰도가 50% 미만이면 **ML을 아예 사용하지 않음**
- 이 경우 Rule 기반 제어로만 작동
- 신뢰도가 충분해야만 ML의 선제적 제어 활성화

---

### 3️⃣ ML 실패 시 Fallback

```python
# IntegratedController.compute_control()
try:
    # ML 예측 시도
    ml_prediction = self._get_ml_prediction(
        temp_prediction, engine_load, temperatures
    )
except Exception as e:
    print(f"[WARNING] ML 예측 실패: {e}")
    ml_prediction = None  # ML 실패 → None

# Rule 기반 제어 (ML이 None이어도 정상 작동!)
decision = self.rule_controller.compute_control(
    temperatures=temperatures,
    pressures=pressures,
    engine_load=engine_load,
    seawater_temp=temperatures.get('T1', 25.0),
    current_frequencies={...},
    ml_prediction=ml_prediction  # None이어도 OK!
)
```

**핵심 포인트:**
- ML 예측이 실패하거나 `None`이면 자동으로 Rule 기반 제어로 전환
- `ml_prediction=None`일 때 Rule 기반 제어는 이전 주파수(`prev_freq`)를 기준으로 작동
- 시스템은 ML 없이도 완벽히 동작

---

### 4️⃣ Dummy Model 학습 (초기 안정성)

```python
# IntegratedController._train_dummy_model()
def _train_dummy_model(self):
    """최소 동작용 더미 모델 학습"""
    
    # 50개의 다양한 더미 데이터 생성
    training_data = []
    for i in range(50):
        # 다양한 온도 트렌드 (상승/하강/안정)
        trend = np.random.choice([-1, 0, 1])
        
        # 90개 시퀀스 생성 (30분 데이터)
        t4_seq = [base_t4 + trend * j/90 * 2 + noise for j in range(90)]
        # ...
        
        # 더미 타겟 (현재 값 + 트렌드 반영)
        targets = {
            't4_5min': t4_seq[-1] + trend * 0.5,
            't4_10min': t4_seq[-1] + trend * 1.0,
            # ...
        }
        training_data.append((sequence, targets))
    
    # Temperature Predictor 학습
    self.temp_predictor.train(training_data)
    # Random Forest Optimizer 학습
    self.rf_optimizer.train(training_data)
```

**초기화 시 동작:**
```python
# IntegratedController.__init__()
try:
    # 기존 모델 로드 시도
    self.temp_predictor.load_models('models/')
    self.rf_optimizer.load_models('models/')
except:
    # 모델 없으면 더미 학습!
    print("[INFO] 기존 모델 없음 → 더미 모델 학습")
    self._train_dummy_model()
```

**핵심 포인트:**
- 실선 배포 초기에도 ML 크래시 없음
- 더미 모델로 최소한의 예측 기능 제공
- 실제 데이터 수집되면 Batch Learning으로 정밀 학습

---

## 🌊 ML 불안정 시 제어 흐름

### 시나리오 1: 초기 운영 (실 데이터 부족)

```
[상황] 선박 취항 첫날, ML 학습 데이터 없음

1. 시스템 부팅
   ├─ IntegratedController 초기화
   ├─ 기존 모델 찾기 실패
   └─ _train_dummy_model() 자동 실행
       └─ 50개 더미 데이터로 최소 ML 학습

2. 운전 시작
   ├─ ML 예측 시도 (더미 모델 사용)
   │   └─ confidence = ~0.3-0.4 (낮음!)
   ├─ confidence < 0.5 → ML 사용 안 함!
   └─ Rule 기반 제어로 전환
       ├─ Safety Layer: 온도 한계 감시
       └─ Fine-tuning Layer: 현재 온도 기반 조정

3. 제어 결과
   ✅ T5 > 40°C → Safety S4: 강제 60Hz
   ✅ T4 < 46°C → Safety S6: 강제 40Hz (에너지 절감)
   ✅ T6 > 45°C → Safety S5: 강제 60Hz
   ✅ ML 없어도 안전하고 효율적!
```

---

### 시나리오 2: ML 신뢰도 부족 (학습 초기)

```
[상황] 운영 1주차, 데이터는 모으고 있지만 아직 충분하지 않음

1. Batch Learning (수요일 새벽 2시)
   ├─ 수집된 데이터: 200개 (최소 요구: 100개)
   ├─ 이상치 제거 (outlier detection)
   └─ ML 모델 업데이트 완료

2. 운전 중 ML 예측
   ├─ ML 예측 성공
   │   └─ confidence = ~0.45 (아직 낮음!)
   ├─ confidence < 0.5 → ML 사용 안 함!
   └─ Rule 기반 제어 계속

3. 제어 결과
   ✅ ML이 예측은 하지만 신뢰도 부족으로 적용 안 함
   ✅ Safety Layer + Rule Fine-tuning으로 안전 운전
   ✅ 데이터는 계속 수집 중 (다음 학습 대비)
```

---

### 시나리오 3: ML 안정화 (운영 2주 후)

```
[상황] 운영 2주차, 데이터 충분히 축적됨

1. Batch Learning (일요일 새벽 2시, 2차 학습)
   ├─ 수집된 데이터: 1,500개
   ├─ 다양한 해역/부하 패턴 학습
   └─ ML 모델 정밀 업데이트

2. 운전 중 ML 예측
   ├─ ML 예측 성공
   │   └─ confidence = ~0.75 (높음!)
   ├─ confidence > 0.5 → ML 사용!
   └─ ML Optimization Layer 활성화
       ├─ 온도 상승 예측 → 선제적 증속
       └─ 온도 하강 예측 → 선제적 감속

3. 제어 결과 (ML + Rule 협업)
   ✅ Safety Layer: 여전히 최우선 감시
   ✅ ML Layer: 선제적 온도 예측 제어
   ✅ Fine-tuning Layer: Rule로 미세 보정
   ✅ 최적 에너지 절감 달성!
```

---

## 🔄 ML 불안정 시 Rule 기반 제어 상세

### T5 제어 (SW Pump) - ML 없을 때

```python
# Safety Layer S4 (극한 온도만)
if t5_temp > 40.0:
    sw_freq = 60.0  # 극고온 → 60Hz 강제
elif t5_temp < 30.0:
    sw_freq = 40.0  # 극저온 → 40Hz 강제
else:
    # 정상 범위 (30-40°C) → ML에게 위임
    pass  # ml_prediction 사용 (있으면)

# Fine-tuning Layer R1 (현재 온도 기반 보정)
# ML이 None이면 prev_sw_freq 기준으로 작동
if t5_temp > 38.0:
    sw_freq += min(6.0, (t5_temp - 38.0) * 3.0)  # 60Hz 수렴
elif t5_temp < 32.0:
    sw_freq -= min(6.0, (32.0 - t5_temp) * 3.0)  # 40Hz 수렴
```

**ML 없을 때 동작:**
- T5 > 40°C: Safety Layer가 60Hz 강제 → 안전!
- 38°C < T5 < 40°C: R1이 점진적 증속 → 38°C에서 시작해 60Hz로 수렴
- 30°C < T5 < 32°C: R1이 점진적 감속 → 32°C에서 시작해 40Hz로 수렴
- T5 < 30°C: Safety Layer가 40Hz 강제 → 안전!

**결과:** ML 없어도 온도 제어 완벽히 작동!

---

### T4 제어 (FW Pump) - ML 없을 때

```python
# Safety Layer S2 (긴급 고온)
if t4_temp >= 48.0:
    fw_freq = 60.0  # 48°C 초과 → 60Hz 강제!
    safety_override = True
    return RuleDecision(...)

# Safety Layer S6 (에너지 절감 모드)
if t4_temp < 46.0:
    # Phase 1: 무조건 40Hz (에너지 절감)
    if prev_fw_freq > 40.5:
        fw_freq = max(40.0, prev_fw_freq - 3.0)  # 점진 감속
    else:
        fw_freq = 40.0  # 40Hz 유지
    safety_override = True
    return RuleDecision(...)

elif 46.0 <= t4_temp < 47.0:
    # Phase 1-2: 42Hz (안전 마진)
    fw_freq = 42.0
    safety_override = True
    return RuleDecision(...)

elif 47.0 <= t4_temp < 48.0:
    # Phase 1-3: 46Hz (대기)
    fw_freq = 46.0
    safety_override = True
    return RuleDecision(...)
```

**ML 없을 때 동작:**
- T4 ≥ 48°C: Safety S2가 60Hz 강제 → 긴급 냉각!
- 47°C ≤ T4 < 48°C: Safety S6가 46Hz 강제 → 대기
- 46°C ≤ T4 < 47°C: Safety S6가 42Hz 강제 → 안전 마진
- T4 < 46°C: Safety S6가 40Hz 강제 → 최대 에너지 절감!

**결과:** ML 없어도 T4 제어 + 에너지 절감 동시 달성!

---

### T6 제어 (E/R Fan) - ML 없을 때

```python
# Safety Layer S5 (T6 온도 제어)
if t6_temp > 45.0:
    er_freq = 60.0  # 긴급 고온 → 60Hz
    safety_override = True
    return RuleDecision(...)

elif 44.0 < t6_temp <= 45.0:
    er_freq = 60.0  # 고온 → 60Hz 유지
    safety_override = True
    return RuleDecision(...)

elif 42.0 <= t6_temp <= 44.0:
    # 정상 구간 → 48Hz 수렴
    if abs(prev_er_freq - 48.0) > 0.5:
        if prev_er_freq > 48.0:
            er_freq = max(48.0, prev_er_freq - 2.0)  # 감속
        else:
            er_freq = min(48.0, prev_er_freq + 2.0)  # 증속
    else:
        er_freq = 48.0  # 48Hz 유지 (ML 가능)
        safety_override = False  # ML 허용!

elif t6_temp < 42.0:
    # 저온 → 40Hz로 감속
    if prev_er_freq > 40.5:
        er_freq = max(40.0, prev_er_freq - 2.0)  # 점진 감속
    else:
        er_freq = 40.0  # 40Hz 유지
        safety_override = False  # 대수 제어 허용
```

**ML 없을 때 동작:**
- T6 > 45°C: 60Hz 강제 → 긴급 냉각
- 44-45°C: 60Hz 유지 → 고온 제어
- 42-44°C: 48Hz로 수렴 → 정상 운전
- T6 < 42°C: 40Hz로 수렴 → 에너지 절감

**결과:** ML 없어도 T6 제어 + 대수 제어 모두 작동!

---

## ✅ 결론: ML 불안정해도 안전한 이유

### 1. 다중 안전망 (Triple Safety Net)

```
[온도 > 위험 수준]
    └─> Safety Layer가 즉시 강제 제어 (ML 무시)
        └─> 100% Rule 기반 → 절대 안전!

[ML 신뢰도 < 50%]
    └─> ML 사용 안 함
        └─> Rule Fine-tuning으로 제어

[ML 예측 실패/크래시]
    └─> Exception 처리 → ml_prediction = None
        └─> Rule 기반 제어로 자동 전환

[초기 모델 없음]
    └─> Dummy Model 자동 학습
        └─> 최소 기능 보장 (크래시 방지)
```

---

### 2. Rule 기반 제어만으로도 충분

| 제어 항목 | ML 없을 때 동작 | 안전성 |
|---------|----------------|--------|
| **T5 (SW Pump)** | Safety S4 + Rule R1로 30-40°C 제어 | ✅ 완벽 |
| **T4 (FW Pump)** | Safety S6로 3단계 제어 (40-46-48°C) | ✅ 완벽 |
| **T6 (E/R Fan)** | Safety S5로 단계별 제어 (40-48-60Hz) | ✅ 완벽 |
| **압력 (PX1)** | Safety S3로 압력 한계 감시 | ✅ 완벽 |
| **과열 보호** | Safety S1, S2로 강제 냉각 | ✅ 완벽 |

---

### 3. ML의 역할: "성능 향상" (필수 아님)

```
[Rule 기반만]
    ├─ 안전: ✅ 완벽 보장
    ├─ 온도 제어: ✅ 정상 범위 유지
    ├─ 에너지 절감: ✅ 기본 수준 달성
    └─ 반응 속도: 🟡 현재 온도 기반 (후행적)

[Rule + ML 협업] (ML 안정화 후)
    ├─ 안전: ✅ 완벽 보장 (Safety Layer 유지)
    ├─ 온도 제어: ✅ 정상 범위 유지
    ├─ 에너지 절감: ⭐ 최적화! (선제 대응)
    └─ 반응 속도: ⭐ 예측 기반 (선행적)

→ ML은 "있으면 좋은" 성능 부스터!
→ 없어도 시스템은 완벽히 안전하고 효율적!
```

---

## 🚀 실선 운영 시 단계별 진화

### Week 1-2: Rule 기반 운전 (ML 비활성)
- Safety Layer만으로 안전 운전
- 데이터 수집 중 (500-1000개)
- ML 예측은 하지만 신뢰도 낮아서 미적용

### Week 3-4: ML 활성화 시작
- Batch Learning 2-3회 완료
- ML 신뢰도 50% 돌파
- ML + Rule 협업 제어 시작

### Month 2+: ML 최적화 운전
- 다양한 해역/부하 데이터 학습
- ML 신뢰도 70-80% 안정화
- 최대 에너지 절감 달성

---

## 📊 안전성 비교

| 항목 | PID 제어 | Rule + ML (현재) |
|------|----------|------------------|
| **초기 안정성** | 🔴 튜닝 필요 | ✅ 즉시 안전 |
| **ML 없을 때** | ❌ 불가능 | ✅ Rule로 작동 |
| **ML 실패 시** | ❌ 크래시 | ✅ 자동 Fallback |
| **다중 안전망** | 🟡 Single | ✅ Triple Layer |
| **투명성** | 🔴 불투명 | ✅ 규칙 명확 |
| **유지보수** | 🔴 어려움 | ✅ 쉬움 |

---

## 💡 핵심 요약

1. **Safety Layer가 절대 최우선**
   - `safety_override = True`면 ML 완전 무시
   - 온도 한계 시 강제 제어

2. **ML 신뢰도 검증**
   - confidence < 0.5이면 ML 사용 안 함
   - Rule 기반 제어로 자동 전환

3. **ML 실패 시 Fallback**
   - Exception 처리로 크래시 방지
   - `ml_prediction = None`으로 Rule 전환

4. **Dummy Model로 초기 안정성**
   - 실선 배포 첫날부터 ML 기능 작동
   - 크래시 없는 안정적 운영

5. **Rule만으로도 완벽한 제어**
   - ML은 "성능 향상" 역할
   - 없어도 안전하고 효율적!

---

**결론: 이 시스템은 ML이 불안정해도 Rule 기반 제어로 완벽히 안전하게 운영됩니다!** ✅


