# 인증기관 질의 답변서 - 2. AI 예측 제어 정확도 (축약본)

**시험 대상**: AI based Energy Saving System (V1.0)
**측정 대상**: AI 최적 주파수 예측 정확도
**시험 횟수**: 150개 시나리오 (저부하 50개, 중부하 50개, 고부하 50개)
**적합 기준**: 전체 ≥85%, 저부하 ≥90%, 중부하 ≥85%, 고부하 ≥80%

---

## [메모:4] 시험 횟수 결정

**시험 횟수**: **150개 시나리오**

**부하별 분포**:
- 저부하 (0-40%): 50개
- 중부하 (40-70%): 50개
- 고부하 (70-100%): 50개

**결정 근거**:
- 각 부하 구간별 50개씩 균등 배분
- 통계적 유의성 확보 (신뢰수준 95%)

**생성 코드** (`src/simulation/scenarios.py`):
```python
def generate_test_scenarios_by_load():
    scenarios = []

    # 저부하 50개
    for i in range(50):
        engine_load = random.uniform(0, 40)
        scenarios.append(generate_scenario(engine_load, 'low'))

    # 중부하 50개
    for i in range(50):
        engine_load = random.uniform(40, 70)
        scenarios.append(generate_scenario(engine_load, 'medium'))

    # 고부하 50개
    for i in range(50):
        engine_load = random.uniform(70, 100)
        scenarios.append(generate_scenario(engine_load, 'high'))

    return scenarios  # 총 150개
```

---

## [메모:14] 시험 데이터 형식

**데이터 생성 방식**: **Python 스크립트 실행 시 자동 생성**

**구현 위치**: `src/simulation/scenarios.py`

**특징**:
- 재현성: 고정 난수 시드 사용 (`random.seed(42)`)
- 자동화: 파일 관리 불필요
- 추적성: ID 자동 부여 (LOW_001, MED_050, HIGH_150)

**실행 예시**:
```python
scenario_gen = ScenarioGenerator()
test_scenarios = scenario_gen.generate_test_scenarios(count=150)

print(f"생성된 시나리오: {len(test_scenarios)}개")
print(f"저부하: {sum(1 for s in test_scenarios if s.load_category=='low')}개")
```

---

## [메모:5] Ground Truth 데이터

**Ground Truth 정의**: **물리 법칙 기반 최적 주파수** (AI 예측의 정답 기준)

**산출 방법**:
- 위치: `src/core/physics_based_control.py`
- 적용 법칙:
  - 열교환 방정식: Q = m × Cp × ΔT
  - 펌프 세제곱 법칙: P ∝ f³
  - 안전 제약조건

**계산 프로세스**:
```python
class PhysicsBasedController:
    def calculate_optimal_frequencies(self, scenario):
        # 1. 필요 냉각 용량 계산
        required_cooling = self._calculate_required_cooling(scenario.engine_load)

        # 2. 주파수 계산 (열교환 방정식)
        sw_freq = self._calculate_sw_pump_frequency(scenario.t1, scenario.t2, required_cooling)
        fw_freq = self._calculate_fw_pump_frequency(scenario.t4, scenario.t3, required_cooling * 0.7)
        fan_freq = self._calculate_fan_frequency(scenario.t6, scenario.t7)

        # 3. 안전 제약조건 적용 (40~60Hz)
        return GroundTruthOutput(
            sw_pump_freq=np.clip(sw_freq, 40, 60),
            fw_pump_freq=np.clip(fw_freq, 40, 60),
            fan_freq=np.clip(fan_freq, 40, 60)
        )
```

**준비 방법**:
```python
# 150개 시나리오에 대한 Ground Truth 자동 계산
physics_controller = PhysicsBasedController()
ground_truths = [physics_controller.calculate_optimal_frequencies(s)
                 for s in test_scenarios]
```

---

## [메모:6] 정확도 자동 계산

**자동 계산**: 예, **Python 스크립트가 전체 자동 계산 및 판정**

**구현 위치**: `tests/test_ai_prediction_accuracy.py`

**정확도 판정 기준**: ±3Hz 이내면 정확
```python
def calculate_accuracy(ai_prediction, ground_truth, tolerance=3.0):
    error = abs(ai_prediction - ground_truth)
    return error <= tolerance  # ±3Hz 이내
```

