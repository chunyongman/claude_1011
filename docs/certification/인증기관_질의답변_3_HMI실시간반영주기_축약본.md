# 인증기관 질의 답변서 - 3. HMI 실시간 반영 주기 (축약본)

**시험 대상**: AI based Energy Saving System (V1.0)
**측정 대상**: PLC 데이터 변경 → HMI 화면 갱신 시간
**측정 시간**: 60초 연속 측정 (약 30회)
**적합 기준**: 평균 1.0~1.2초, 1.0초 이상 비율 ≥95%, CPU <20%

---

## [메모:16] PLC 데이터 생성 및 HMI 갱신 타이밍

### Q1. PLC 데이터 생성 방식

**PLC는 2초 주기로 자동 갱신**

```python
# src/communication/modbus_client.py
class ModbusTCPClient:
    def __init__(self):
        self.cycle_time = 2.0  # PLC 스캔 사이클: 2초

    def run_plc_scan_cycle(self):
        while self.running:
            current_time = time.time()

            if current_time - self.last_update_time >= 2.0:
                # 센서 데이터 갱신 (온도 ±0.5°C, 압력 ±0.05bar)
                self._update_sensor_data()

                # 타임스탬프 기록
                self.last_data_timestamp = time.perf_counter()

                self.last_update_time = current_time
```

### Q2. HMI 갱신 주기

**Streamlit의 자동 갱신 기능 사용**

```python
# src/hmi/dashboard.py
def main():
    # 시스템 매니저에서 최신 데이터 가져오기
    system_manager = get_system_manager_instance()
    current_state = system_manager.get_current_state()

    # 화면 렌더링 (PLC 2초마다 새 데이터)
    render_sensor_panel(current_state.sensor_data)
    render_control_panel(current_state.control_output)
    render_performance_panel(current_state.performance_stats)
```

### Q3. 측정 시점

**t1 (PLC 데이터 변경 완료) → t2 (HMI 화면 렌더링 완료)**

```python
def measure_hmi_refresh_cycle():
    # t1: PLC 데이터 변경 완료 시점
    plc_client.update_sensor_data()
    t1 = plc_client.get_last_update_timestamp()

    # HMI 데이터 읽기 및 화면 갱신
    sensor_data = plc_client.read_all_sensors()
    render_dashboard(sensor_data)

    # t2: HMI 화면 렌더링 완료 시점
    t2 = time.perf_counter()

    refresh_time = t2 - t1  # 갱신 시간
```

**타이밍 다이어그램**:
```
PLC:    [데이터 갱신] ──(150ms)──> [완료]
         ↑ 2초 주기                 ↑ t1

HMI:                        [데이터 읽기] ──(300ms)──> [렌더링] ──(800ms)──> [완료]
                                                                              ↑ t2

측정:                                  |<────── 약 1.1초 ──────>|
```

---

## [메모:9] 측정 시작 시점 명확화

**질문**: 해당 시점이 HMI에서 데이터를 수신받아 화면에 출력하도록 명령한 시점인 것일까요?

**답변**: 아니오, **PLC가 데이터를 갱신 완료한 시점**입니다.

**측정 시작점 (t1)**:
- ✅ PLC가 센서 데이터 갱신을 완료한 시점
- ❌ HMI가 화면 출력 명령을 보낸 시점 (아님)

**측정 종료점 (t2)**:
- ✅ HMI가 화면 렌더링을 완료한 시점

**데이터 흐름**:
```
PLC: [센서 읽기] → [데이터 갱신 완료] ← t1 (측정 시작)
                        ↓
HMI:              [데이터 수신] → [화면 렌더링] → [완료] ← t2 (측정 종료)
```

**측정 구간**: PLC 데이터 갱신 완료 → HMI 화면 렌더링 완료

**정리**: HMI의 "명령" 시점이 아니라, PLC의 "데이터 준비 완료" 시점부터 측정

---

## [메모:8] 추가 검증 기준

### Q1. 1.0초 이상 비율

**60초 동안 측정한 값 중 1.0초 이상인 비율**

```python
def calculate_pass_rate(refresh_times, threshold=1.0):
    above_threshold = sum(1 for t in refresh_times if t >= threshold)
    total = len(refresh_times)
    pass_rate = (above_threshold / total) * 100
    return pass_rate

# 예시: 30회 중 29회가 1.0초 이상 → 96.67%
```

