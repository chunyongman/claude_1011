# 인증기관 질의 답변서 - 2. AI 예측 제어 정확도

## 시험 항목 개요

**시험 항목**: AI 예측 제어 정확도
**측정 대상**: AI 모델의 최적 주파수 예측 정확도
**시험 기준**: 전체 정확도 ≥85%, 부하별 정확도 (저부하 ≥90%, 중부하 ≥85%, 고부하 ≥80%)
**시험 횟수**: 100-200개 시나리오
**시험 환경**: Python 기반 시뮬레이션 환경 (Mock PLC/VFD)

---

## 질의 답변

### [메모:4] 시험횟수 결정 - 100회 vs 200회

**Q1**: 100회와 200회 중 어느 것으로 진행하나요?
**Q2**: 각 부하 범위별로 몇 개씩 테스트하나요?

**답변**:

**시험 횟수**: 총 **150개 시나리오**로 진행합니다.

**부하별 분포**:
- **저부하 (0-40%)**: 50개 시나리오
- **중부하 (40-70%)**: 50개 시나리오
- **고부하 (70-100%)**: 50개 시나리오

**결정 근거**:
1. 100개는 통계적 신뢰도가 다소 부족하고, 200개는 시험 시간이 과도함
2. 150개는 각 부하 구간별로 50개씩 균등 배분 가능
3. 부하 구간별 최소 50개 샘플로 통계적 유의성 확보 (신뢰수준 95%, 오차범위 ±5%)

**시험 코드 예시**:
```python
def generate_test_scenarios_by_load():
    """부하별 균등 분포 시나리오 생성"""
    scenarios = []

    # 저부하 50개
    for i in range(50):
        engine_load = random.uniform(0, 40)
        scenario = generate_scenario_with_load(engine_load, category='low')
        scenarios.append(scenario)

    # 중부하 50개
    for i in range(50):
        engine_load = random.uniform(40, 70)
        scenario = generate_scenario_with_load(engine_load, category='medium')
        scenarios.append(scenario)

    # 고부하 50개
    for i in range(50):
        engine_load = random.uniform(70, 100)
        scenario = generate_scenario_with_load(engine_load, category='high')
        scenarios.append(scenario)

    return scenarios  # 총 150개
```

---

### [메모:14] 시험 데이터 형식

**Q1**: 150개 시나리오를 파일로 미리 만들어 놓나요?
**Q2**: 아니면 Python 스크립트로 실행 시 생성하나요?

**답변**:

**데이터 생성 방식**: **Python 스크립트 실행 시 자동 생성** 방식을 사용합니다.

**구현 위치**: `src/simulation/scenarios.py`

**생성 프로세스**:
```python
# src/simulation/scenarios.py
class ScenarioGenerator:
    """시나리오 자동 생성기"""

    def generate_test_scenarios(self, count: int = 150) -> List[TestScenario]:
        """
        시험용 시나리오 생성
        - 부하별 균등 분포
        - 재현 가능한 난수 시드 사용
        """
        random.seed(42)  # 재현성을 위한 고정 시드
        np.random.seed(42)

        scenarios = []
        scenarios_per_load = count // 3

        # 저부하 시나리오
        scenarios.extend(self._generate_low_load_scenarios(scenarios_per_load))

        # 중부하 시나리오
        scenarios.extend(self._generate_medium_load_scenarios(scenarios_per_load))

        # 고부하 시나리오
        scenarios.extend(self._generate_high_load_scenarios(scenarios_per_load))

        return scenarios

    def _generate_low_load_scenarios(self, count: int) -> List[TestScenario]:
        """저부하 (0-40%) 시나리오 생성"""
        scenarios = []
        for i in range(count):
            scenario = TestScenario(
                id=f"LOW_{i+1:03d}",
                engine_load=random.uniform(0, 40),
                t1=random.uniform(40, 55),  # Main SW 입구
                t2=random.uniform(45, 60),  # Main SW 출구
                t3=random.uniform(43, 58),  # LT FW 출구
                t4=random.uniform(38, 52),  # LT FW 입구
                t5=random.uniform(25, 32),  # SW 펌프 베어링
                t6=random.uniform(28, 38),  # E/R 온도
                t7=random.uniform(26, 35),  # E/R 환기구
                px1=random.uniform(2.0, 2.3),  # 압력
                gps_speed=random.uniform(8, 12),
                load_category='low'
            )
            scenarios.append(scenario)
        return scenarios
```