**시험 프로세스**:
```python
def test_ai_prediction_accuracy():
    # 1. 시나리오 생성 (150개)
    test_scenarios = scenario_gen.generate_test_scenarios(150)

    # 2. Ground Truth 계산 (물리 기반)
    ground_truths = [physics_controller.calculate_optimal_frequencies(s)
                     for s in test_scenarios]

    # 3. AI 예측 수행
    ai_predictions = [ai_controller.compute_predictive_control(s)
                      for s in test_scenarios]

    # 4. 정확도 자동 계산
    for scenario, ai_pred, gt in zip(test_scenarios, ai_predictions, ground_truths):
        overall_accurate = (
            calculate_accuracy(ai_pred.sw_pump_freq, gt.sw_pump_freq) and
            calculate_accuracy(ai_pred.fw_pump_freq, gt.fw_pump_freq) and
            calculate_accuracy(ai_pred.fan_freq, gt.fan_freq)
        )  # 3개 모두 정확해야 함

    # 5. 통계 계산
    overall_accuracy = df['overall_accurate'].mean() * 100
    low_load_accuracy = df[df['load_category']=='low']['overall_accurate'].mean() * 100
    medium_load_accuracy = df[df['load_category']=='medium']['overall_accurate'].mean() * 100
    high_load_accuracy = df[df['load_category']=='high']['overall_accurate'].mean() * 100

    # 6. 합격 판정 (자동)
    final_pass = (overall_accuracy >= 85.0 and
                  low_load_accuracy >= 90.0 and
                  medium_load_accuracy >= 85.0 and
                  high_load_accuracy >= 80.0)
```

**합격 기준**: 모든 조건 동시 만족
1. 전체 정확도 ≥ 85.0%
2. 저부하 정확도 ≥ 90.0%
3. 중부하 정확도 ≥ 85.0%
4. 고부하 정확도 ≥ 80.0%

**출력 예시**:
```
============================================================
AI 예측 제어 정확도 시험 결과
============================================================
총 시나리오: 150개

[전체 정확도]
  정확도: 87.33%
  기준: ≥85.0%
  판정: ✓ 합격

[부하별 정확도]
  저부하 (0-40%): 92.00% (기준 ≥90%) ✓
  중부하 (40-70%): 86.00% (기준 ≥85%) ✓
  고부하 (70-100%): 84.00% (기준 ≥80%) ✓

[최종 판정]
  ✓✓✓ 합격 ✓✓✓

상세 결과: test_results_ai_accuracy.csv
```

---

## [메모:7] 부하별 정확도 검증

**시나리오 분류**: 엔진 부하(%)로 자동 분류
- 저부하: 0 ≤ load < 40
- 중부하: 40 ≤ load < 70
- 고부하: 70 ≤ load ≤ 100

**통계 산출**:
```python
def analyze_accuracy_by_load(results_df):
    for load_category, criteria in [('low', 90.0), ('medium', 85.0), ('high', 80.0)]:
        load_df = results_df[results_df['load_category'] == load_category]

        # 정확도 계산
        total_count = len(load_df)
        accurate_count = load_df['overall_accurate'].sum()
        accuracy_rate = (accurate_count / total_count) * 100

        # 장비별 평균 오차
        sw_avg_error = load_df['sw_error'].mean()
        fw_avg_error = load_df['fw_error'].mean()
        fan_avg_error = load_df['fan_error'].mean()

        # 판정
        pass_flag = accuracy_rate >= criteria
```

**출력 예시**:
```
[저부하 (0-40%)]
  시나리오 개수: 50개
  엔진 부하 범위: 2.3% ~ 39.8% (평균 20.5%)
  전체 정확도: 92.00% (46/50)
  합격 기준: ≥90.0%
  판정: ✓ 합격

  [장비별 정확도]
    Main SW 펌프: 94.00% (평균 오차 1.85Hz)
    LT FW 펌프: 96.00% (평균 오차 1.62Hz)
    E/R 팬: 98.00% (평균 오차 1.23Hz)

  [오차 분포]
    0-1Hz: 22개 (44.0%)
    1-2Hz: 18개 (36.0%)
    2-3Hz: 6개 (12.0%)
    >3Hz: 4개 (8.0%)
```

**CSV 파일 저장**:
- `test_results_ai_accuracy.csv` (전체 150개)
- `test_results_ai_accuracy_low_load.csv` (저부하 50개)
- `test_results_ai_accuracy_medium_load.csv` (중부하 50개)
- `test_results_ai_accuracy_high_load.csv` (고부하 50개)

---

## 시험 실행 방법

```bash
# 시험 실행
python tests/test_ai_prediction_accuracy.py

# 예상 소요 시간: 3-5분 (150개 × 2초)
```

---

## 핵심 요약

| 항목 | 내용 |
|------|------|
| **시험 횟수** | 150개 (저/중/고 부하 각 50개) |
| **데이터 생성** | Python 스크립트 자동 생성 (고정 시드) |
| **Ground Truth** | 물리 법칙 기반 최적 주파수 |
| **정확도 기준** | ±3Hz 이내면 정확 |
| **자동화** | 시나리오 생성, GT 계산, 정확도 측정, 판정 모두 자동 |
| **출력** | 화면 + 로그 + CSV (부하별 분리) |
| **합격 기준** | 전체 ≥85% AND 저부하 ≥90% AND 중부하 ≥85% AND 고부하 ≥80% |