**기준**: ≥95% (최대 1-2회만 1.0초 미만 허용)

### Q2. 최대 반영 시간

**예, 최대값과 최소값 모두 기록**

```python
def analyze_refresh_statistics(refresh_times):
    avg_time = np.mean(refresh_times)
    min_time = np.min(refresh_times)
    max_time = np.max(refresh_times)
    std_time = np.std(refresh_times)

    # 1.0초 이상 비율
    pass_rate = calculate_pass_rate(refresh_times, 1.0)

    print(f"평균: {avg_time:.3f}초 (기준: 1.0-1.2초)")
    print(f"최소: {min_time:.3f}초")
    print(f"최대: {max_time:.3f}초")
    print(f"1.0초 이상 비율: {pass_rate:.2f}% (기준: ≥95%)")
```

### Q3. CPU 사용률 측정

**`psutil` 라이브러리로 HMI 프로세스 CPU 사용률 측정**

```python
import psutil

def monitor_cpu_usage(duration=60):
    process = psutil.Process(os.getpid())
    cpu_samples = []

    start_time = time.time()

    while time.time() - start_time < duration:
        cpu_percent = process.cpu_percent(interval=1.0)
        cpu_samples.append(cpu_percent)

    avg_cpu = np.mean(cpu_samples)
    max_cpu = np.max(cpu_samples)

    print(f"평균 CPU: {avg_cpu:.1f}%")
    print(f"최대 CPU: {max_cpu:.1f}%")
    print(f"기준: <20.0%")

    return avg_cpu
```

**통합 측정** (멀티스레드):
```python
# 동시 측정: HMI 갱신 시간 + CPU 사용률
def test_hmi_comprehensive():
    refresh_times = []
    cpu_samples = []

    # 스레드 1: HMI 갱신 시간 측정
    def measure_refresh_thread():
        # 60초 동안 갱신 시간 측정
        pass

    # 스레드 2: CPU 사용률 측정
    def measure_cpu_thread():
        # 60초 동안 CPU 측정
        pass

    # 동시 실행
    threading.Thread(target=measure_refresh_thread).start()
    threading.Thread(target=measure_cpu_thread).start()
```

---

## [메모:17] 계산 자동화

**Q1 & Q2: 모든 계산과 판정 자동화**

```python
def automated_analysis_and_judgment(refresh_times, cpu_samples):
    # 1. 갱신 시간 통계 자동 계산
    avg_refresh = np.mean(refresh_times)
    min_refresh = np.min(refresh_times)
    max_refresh = np.max(refresh_times)
    std_refresh = np.std(refresh_times)

    # 2. 1.0초 이상 비율 자동 계산
    above_1s_count = sum(1 for t in refresh_times if t >= 1.0)
    total_count = len(refresh_times)
    pass_rate = (above_1s_count / total_count) * 100

    # 3. CPU 사용률 통계 자동 계산
    avg_cpu = np.mean(cpu_samples)
    max_cpu = np.max(cpu_samples)

    # 4. 합격 기준 자동 판정
    criterion1_pass = 1.0 <= avg_refresh <= 1.2  # 평균 1.0-1.2초
    criterion2_pass = pass_rate >= 95.0           # 1.0초 이상 비율 ≥95%
    criterion3_pass = avg_cpu < 20.0              # CPU <20%

    final_pass = criterion1_pass and criterion2_pass and criterion3_pass

    # 5. 결과 출력 및 CSV 저장
    print(f"평균 시간: {avg_refresh:.3f}초 {'✓' if criterion1_pass else '✗'}")
    print(f"1.0초 이상 비율: {pass_rate:.2f}% {'✓' if criterion2_pass else '✗'}")
    print(f"CPU 사용률: {avg_cpu:.1f}% {'✓' if criterion3_pass else '✗'}")
    print(f"최종 판정: {'✓✓✓ 합격 ✓✓✓' if final_pass else '✗✗✗ 불합격 ✗✗✗'}")

    # CSV 자동 저장
    df = pd.DataFrame({
        '측정번호': range(1, len(refresh_times) + 1),
        '갱신시간(초)': refresh_times,
        '1.0초이상': [t >= 1.0 for t in refresh_times]
    })
    df.to_csv(f'test_results_hmi_refresh_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

    return {'pass': final_pass}
```