**장점**:
1. **재현성**: 동일한 난수 시드 사용으로 테스트 재현 가능
2. **유연성**: 시나리오 개수나 분포를 코드로 쉽게 조정 가능
3. **자동화**: 파일 관리 없이 스크립트 실행만으로 시험 가능
4. **추적성**: 각 시나리오에 ID 자동 부여 (LOW_001, MED_050, HIGH_150 등)

**시험 실행 예시**:
```python
# tests/test_stage2.py
def test_ai_prediction_accuracy():
    scenario_gen = ScenarioGenerator()
    test_scenarios = scenario_gen.generate_test_scenarios(count=150)

    print(f"생성된 시나리오: {len(test_scenarios)}개")
    print(f"저부하: {sum(1 for s in test_scenarios if s.load_category=='low')}개")
    print(f"중부하: {sum(1 for s in test_scenarios if s.load_category=='medium')}개")
    print(f"고부하: {sum(1 for s in test_scenarios if s.load_category=='high')}개")
```

---

### [메모:5] Ground Truth 데이터 내용 및 준비

**Q1**: Ground Truth는 무엇을 의미하나요?
**Q2**: Ground Truth는 어떻게 준비하나요?

**답변**:

**Ground Truth 정의**:
Ground Truth는 **물리 법칙 기반 최적 주파수**를 의미합니다. AI 모델의 예측 정확도를 평가하기 위한 **정답 기준값**입니다.

**Ground Truth 산출 방법**:

1. **물리 기반 계산 엔진 사용**
   - 위치: `src/core/physics_based_control.py`
   - 열역학 1법칙, 펌프 세제곱 법칙 적용
   - 안전 제약조건 고려

2. **Ground Truth 계산 로직**:
```python
# src/core/physics_based_control.py
class PhysicsBasedController:
    """물리 법칙 기반 Ground Truth 계산"""

    def calculate_optimal_frequencies(self, scenario: TestScenario) -> GroundTruthOutput:
        """
        물리 법칙으로 최적 주파수 계산
        - 열교환 방정식: Q = m × Cp × ΔT
        - 펌프 세제곱 법칙: P ∝ f³
        - 안전 제약조건 적용
        """

        # 1. 필요 냉각 용량 계산 (엔진 부하 기반)
        required_cooling = self._calculate_required_cooling(scenario.engine_load)

        # 2. Main SW 펌프 주파수 계산
        sw_freq = self._calculate_sw_pump_frequency(
            t_in=scenario.t1,
            t_out=scenario.t2,
            required_q=required_cooling
        )

        # 3. LT FW 펌프 주파수 계산
        fw_freq = self._calculate_fw_pump_frequency(
            t_in=scenario.t4,
            t_out=scenario.t3,
            required_q=required_cooling * 0.7  # FW는 SW의 70%
        )

        # 4. E/R 팬 주파수 계산
        fan_freq = self._calculate_fan_frequency(
            er_temp=scenario.t6,
            ventilation_temp=scenario.t7
        )

        # 5. 안전 제약조건 적용
        sw_freq = self._apply_safety_constraints(sw_freq, scenario)
        fw_freq = self._apply_safety_constraints(fw_freq, scenario)
        fan_freq = self._apply_safety_constraints(fan_freq, scenario)

        return GroundTruthOutput(
            sw_pump_freq=sw_freq,
            fw_pump_freq=fw_freq,
            fan_freq=fan_freq,
            energy_consumption=self._calculate_energy(sw_freq, fw_freq, fan_freq),
            reasoning="Physics-based optimal calculation"
        )

    def _calculate_sw_pump_frequency(self, t_in, t_out, required_q):
        """Main SW 펌프 최적 주파수 계산"""
        # 열교환 방정식: Q = m × Cp × ΔT
        # 필요 유량: m = Q / (Cp × ΔT)
        delta_t = t_out - t_in
        if delta_t < 3.0:  # 최소 온도차
            delta_t = 3.0

        required_flow = required_q / (4.18 * delta_t)  # Cp(물) = 4.18 kJ/kg·K

        # 세제곱 법칙: Q ∝ f → f = 60 × (Q / Q_rated)^(1/3)
        rated_flow = 1250  # m³/h
        frequency = 60 * (required_flow / rated_flow) ** (1/3)

        # 제약조건 적용
        return np.clip(frequency, 40, 60)
```

**Ground Truth 준비 프로세스**:

```python
def prepare_ground_truth_data(test_scenarios: List[TestScenario]) -> List[GroundTruthOutput]:
    """150개 시나리오에 대한 Ground Truth 계산"""
    physics_controller = PhysicsBasedController()
    ground_truths = []

    print("Ground Truth 계산 중...")
    for i, scenario in enumerate(test_scenarios, 1):
        gt = physics_controller.calculate_optimal_frequencies(scenario)
        ground_truths.append(gt)

        if i % 50 == 0:
            print(f"  진행: {i}/{len(test_scenarios)}")

    print("Ground Truth 계산 완료")
    return ground_truths
```

