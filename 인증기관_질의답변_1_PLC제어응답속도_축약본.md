# 인증기관 질의 답변서 - 1. PLC 제어 응답속도 (축약본)

**시험 대상**: AI based Energy Saving System (V1.0)
**신청기관**: 오엠텍㈜
**측정 항목**: AI 계산 완료 → VFD 변경 완료 시간
**측정 횟수**: 50회
**적합 기준**: 평균 0.6~0.8초, 최대 <1.0초

---

## [메모:13] 입력 데이터 구조

**50개 시나리오, 각 1회씩 실행**

**입력 데이터 항목**:
- 온도 센서 7개: T1(해수입구), T2(Main SW출구), T3(Aux SW출구), T4(FW입구), T5(FW출구), T6(E/R온도), T7(외기)
- 압력: PX1(해수압력)
- 운전 조건: 엔진부하(%), 선속(knots), GPS 위치

**출력 데이터**:
- SW펌프 주파수 (40~60Hz)
- FW펌프 주파수 (40~60Hz)
- E/R팬 주파수 (40~60Hz)
- 운전 대수 (펌프 1~2대, 팬 2~4대)

**생성 방식**: Python 스크립트 실행 시 자동 생성 (`src/simulation/scenarios.py`)

---

## [메모:15] Python 측정 방법

**측정 도구**: `time.perf_counter()` (마이크로초 정밀도)

**측정 코드** (`tests/test_stage2.py`):
```python
# 50개 시나리오 생성
test_data = scenario_gen.generate_random_scenarios(50)

for i, scenario in enumerate(test_data, 1):
    # AI 계산 완료 시점 (t1)
    t1 = time.perf_counter()

    # AI 최적 주파수 계산
    control_output = ai_controller.compute_predictive_control(scenario)

    # PLC → VFD 전송 및 변경 완료 대기
    plc_client.write_frequency(control_output)
    vfd_client.wait_frequency_change_complete()

    # VFD 변경 완료 시점 (t2)
    t2 = time.perf_counter()

    response_time = t2 - t1
    print(f"[{i}/50] 응답시간: {response_time:.3f}초")
```

**소스 코드 위치**:
- 시험 실행: `tests/test_stage2.py`
- PLC 통신: `src/communication/modbus_client.py`
- AI 추론: `src/ml/predictive_controller.py`
- 시나리오 생성: `src/simulation/scenarios.py`

---

## [메모:12] 측정 시작 시점

**"AI가 최적 주파수를 계산한 시점" = 계산 완료 시점 (t1)**

| 시점 | 이벤트 | 측정 여부 |
|------|--------|-----------|
| t0 | AI 계산 시작 | ❌ 제외 |
| **t1** | **AI 계산 완료** | ✅ **측정 시작** |
| t1+α | PLC 명령 전송 | - |
| t1+β | VFD 변경 시작 | - |
| **t2** | **VFD 변경 완료** | ✅ **측정 종료** |

**응답시간 = t2 - t1** (AI 계산 시간 제외)

---

## [메모:21] / [메모:2] 결과 출력 방식

**3가지 방식 모두 지원**:

1. **화면 출력** (실시간):
```
[ 1/50] 응답시간: 0.723초 (AI:8.3ms, PLC:152ms, VFD:183ms)
[ 2/50] 응답시간: 0.715초
...
[50/50] 응답시간: 0.718초

평균 응답시간: 0.721초
최대 응답시간: 0.856초
최종 판정: ✓ 적합
```

2. **로그 파일**: `logs/plc_response_test_YYYYMMDD_HHMMSS.log`

3. **CSV 파일**: `results/plc_response_test_YYYYMMDD_HHMMSS.csv`

---

## [메모:1] 시험 수행 방식

**50개 서로 다른 시나리오를 각 1회씩 실행**

- ✅ 50개 다른 조건 × 1회 = 총 50회
- ❌ 1개 조건 × 50회 반복 (아님)

**이유**: 다양한 운전 조건에서 시스템 성능 검증

---

## [메모:3] 통계 계산 및 판정 기준

### Q1. 평균 계산

**Python 스크립트가 자동 계산**:
```python
mean_time = np.mean(results)  # 평균
max_time = np.max(results)    # 최대
min_time = np.min(results)    # 최소
std_time = np.std(results)    # 표준편차
```

**시험원 수동 계산 불필요**

### Q2. 판정 기준

**두 기준 모두 만족 필요**:

| 기준 | 목표 | 필수 |
|------|------|------|
| 기준 1 | 평균 0.6~0.8초 | ✅ |
| 기준 2 | 최대 <1.0초 | ✅ |

**자동 판정 코드**:
```python
mean_pass = 0.6 <= mean_time <= 0.8
max_pass = max_time < 1.0
final_pass = mean_pass and max_pass  # 둘 다 만족
```

---

## [메모:16] 측정 구간 상세

### Q1. PLC 데이터 생성 시점?

**아니오**. 측정 구간:
- **시작**: Xavier NX에서 Modbus Write 전송 시점
- **종료**: Xavier NX에서 VFD 완료 응답 수신 시점

### Q2. HMI 데이터 생성?

**아니오**. HMI는 데이터 표시만 수행 (생성 안 함)

### Q3. HMI 갱신 포함?

**아니오**. HMI 갱신은 **시험 항목 3**에서 별도 측정

---

## 시험 실행 방법

```bash
# 시험 실행
python tests/test_stage2.py

# 예상 소요 시간: 30분
```

**결과 확인**:
1. 화면 출력 → 실시간 진행 상황
2. 로그 파일 → 상세 이벤트 기록
3. CSV 파일 → Excel 분석 가능

---

## 핵심 요약

| 항목 | 내용 |
|------|------|
| **측정 대상** | AI 계산 완료(t1) → VFD 변경 완료(t2) |
| **측정 방법** | Python `time.perf_counter()` 자동 측정 |
| **시험 횟수** | 50개 시나리오 × 1회 = 50회 |
| **자동화** | 데이터 생성, 측정, 통계, 판정 모두 자동 |
| **출력** | 화면 + 로그 + CSV |
| **적합 기준** | (평균 0.6~0.8초) AND (최대 <1.0초) |
| **시험원 작업** | 스크립트 실행만 (수동 계산 불필요) |