**출력 예시**:
```
============================================================
자동 통계 분석 및 합격 판정 결과
============================================================

[1. 갱신 시간 통계]
  총 측정 횟수: 30회
  평균: 1.087초
  최소: 0.982초
  최대: 1.156초
  표준편차: 0.045초

[2. 1.0초 이상 비율]
  1.0초 이상: 29회
  1.0초 미만: 1회
  비율: 96.67%

[3. CPU 사용률]
  평균: 15.3%
  최대: 18.7%

============================================================
[합격 기준 판정]
============================================================
  기준 1 - 평균 시간 (1.0-1.2초): 1.087초 ✓ 합격
  기준 2 - 1.0초 이상 비율 (≥95%): 96.67% ✓ 합격
  기준 3 - CPU 사용률 (<20%): 15.3% ✓ 합격

[최종 판정]
============================================================
  ✓✓✓  모든 기준 만족 - 합격  ✓✓✓
============================================================

[결과 파일]
  상세 데이터: test_results_hmi_refresh_20251210_143022.csv
  통계 요약: test_summary_hmi_refresh_20251210_143022.csv
```

---

## [메모:10] 60초 연속 측정 의미

**"60초 동안 연속 측정" = 60초 동안 중단 없이 계속 측정**

```python
def continuous_measurement_60_seconds():
    print("60초 연속 측정 시작...")
    print("- PLC는 2초마다 자동으로 데이터 갱신")
    print("- 예상 측정 횟수: 약 30회 (60초 ÷ 2초)")

    start_time = time.time()
    refresh_times = []

    # 60초 동안 반복 (중단 없음)
    while time.time() - start_time < 60.0:
        plc_client.wait_for_next_update()  # 2초마다

        t1 = plc_client.get_last_update_timestamp()
        sensor_data = plc_client.read_all_sensors()
        hmi_dashboard.update_display(sensor_data)
        t2 = time.perf_counter()

        refresh_time = t2 - t1
        refresh_times.append(refresh_time)

        elapsed = time.time() - start_time
        print(f"  [{elapsed:5.1f}s] 측정 #{len(refresh_times)}: {refresh_time:.3f}초")

    print(f"측정 완료: 총 {len(refresh_times)}회")
```

**출력 예시**:
```
60초 연속 측정 시작...
- PLC는 2초마다 자동으로 데이터 갱신
- 예상 측정 횟수: 약 30회 (60초 ÷ 2초)

  [  2.0s] 측정 #1: 1.085초
  [  4.0s] 측정 #2: 1.092초
  [  6.1s] 측정 #3: 1.078초
  ...
  [ 58.1s] 측정 #29: 1.082초
  [ 60.1s] 측정 #30: 1.091초

측정 완료: 총 30회
```

**타임라인**:
```
시간축(초): 0────2────4────6────8────10───...───56───58───60

PLC 갱신:   ●────●────●────●────●────●─...──●────●────●
            ↓    ↓    ↓    ↓    ↓    ↓      ↓    ↓    ↓
HMI 측정:   1    2    3    4    5    6  ... 28   29   30

            |<──────────── 60초 연속 측정 ────────────>|
```

**정리**:
- 60초 동안 중단 없이 계속 측정
- PLC 2초 주기로 약 30회 자동 측정
- 실제 운영 환경 그대로 반영

---

## 시험 실행 방법

```bash
# 시험 실행
python tests/test_hmi_realtime_refresh.py

# 예상 소요 시간: 60초
```

**결과 확인**:
1. 화면 출력 → 실시간 측정 진행
2. 로그 파일 → `logs/hmi_refresh_test_YYYYMMDD_HHMMSS.log`
3. CSV 파일 → `test_results_hmi_refresh_YYYYMMDD_HHMMSS.csv`

---

## 핵심 요약

| 항목 | 내용 |
|------|------|
| **측정 대상** | PLC 데이터 변경(t1) → HMI 화면 갱신(t2) |
| **측정 시간** | 60초 연속 (약 30회 측정) |
| **PLC 주기** | 2초마다 자동 갱신 |
| **측정 방법** | Python `time.perf_counter()` 자동 측정 |
| **자동화** | 측정, 통계, CPU 모니터링, 판정 모두 자동 |
| **출력** | 화면 + 로그 + CSV |
| **적합 기준** | (평균 1.0~1.2초) AND (1.0초 이상 비율 ≥95%) AND (CPU <20%) |
| **사용자 조작** | 없음 (완전 자동) |