**Ground Truth 검증**:
- 물리 법칙 준수 확인 (세제곱 법칙, 열교환 방정식)
- 안전 제약조건 위반 없음 확인
- 에너지 효율성 확인 (최소 에너지 소비)

**Ground Truth 예시**:
```
시나리오 LOW_001 (엔진 부하 25%):
  - Main SW 펌프: 48Hz (물리 계산)
  - LT FW 펌프: 46Hz (물리 계산)
  - E/R 팬: 45Hz (물리 계산)
  - 에너지: 245 kW
```

---

### [메모:6] 정확도 자동 계산

**Q1**: 정확도는 자동으로 계산되나요?
**Q2**: 합격 기준은 어떻게 판정하나요?

**답변**:

**자동 계산**: 예, **Python 스크립트가 전체 자동 계산 및 판정**합니다.

**구현 위치**: `tests/test_ai_prediction_accuracy.py`

**정확도 계산 로직**:

```python
def calculate_accuracy(ai_prediction: float, ground_truth: float, tolerance: float = 3.0) -> bool:
    """
    정확도 계산
    - 허용 오차: ±3Hz 이내면 정확한 것으로 간주
    - 근거: 제어 시스템의 실용적 허용 범위
    """
    error = abs(ai_prediction - ground_truth)
    return error <= tolerance

def test_ai_prediction_accuracy():
    """Test Item 2: AI 예측 제어 정확도 - 150개 시나리오"""

    # 1. 시나리오 생성
    scenario_gen = ScenarioGenerator()
    test_scenarios = scenario_gen.generate_test_scenarios(count=150)

    # 2. Ground Truth 계산
    physics_controller = PhysicsBasedController()
    ground_truths = [physics_controller.calculate_optimal_frequencies(s)
                     for s in test_scenarios]

    # 3. AI 예측 수행
    ai_controller = PredictiveController()
    ai_predictions = [ai_controller.compute_predictive_control(s)
                      for s in test_scenarios]

    # 4. 정확도 계산 (자동)
    results = []
    for i, (scenario, ai_pred, gt) in enumerate(zip(test_scenarios, ai_predictions, ground_truths)):
        result = {
            'scenario_id': scenario.id,
            'load_category': scenario.load_category,
            'engine_load': scenario.engine_load,

            # Main SW 펌프
            'sw_ai': ai_pred.sw_pump_freq,
            'sw_gt': gt.sw_pump_freq,
            'sw_error': abs(ai_pred.sw_pump_freq - gt.sw_pump_freq),
            'sw_accurate': calculate_accuracy(ai_pred.sw_pump_freq, gt.sw_pump_freq),

            # LT FW 펌프
            'fw_ai': ai_pred.fw_pump_freq,
            'fw_gt': gt.fw_pump_freq,
            'fw_error': abs(ai_pred.fw_pump_freq - gt.fw_pump_freq),
            'fw_accurate': calculate_accuracy(ai_pred.fw_pump_freq, gt.fw_pump_freq),

            # E/R 팬
            'fan_ai': ai_pred.fan_freq,
            'fan_gt': gt.fan_freq,
            'fan_error': abs(ai_pred.fan_freq - gt.fan_freq),
            'fan_accurate': calculate_accuracy(ai_pred.fan_freq, gt.fan_freq),

            # 전체 정확도 (3개 모두 정확해야 함)
            'overall_accurate': (
                calculate_accuracy(ai_pred.sw_pump_freq, gt.sw_pump_freq) and
                calculate_accuracy(ai_pred.fw_pump_freq, gt.fw_pump_freq) and
                calculate_accuracy(ai_pred.fan_freq, gt.fan_freq)
            )
        }
        results.append(result)

    # 5. 통계 계산 (자동)
    df = pd.DataFrame(results)

    # 전체 정확도
    overall_accuracy = df['overall_accurate'].mean() * 100

    # 부하별 정확도
    low_load_accuracy = df[df['load_category']=='low']['overall_accurate'].mean() * 100
    medium_load_accuracy = df[df['load_category']=='medium']['overall_accurate'].mean() * 100
    high_load_accuracy = df[df['load_category']=='high']['overall_accurate'].mean() * 100

    # 6. 합격 판정 (자동)
    pass_overall = overall_accuracy >= 85.0
    pass_low = low_load_accuracy >= 90.0
    pass_medium = medium_load_accuracy >= 85.0
    pass_high = high_load_accuracy >= 80.0

    final_pass = pass_overall and pass_low and pass_medium and pass_high

    # 7. 결과 출력
    print("="*60)
    print("AI 예측 제어 정확도 시험 결과")
    print("="*60)
    print(f"총 시나리오: {len(results)}개")
    print(f"\n[전체 정확도]")
    print(f"  정확도: {overall_accuracy:.2f}%")
    print(f"  기준: ≥85.0%")
    print(f"  판정: {'✓ 합격' if pass_overall else '✗ 불합격'}")

    print(f"\n[부하별 정확도]")
    print(f"  저부하 (0-40%): {low_load_accuracy:.2f}% (기준 ≥90%) {'✓' if pass_low else '✗'}")
    print(f"  중부하 (40-70%): {medium_load_accuracy:.2f}% (기준 ≥85%) {'✓' if pass_medium else '✗'}")
    print(f"  고부하 (70-100%): {high_load_accuracy:.2f}% (기준 ≥80%) {'✓' if pass_high else '✗'}")

    print(f"\n[최종 판정]")
    print(f"  {'='*58}")
    print(f"  {'✓✓✓ 합격 ✓✓✓' if final_pass else '✗✗✗ 불합격 ✗✗✗'}")
    print(f"  {'='*58}")

    # 8. CSV 파일 저장
    df.to_csv('test_results_ai_accuracy.csv', index=False, encoding='utf-8-sig')
    print(f"\n상세 결과: test_results_ai_accuracy.csv")

    return final_pass
```

**합격 기준 판정**:

모든 조건을 **동시에 만족**해야 합격:
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
  ==========================================================
  ✓✓✓ 합격 ✓✓✓
  ==========================================================

상세 결과: test_results_ai_accuracy.csv
```

---

### [메모:7] 부하별 정확도 검증

**Q1**: 부하 범위별 정확도는 어떻게 검증하나요?
**Q2**: 각 부하 구간의 세부 통계는 어떻게 산출하나요?

**답변**:

**부하별 정확도 검증 방법**:

1. **시나리오 분류**: 엔진 부하(%)로 자동 분류
   - 저부하: 0 ≤ load < 40
   - 중부하: 40 ≤ load < 70
   - 고부하: 70 ≤ load ≤ 100

2. **부하별 통계 산출**:

```python
def analyze_accuracy_by_load(results_df: pd.DataFrame):
    """부하별 상세 통계 분석"""

    print("\n" + "="*80)
    print("부하별 상세 정확도 분석")
    print("="*80)

    for load_category, criteria in [('low', 90.0), ('medium', 85.0), ('high', 80.0)]:
        load_name = {'low': '저부하 (0-40%)', 'medium': '중부하 (40-70%)', 'high': '고부하 (70-100%)'}

        # 해당 부하 데이터 필터링
        load_df = results_df[results_df['load_category'] == load_category]

        # 통계 계산
        total_count = len(load_df)
        accurate_count = load_df['overall_accurate'].sum()
        accuracy_rate = (accurate_count / total_count) * 100

        # 장비별 평균 오차
        sw_avg_error = load_df['sw_error'].mean()
        fw_avg_error = load_df['fw_error'].mean()
        fan_avg_error = load_df['fan_error'].mean()

        # 장비별 정확도
        sw_accuracy = load_df['sw_accurate'].mean() * 100
        fw_accuracy = load_df['fw_accurate'].mean() * 100
        fan_accuracy = load_df['fan_accurate'].mean() * 100

        # 엔진 부하 범위
        load_min = load_df['engine_load'].min()
        load_max = load_df['engine_load'].max()
        load_avg = load_df['engine_load'].mean()

        # 출력
        print(f"\n[{load_name[load_category]}]")
        print(f"  시나리오 개수: {total_count}개")
        print(f"  엔진 부하 범위: {load_min:.1f}% ~ {load_max:.1f}% (평균 {load_avg:.1f}%)")
        print(f"  \n  전체 정확도: {accuracy_rate:.2f}% ({accurate_count}/{total_count})")
        print(f"  합격 기준: ≥{criteria:.1f}%")
        print(f"  판정: {'✓ 합격' if accuracy_rate >= criteria else '✗ 불합격'}")

        print(f"  \n  [장비별 정확도]")
        print(f"    Main SW 펌프: {sw_accuracy:.2f}% (평균 오차 {sw_avg_error:.2f}Hz)")
        print(f"    LT FW 펌프: {fw_accuracy:.2f}% (평균 오차 {fw_avg_error:.2f}Hz)")
        print(f"    E/R 팬: {fan_accuracy:.2f}% (평균 오차 {fan_avg_error:.2f}Hz)")

        # 오차 분포 분석
        print(f"  \n  [오차 분포]")
        error_ranges = [
            ("0-1Hz", 0, 1),
            ("1-2Hz", 1, 2),
            ("2-3Hz", 2, 3),
            (">3Hz", 3, 999)
        ]

        for range_name, min_err, max_err in error_ranges:
            count = len(load_df[
                (load_df['sw_error'] >= min_err) & (load_df['sw_error'] < max_err) |
                (load_df['fw_error'] >= min_err) & (load_df['fw_error'] < max_err) |
                (load_df['fan_error'] >= min_err) & (load_df['fan_error'] < max_err)
            ])
            percentage = (count / total_count) * 100
            print(f"    {range_name}: {count}개 ({percentage:.1f}%)")

    print("\n" + "="*80)
```

**출력 예시**:

```
================================================================================
부하별 상세 정확도 분석
================================================================================

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

[중부하 (40-70%)]
  시나리오 개수: 50개
  엔진 부하 범위: 40.2% ~ 69.9% (평균 55.3%)

  전체 정확도: 86.00% (43/50)
  합격 기준: ≥85.0%
  판정: ✓ 합격

  [장비별 정확도]
    Main SW 펌프: 90.00% (평균 오차 2.12Hz)
    LT FW 펌프: 88.00% (평균 오차 2.35Hz)
    E/R 팬: 92.00% (평균 오차 1.98Hz)

  [오차 분포]
    0-1Hz: 18개 (36.0%)
    1-2Hz: 20개 (40.0%)
    2-3Hz: 5개 (10.0%)
    >3Hz: 7개 (14.0%)

[고부하 (70-100%)]
  시나리오 개수: 50개
  엔진 부하 범위: 70.1% ~ 98.7% (평균 84.2%)

  전체 정확도: 84.00% (42/50)
  합격 기준: ≥80.0%
  판정: ✓ 합격

  [장비별 정확도]
    Main SW 펌프: 86.00% (평균 오차 2.58Hz)
    LT FW 펌프: 84.00% (평균 오차 2.73Hz)
    E/R 팬: 88.00% (평균 오차 2.45Hz)

  [오차 분포]
    0-1Hz: 15개 (30.0%)
    1-2Hz: 19개 (38.0%)
    2-3Hz: 8개 (16.0%)
    >3Hz: 8개 (16.0%)

================================================================================
```

**CSV 파일 저장**:
```python
# 부하별 상세 결과를 별도 CSV로 저장
for load_category in ['low', 'medium', 'high']:
    load_df = results_df[results_df['load_category'] == load_category]
    load_df.to_csv(f'test_results_ai_accuracy_{load_category}_load.csv',
                   index=False, encoding='utf-8-sig')
```

생성되는 파일:
- `test_results_ai_accuracy_low_load.csv` (저부하 50개)
- `test_results_ai_accuracy_medium_load.csv` (중부하 50개)
- `test_results_ai_accuracy_high_load.csv` (고부하 50개)

---

## 시험 실행 방법

```bash
# Python 환경 설정
set PYTHONPATH=%CD%

# 시험 실행
python tests/test_ai_prediction_accuracy.py
```

**실행 시간**: 약 3-5분 (150개 시나리오 × 2초/시나리오)

---

## 출력 결과물

1. **콘솔 출력**: 실시간 진행 상황 및 최종 판정
2. **로그 파일**: `logs/ai_accuracy_test_YYYYMMDD_HHMMSS.log`
3. **CSV 파일**:
   - `test_results_ai_accuracy.csv` (전체 150개)
   - `test_results_ai_accuracy_low_load.csv` (저부하 50개)
   - `test_results_ai_accuracy_medium_load.csv` (중부하 50개)
   - `test_results_ai_accuracy_high_load.csv` (고부하 50개)

---

## 참고 사항

### AI 모델 구성
- **온도 예측기**: Polynomial Regression (2차 다항식)
- **최적화 엔진**: Random Forest Regressor (100 trees)
- **패턴 분류기**: K-Means Clustering (15 clusters)

### 정확도 기준 근거
- **허용 오차 ±3Hz**: 제어 시스템의 실용적 허용 범위
- **부하별 차등 기준**: 고부하일수록 제어 난이도 증가 반영
  - 저부하 ≥90%: 안정적 운전 구간
  - 중부하 ≥85%: 일반적 운전 구간
  - 고부하 ≥80%: 불안정 운전 구간

### 물리 법칙 기반 검증
- 열교환 방정식: Q = m × Cp × ΔT
- 펌프 세제곱 법칙: P ∝ f³
- 팬 친화 법칙: Q ∝ f, P ∝ f³
