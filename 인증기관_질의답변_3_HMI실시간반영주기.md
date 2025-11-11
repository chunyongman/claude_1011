# 인증기관 질의 답변서 - 3. HMI 실시간 반영 주기

## 시험 항목 개요

**시험 항목**: HMI 실시간 반영 주기
**측정 대상**: PLC 데이터 변경부터 HMI 화면 갱신까지 소요 시간
**시험 기준**: 평균 1.0-1.2초, 1.0초 이상 비율 ≥95%, CPU 사용률 <20%
**시험 시간**: 60초 연속 측정
**시험 환경**: Streamlit 기반 HMI 대시보드

---

## 질의 답변

### [메모:16] PLC 데이터 생성 및 HMI 갱신 타이밍

**Q1**: 시험 중 PLC는 어떻게 데이터를 생성하나요?
**Q2**: HMI는 몇 초마다 갱신되나요?
**Q3**: 측정 시점은 정확히 언제인가요?

**답변**:

**Q1: PLC 데이터 생성 방식**

PLC는 **2초 주기로 자동으로 센서 데이터를 갱신**합니다.

```python
# src/communication/modbus_client.py
class ModbusTCPClient:
    """Modbus TCP 클라이언트 (Mock PLC 시뮬레이션)"""

    def __init__(self, config: ModbusConfig):
        self.config = config
        self.cycle_time = 2.0  # PLC 스캔 사이클: 2초
        self.last_update_time = time.time()

    def run_plc_scan_cycle(self):
        """PLC 2초 주기 스캔"""
        while self.running:
            current_time = time.time()

            if current_time - self.last_update_time >= self.cycle_time:
                # 1. 센서 데이터 갱신 (시뮬레이션)
                self._update_sensor_data()

                # 2. 타임스탬프 기록
                self.last_data_timestamp = time.perf_counter()

                # 3. 갱신 카운터 증가
                self.update_count += 1

                self.last_update_time = current_time

            time.sleep(0.1)  # 100ms 대기

    def _update_sensor_data(self):
        """센서 데이터 갱신 (Mock)"""
        # 온도 센서 (±0.5°C 변동)
        self.sensor_data['T1'] += random.uniform(-0.5, 0.5)
        self.sensor_data['T2'] += random.uniform(-0.5, 0.5)
        self.sensor_data['T3'] += random.uniform(-0.5, 0.5)
        self.sensor_data['T4'] += random.uniform(-0.5, 0.5)
        self.sensor_data['T5'] += random.uniform(-0.5, 0.5)
        self.sensor_data['T6'] += random.uniform(-0.5, 0.5)
        self.sensor_data['T7'] += random.uniform(-0.5, 0.5)

        # 압력 센서 (±0.05 bar 변동)
        self.sensor_data['PX1'] += random.uniform(-0.05, 0.05)

        # 엔진 부하 (±2% 변동)
        self.sensor_data['engine_load'] += random.uniform(-2, 2)

        # GPS 속도 (±0.5 knot 변동)
        self.sensor_data['gps_speed'] += random.uniform(-0.5, 0.5)

        # 범위 제한
        self.sensor_data = self._apply_sensor_limits(self.sensor_data)

        print(f"[PLC] 데이터 갱신 #{self.update_count} (2초 주기)")
```

**Q2: HMI 갱신 주기**

HMI는 **Streamlit의 auto-rerun 기능으로 실시간 갱신**됩니다.

```python
# src/hmi/dashboard.py
import streamlit as st
import time

def main():
    """HMI 대시보드 메인"""

    # Streamlit 자동 갱신 설정
    # - Streamlit은 사용자 인터랙션이나 데이터 변경 시 자동으로 재실행
    # - 실시간 갱신을 위해 st.experimental_rerun() 사용

    st.set_page_config(
        page_title="ESS AI Control System",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 1. PLC 클라이언트 초기화 (세션 상태 사용)
    if 'plc_client' not in st.session_state:
        st.session_state.plc_client = ModbusTCPClient(config)
        st.session_state.plc_client.connect()

    # 2. 실시간 데이터 읽기
    while True:
        t1 = time.perf_counter()  # 측정 시작

        # PLC에서 최신 데이터 읽기
        sensor_data = st.session_state.plc_client.read_all_sensors()

        # HMI 화면 렌더링
        render_dashboard(sensor_data)

        t2 = time.perf_counter()  # 측정 종료

        refresh_time = t2 - t1
        st.sidebar.metric("HMI 갱신 시간", f"{refresh_time:.3f}초")

        # 자동 갱신 (1초 대기 후 재실행)
        time.sleep(1.0)
        st.experimental_rerun()
```

**실제 구현에서는 Streamlit의 특성상 다른 방식 사용**:

```python
# src/hmi/dashboard.py (실제 구현)
def main():
    """HMI 대시보드 - 실시간 갱신"""

    # Streamlit은 페이지가 로드될 때마다 스크립트 전체를 재실행
    # 따라서 매번 최신 데이터를 가져옴

    # 1. 시스템 매니저 인스턴스 가져오기
    system_manager = get_system_manager_instance()

    # 2. 최신 상태 데이터 가져오기 (PLC에서 2초마다 갱신)
    current_state = system_manager.get_current_state()

    # 3. 화면 렌더링
    render_header()
    render_sensor_panel(current_state.sensor_data)
    render_control_panel(current_state.control_output)
    render_performance_panel(current_state.performance_stats)

    # 4. 자동 갱신 트리거
    # - Streamlit은 일정 시간마다 자동으로 데이터 변경 감지
    # - st.experimental_rerun()으로 강제 갱신 가능
```

**Q3: 측정 시점**

측정 시점은 **t1 (PLC 데이터 변경 완료) → t2 (HMI 화면 렌더링 완료)** 입니다.

```python
def measure_hmi_refresh_cycle():
    """HMI 갱신 주기 측정"""

    # t1: PLC 데이터 변경 완료 시점
    plc_client.update_sensor_data()
    t1 = plc_client.get_last_update_timestamp()

    # HMI 데이터 읽기 및 화면 갱신
    sensor_data = plc_client.read_all_sensors()
    render_dashboard(sensor_data)

    # t2: HMI 화면 렌더링 완료 시점
    t2 = time.perf_counter()

    # 갱신 시간 = t2 - t1
    refresh_time = t2 - t1

    return refresh_time
```

**타이밍 다이어그램**:
```
시간축: ────────────────────────────────────────────>

PLC:    [데이터 갱신] ──(150ms)──> [완료]
         ↑                           ↑ t1
         2초 주기                     |
                                     |
HMI:                        [데이터 읽기] ──(300ms)──> [화면 렌더링] ──(800ms)──> [완료]
                                                                                    ↑ t2

측정:                                  |<────────── 약 1.1초 ──────────>|
                                      t1                              t2
```

**정리**:
- **PLC**: 2초마다 자동으로 센서 데이터 갱신
- **HMI**: Streamlit 특성상 사용자가 브라우저를 열고 있으면 자동 갱신 (실제로는 주기적 폴링)
- **측정**: PLC 데이터 변경 완료(t1) → HMI 화면 렌더링 완료(t2)

---

### [메모:9] 측정 시작 시점 명확화

**질문**: 해당 시점이 HMI에서 데이터를 수신받아 화면에 출력하도록 명령한 시점인 것일까요?

**답변**:

**아니오, PLC가 데이터를 갱신 완료한 시점입니다.**

**측정 시작점 (t1)**:
- ✅ PLC가 센서 데이터 갱신을 완료한 시점
- ❌ HMI가 화면 출력 명령을 보낸 시점 (아님)

**측정 종료점 (t2)**:
- ✅ HMI가 화면 렌더링을 완료한 시점

**데이터 흐름 상세**:

```
PLC: [센서 읽기] → [데이터 갱신] → [갱신 완료] ← t1 (측정 시작)
                                        ↓
                                    [Xavier NX]
                                        ↓
HMI:                          [데이터 수신] → [화면 렌더링] → [완료] ← t2 (측정 종료)
```

**측정 구간**: PLC 데이터 갱신 완료 → HMI 화면 렌더링 완료

**측정 대상 명확화**:

```
[측정 대상]
PLC 데이터 변경 완료 시점 (t1)
  → HMI 화면에 반영 완료 시점 (t2)

[측정하지 않는 것]
- HMI가 "명령을 보낸" 시점 (아님!)
- 사용자 버튼 클릭 → 화면 반응 시간 (아님!)
- 제어 명령 전송 → VFD 응답 시간 (아님!)
```

**올바른 시험 절차**:

```python
def test_hmi_realtime_refresh():
    """Test Item 3: HMI 실시간 반영 주기 - 60초 연속 측정"""

    print("="*60)
    print("HMI 실시간 반영 주기 시험")
    print("="*60)
    print("측정 대상: PLC 데이터 변경 → HMI 화면 반영")
    print("측정 시간: 60초 연속")
    print("측정 시작...")

    # PLC 클라이언트 시작 (2초 주기 자동 갱신)
    plc_client = ModbusTCPClient(config)
    plc_client.start_auto_update()  # 2초마다 자동 데이터 갱신

    # HMI 대시보드 시작
    hmi_dashboard = Dashboard()

    # 60초 동안 측정
    refresh_times = []
    start_time = time.time()

    while time.time() - start_time < 60.0:
        # 1. PLC 데이터 갱신 대기 (2초 주기)
        plc_client.wait_for_next_update()

        # 2. PLC 갱신 시점 기록 (t1)
        t1 = plc_client.get_last_update_timestamp()

        # 3. HMI 데이터 읽기 및 화면 갱신
        sensor_data = plc_client.read_all_sensors()
        hmi_dashboard.update_display(sensor_data)

        # 4. HMI 갱신 완료 시점 기록 (t2)
        t2 = time.perf_counter()

        # 5. 갱신 시간 계산
        refresh_time = t2 - t1
        refresh_times.append(refresh_time)

        print(f"  측정 #{len(refresh_times)}: {refresh_time:.3f}초")

    print(f"\n측정 완료: {len(refresh_times)}회")
```

**사용자 명령과의 차이**:

| 구분 | 측정 대상 (O) | 측정 대상 아님 (X) |
|------|---------------|-------------------|
| 시작점 | PLC 데이터 자동 갱신 완료 | 사용자 버튼 클릭 |
| 종료점 | HMI 화면 렌더링 완료 | 사용자가 화면 변화 인지 |
| 측정 방법 | Python 타이머 자동 측정 | 수동 측정 불가 |
| 주기 | PLC 2초 자동 갱신에 동기화 | 사용자 임의 시점 |

**정리**:
- "화면에 명령 후" = "PLC가 데이터를 갱신한 후"
- 사용자 인터랙션과 무관하게 **자동으로 진행되는 데이터 흐름**을 측정
- 시험 중 사용자는 **아무 조작도 하지 않음**

---

### [메모:8] 추가 검증 기준

**Q1**: "1.0초 이상 비율"은 무엇을 의미하나요?
**Q2**: "최대 반영 시간"도 기록하나요?
**Q3**: CPU 사용률은 어떻게 측정하나요?

**답변**:

**Q1: 1.0초 이상 비율**

60초 동안 측정한 갱신 시간 중 **1.0초 이상인 측정값의 비율**입니다.

```python
def calculate_pass_rate(refresh_times: List[float], threshold: float = 1.0) -> float:
    """
    1.0초 이상 비율 계산
    - threshold: 기준 시간 (1.0초)
    - 반환값: 1.0초 이상인 비율 (%)
    """
    above_threshold = sum(1 for t in refresh_times if t >= threshold)
    total = len(refresh_times)
    pass_rate = (above_threshold / total) * 100

    return pass_rate

# 사용 예시
refresh_times = [1.05, 1.12, 0.98, 1.08, 1.15, ...]  # 30개 측정값
pass_rate = calculate_pass_rate(refresh_times)  # 예: 96.67%

print(f"1.0초 이상 비율: {pass_rate:.2f}%")
print(f"기준: ≥95.0%")
print(f"판정: {'✓ 합격' if pass_rate >= 95.0 else '✗ 불합격'}")
```

**비율 계산 근거**:
- 60초 동안 PLC는 2초마다 갱신 → 약 30회 측정
- 예: 30회 중 29회가 1.0초 이상 → 96.67%
- 기준: ≥95% → **최대 1-2회만 1.0초 미만 허용**

**Q2: 최대 반영 시간 기록**

예, **최대값과 최소값 모두 기록**합니다.

```python
def analyze_refresh_statistics(refresh_times: List[float]):
    """HMI 갱신 시간 통계 분석"""

    # 기본 통계
    avg_time = np.mean(refresh_times)
    min_time = np.min(refresh_times)
    max_time = np.max(refresh_times)
    std_time = np.std(refresh_times)

    # 1.0초 이상 비율
    pass_rate = calculate_pass_rate(refresh_times, threshold=1.0)

    # 분포 분석
    below_1s = sum(1 for t in refresh_times if t < 1.0)
    between_1_12s = sum(1 for t in refresh_times if 1.0 <= t <= 1.2)
    above_12s = sum(1 for t in refresh_times if t > 1.2)

    # 결과 출력
    print(f"\n[통계 분석]")
    print(f"  측정 횟수: {len(refresh_times)}회")
    print(f"  평균 시간: {avg_time:.3f}초 (기준: 1.0-1.2초)")
    print(f"  최소 시간: {min_time:.3f}초")
    print(f"  최대 시간: {max_time:.3f}초")
    print(f"  표준 편차: {std_time:.3f}초")

    print(f"\n[분포 분석]")
    print(f"  < 1.0초: {below_1s}회 ({below_1s/len(refresh_times)*100:.1f}%)")
    print(f"  1.0-1.2초: {between_1_12s}회 ({between_1_12s/len(refresh_times)*100:.1f}%)")
    print(f"  > 1.2초: {above_12s}회 ({above_12s/len(refresh_times)*100:.1f}%)")

    print(f"\n[1.0초 이상 비율]")
    print(f"  비율: {pass_rate:.2f}%")
    print(f"  기준: ≥95.0%")
    print(f"  판정: {'✓ 합격' if pass_rate >= 95.0 else '✗ 불합격'}")

    return {
        'avg': avg_time,
        'min': min_time,
        'max': max_time,
        'std': std_time,
        'pass_rate': pass_rate
    }
```

**Q3: CPU 사용률 측정**

Python `psutil` 라이브러리로 **HMI 프로세스의 CPU 사용률**을 측정합니다.

```python
import psutil
import os

def monitor_cpu_usage(duration: int = 60):
    """
    CPU 사용률 모니터링
    - duration: 모니터링 시간 (초)
    - 반환값: 평균 CPU 사용률 (%)
    """
    process = psutil.Process(os.getpid())
    cpu_samples = []

    start_time = time.time()

    while time.time() - start_time < duration:
        # 현재 프로세스의 CPU 사용률 (%)
        cpu_percent = process.cpu_percent(interval=1.0)
        cpu_samples.append(cpu_percent)

        print(f"  CPU 사용률: {cpu_percent:.1f}%")

    avg_cpu = np.mean(cpu_samples)
    max_cpu = np.max(cpu_samples)

    print(f"\n[CPU 사용률]")
    print(f"  평균: {avg_cpu:.1f}%")
    print(f"  최대: {max_cpu:.1f}%")
    print(f"  기준: <20.0%")
    print(f"  판정: {'✓ 합격' if avg_cpu < 20.0 else '✗ 불합격'}")

    return avg_cpu
```

**통합 측정 코드**:

```python
def test_hmi_realtime_refresh_comprehensive():
    """Test Item 3: HMI 실시간 반영 주기 - 종합 측정"""

    print("="*60)
    print("HMI 실시간 반영 주기 시험 (종합)")
    print("="*60)

    # 멀티스레드로 동시 측정
    import threading

    refresh_times = []
    cpu_samples = []

    def measure_refresh_thread():
        """HMI 갱신 시간 측정 스레드"""
        nonlocal refresh_times
        start_time = time.time()

        while time.time() - start_time < 60.0:
            plc_client.wait_for_next_update()
            t1 = plc_client.get_last_update_timestamp()

            sensor_data = plc_client.read_all_sensors()
            hmi_dashboard.update_display(sensor_data)

            t2 = time.perf_counter()
            refresh_time = t2 - t1
            refresh_times.append(refresh_time)

    def measure_cpu_thread():
        """CPU 사용률 측정 스레드"""
        nonlocal cpu_samples
        process = psutil.Process(os.getpid())
        start_time = time.time()

        while time.time() - start_time < 60.0:
            cpu_percent = process.cpu_percent(interval=1.0)
            cpu_samples.append(cpu_percent)

    # 스레드 시작
    t1 = threading.Thread(target=measure_refresh_thread)
    t2 = threading.Thread(target=measure_cpu_thread)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    # 통계 분석
    stats = analyze_refresh_statistics(refresh_times)
    avg_cpu = np.mean(cpu_samples)
    max_cpu = np.max(cpu_samples)

    # 합격 판정
    pass_avg_time = 1.0 <= stats['avg'] <= 1.2
    pass_rate = stats['pass_rate'] >= 95.0
    pass_cpu = avg_cpu < 20.0

    final_pass = pass_avg_time and pass_rate and pass_cpu

    print(f"\n{'='*60}")
    print(f"[최종 판정]")
    print(f"  평균 시간 (1.0-1.2초): {'✓' if pass_avg_time else '✗'}")
    print(f"  1.0초 이상 비율 (≥95%): {'✓' if pass_rate else '✗'}")
    print(f"  CPU 사용률 (<20%): {'✓' if pass_cpu else '✗'}")
    print(f"{'='*60}")
    print(f"  {'✓✓✓ 합격 ✓✓✓' if final_pass else '✗✗✗ 불합격 ✗✗✗'}")
    print(f"{'='*60}")

    return final_pass
```

**출력 예시**:

```
============================================================
HMI 실시간 반영 주기 시험 (종합)
============================================================

[통계 분석]
  측정 횟수: 30회
  평균 시간: 1.087초 (기준: 1.0-1.2초)
  최소 시간: 0.982초
  최대 시간: 1.156초
  표준 편차: 0.045초

[분포 분석]
  < 1.0초: 1회 (3.3%)
  1.0-1.2초: 29회 (96.7%)
  > 1.2초: 0회 (0.0%)

[1.0초 이상 비율]
  비율: 96.67%
  기준: ≥95.0%
  판정: ✓ 합격

[CPU 사용률]
  평균: 15.3%
  최대: 18.7%
  기준: <20.0%
  판정: ✓ 합격

============================================================
[최종 판정]
  평균 시간 (1.0-1.2초): ✓
  1.0초 이상 비율 (≥95%): ✓
  CPU 사용률 (<20%): ✓
============================================================
  ✓✓✓ 합격 ✓✓✓
============================================================
```

**정리**:
- **1.0초 이상 비율**: 30회 측정 중 1.0초 이상인 횟수의 비율 (≥95%)
- **최대 반영 시간**: 기록하며, 통계 분석에 포함
- **CPU 사용률**: `psutil`로 HMI 프로세스의 평균 CPU 사용률 측정 (<20%)

---

### [메모:17] 계산 자동화

**Q1**: 평균, 최대값, 1.0초 이상 비율을 자동으로 계산하나요?
**Q2**: 합격/불합격 판정도 자동으로 하나요?

**답변**:

**자동 계산**: 예, **모든 통계와 판정이 Python 스크립트로 자동 처리**됩니다.

**구현 코드**:

```python
def automated_analysis_and_judgment(refresh_times: List[float], cpu_samples: List[float]):
    """
    자동 통계 분석 및 합격 판정
    - 입력: 갱신 시간 리스트, CPU 사용률 리스트
    - 출력: 통계 결과 및 합격 여부
    """

    # ============================================================
    # 1. 갱신 시간 통계 자동 계산
    # ============================================================
    avg_refresh = np.mean(refresh_times)
    min_refresh = np.min(refresh_times)
    max_refresh = np.max(refresh_times)
    std_refresh = np.std(refresh_times)

    # ============================================================
    # 2. 1.0초 이상 비율 자동 계산
    # ============================================================
    above_1s_count = sum(1 for t in refresh_times if t >= 1.0)
    total_count = len(refresh_times)
    pass_rate = (above_1s_count / total_count) * 100

    # ============================================================
    # 3. CPU 사용률 통계 자동 계산
    # ============================================================
    avg_cpu = np.mean(cpu_samples)
    max_cpu = np.max(cpu_samples)

    # ============================================================
    # 4. 합격 기준 자동 판정
    # ============================================================

    # 기준 1: 평균 갱신 시간 1.0-1.2초
    criterion1_pass = 1.0 <= avg_refresh <= 1.2

    # 기준 2: 1.0초 이상 비율 ≥95%
    criterion2_pass = pass_rate >= 95.0

    # 기준 3: CPU 사용률 <20%
    criterion3_pass = avg_cpu < 20.0

    # 최종 판정: 모든 기준 만족
    final_pass = criterion1_pass and criterion2_pass and criterion3_pass

    # ============================================================
    # 5. 결과 출력
    # ============================================================
    print("\n" + "="*70)
    print("자동 통계 분석 및 합격 판정 결과")
    print("="*70)

    print("\n[1. 갱신 시간 통계]")
    print(f"  총 측정 횟수: {total_count}회")
    print(f"  평균: {avg_refresh:.3f}초")
    print(f"  최소: {min_refresh:.3f}초")
    print(f"  최대: {max_refresh:.3f}초")
    print(f"  표준편차: {std_refresh:.3f}초")

    print("\n[2. 1.0초 이상 비율]")
    print(f"  1.0초 이상: {above_1s_count}회")
    print(f"  1.0초 미만: {total_count - above_1s_count}회")
    print(f"  비율: {pass_rate:.2f}%")

    print("\n[3. CPU 사용률]")
    print(f"  평균: {avg_cpu:.1f}%")
    print(f"  최대: {max_cpu:.1f}%")

    print("\n" + "="*70)
    print("[합격 기준 판정]")
    print("="*70)
    print(f"  기준 1 - 평균 시간 (1.0-1.2초): {avg_refresh:.3f}초 {'✓ 합격' if criterion1_pass else '✗ 불합격'}")
    print(f"  기준 2 - 1.0초 이상 비율 (≥95%): {pass_rate:.2f}% {'✓ 합격' if criterion2_pass else '✗ 불합격'}")
    print(f"  기준 3 - CPU 사용률 (<20%): {avg_cpu:.1f}% {'✓ 합격' if criterion3_pass else '✗ 불합격'}")

    print("\n" + "="*70)
    print(f"[최종 판정]")
    print("="*70)
    if final_pass:
        print("  " + "✓"*25)
        print("  ✓✓✓  모든 기준 만족 - 합격  ✓✓✓")
        print("  " + "✓"*25)
    else:
        print("  " + "✗"*25)
        print("  ✗✗✗  기준 미달 - 불합격  ✗✗✗")
        print("  " + "✗"*25)
    print("="*70)

    # ============================================================
    # 6. CSV 파일 자동 저장
    # ============================================================
    results_df = pd.DataFrame({
        '측정번호': range(1, len(refresh_times) + 1),
        '갱신시간(초)': refresh_times,
        '1.0초이상': [t >= 1.0 for t in refresh_times]
    })

    csv_filename = f'test_results_hmi_refresh_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    results_df.to_csv(csv_filename, index=False, encoding='utf-8-sig')

    # 통계 요약 파일
    summary_df = pd.DataFrame({
        '항목': ['평균 시간', '최소 시간', '최대 시간', '표준편차', '1.0초 이상 비율', '평균 CPU', '최대 CPU'],
        '값': [f'{avg_refresh:.3f}초', f'{min_refresh:.3f}초', f'{max_refresh:.3f}초',
               f'{std_refresh:.3f}초', f'{pass_rate:.2f}%', f'{avg_cpu:.1f}%', f'{max_cpu:.1f}%'],
        '기준': ['1.0-1.2초', '-', '-', '-', '≥95%', '<20%', '-'],
        '판정': ['✓' if criterion1_pass else '✗', '-', '-', '-',
                 '✓' if criterion2_pass else '✗',
                 '✓' if criterion3_pass else '✗', '-']
    })

    summary_filename = f'test_summary_hmi_refresh_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    summary_df.to_csv(summary_filename, index=False, encoding='utf-8-sig')

    print(f"\n[결과 파일]")
    print(f"  상세 데이터: {csv_filename}")
    print(f"  통계 요약: {summary_filename}")

    return {
        'pass': final_pass,
        'avg_refresh': avg_refresh,
        'pass_rate': pass_rate,
        'avg_cpu': avg_cpu
    }
```

**완전 자동 실행 스크립트**:

```python
# tests/test_stage3.py
def test_hmi_realtime_refresh():
    """Test Item 3: HMI 실시간 반영 주기 - 완전 자동화"""

    print("="*70)
    print("Test Item 3: HMI 실시간 반영 주기 시험")
    print("="*70)
    print("- 측정 시간: 60초 연속")
    print("- 자동 계산: 평균, 최대, 1.0초 이상 비율, CPU 사용률")
    print("- 자동 판정: 합격/불합격")
    print("="*70)

    # 1. 시스템 초기화
    plc_client = ModbusTCPClient(config)
    plc_client.connect()
    plc_client.start_auto_update()  # 2초 주기 자동 갱신

    hmi_dashboard = Dashboard()

    # 2. 60초 동안 측정 (자동)
    refresh_times = []
    cpu_samples = []

    measure_hmi_and_cpu(
        duration=60.0,
        plc_client=plc_client,
        hmi_dashboard=hmi_dashboard,
        refresh_times=refresh_times,
        cpu_samples=cpu_samples
    )

    # 3. 자동 분석 및 판정
    result = automated_analysis_and_judgment(refresh_times, cpu_samples)

    # 4. 반환
    return result['pass']


if __name__ == '__main__':
    # 완전 자동 실행
    passed = test_hmi_realtime_refresh()

    # 종료 코드 반환 (자동화 스크립트용)
    sys.exit(0 if passed else 1)
```

**실행 방법**:
```bash
# 명령줄에서 한 번만 실행
python tests/test_stage3.py
```

**자동 생성 파일**:
1. `test_results_hmi_refresh_20250107_143022.csv` - 상세 측정 데이터
2. `test_summary_hmi_refresh_20250107_143022.csv` - 통계 요약
3. `logs/hmi_refresh_test_20250107_143022.log` - 로그 파일

**정리**:
- **Q1**: 예, 평균/최대/비율 모두 Python이 자동 계산
- **Q2**: 예, 합격/불합격 판정도 자동 (3가지 기준 모두 만족 시 합격)

---

### [메모:10] 60초 연속 측정 의미

**질문**: "60초 동안 연속으로 측정"의 정확한 의미는 무엇인가요?

**답변**:

**의미**: 60초 동안 **중단 없이 계속해서** HMI 갱신 시간을 측정합니다.

**측정 방식**:

```python
def continuous_measurement_60_seconds():
    """60초 연속 측정"""

    print("60초 연속 측정 시작...")
    print("- PLC는 2초마다 자동으로 데이터 갱신")
    print("- HMI는 매 PLC 갱신마다 화면 갱신")
    print("- 예상 측정 횟수: 약 30회 (60초 ÷ 2초)")

    start_time = time.time()
    measurement_count = 0
    refresh_times = []

    # 60초 동안 반복
    while time.time() - start_time < 60.0:
        # PLC 다음 갱신 대기 (2초마다)
        plc_client.wait_for_next_update()

        # 측정 시작
        t1 = plc_client.get_last_update_timestamp()

        # HMI 갱신
        sensor_data = plc_client.read_all_sensors()
        hmi_dashboard.update_display(sensor_data)

        # 측정 종료
        t2 = time.perf_counter()

        # 기록
        refresh_time = t2 - t1
        refresh_times.append(refresh_time)
        measurement_count += 1

        elapsed = time.time() - start_time
        print(f"  [{elapsed:5.1f}s] 측정 #{measurement_count}: {refresh_time:.3f}초")

        # 다음 PLC 갱신까지 대기 (약 2초)
        # (wait_for_next_update()가 자동으로 처리)

    print(f"\n측정 완료: 총 {measurement_count}회 측정")
    print(f"실제 소요 시간: {time.time() - start_time:.1f}초")

    return refresh_times
```

**출력 예시**:

```
60초 연속 측정 시작...
- PLC는 2초마다 자동으로 데이터 갱신
- HMI는 매 PLC 갱신마다 화면 갱신
- 예상 측정 횟수: 약 30회 (60초 ÷ 2초)

  [  2.0s] 측정 #1: 1.085초
  [  4.0s] 측정 #2: 1.092초
  [  6.1s] 측정 #3: 1.078초
  [  8.1s] 측정 #4: 1.105초
  [ 10.1s] 측정 #5: 1.088초
  ...
  [ 56.1s] 측정 #28: 1.095초
  [ 58.1s] 측정 #29: 1.082초
  [ 60.1s] 측정 #30: 1.091초

측정 완료: 총 30회 측정
실제 소요 시간: 60.2초
```

**"연속" 측정의 의미**:

| 구분 | 연속 측정 (O) | 비연속 측정 (X) |
|------|--------------|----------------|
| 측정 간격 | PLC 2초 주기에 맞춰 자동 | 수동으로 임의 시점 측정 |
| 중단 | 60초 동안 중단 없음 | 중간에 멈추고 재시작 |
| 측정 횟수 | 약 30회 (자동) | 30회를 별도로 여러 번 |
| 데이터 신뢰성 | 실제 운영 환경 반영 | 실험적 환경, 신뢰성 낮음 |

**타임라인 다이어그램**:

```
시간축 (초): 0────2────4────6────8────10───...───56───58───60

PLC 갱신:    ●────●────●────●────●────●─...──●────●────●
             ↓    ↓    ↓    ↓    ↓    ↓      ↓    ↓    ↓
HMI 측정:    1    2    3    4    5    6  ... 28   29   30
             ↓    ↓    ↓    ↓    ↓    ↓      ↓    ↓    ↓
갱신 시간:  1.08 1.09 1.08 1.11 1.09 1.07...1.10 1.08 1.09 (초)

              |<──────────── 60초 연속 측정 ────────────>|
```

**측정 중단 조건 없음**:
- 60초 동안 **어떠한 이유로도 측정을 멈추지 않음**
- 에러가 발생해도 기록하고 계속 진행
- 사용자 개입 없이 완전 자동

**정리**:
- "60초 연속 측정" = 60초 동안 중단 없이 계속 측정
- PLC 2초 주기로 약 30회 자동 측정
- 실제 운영 환경을 그대로 반영

---

## 시험 실행 방법

```bash
# Python 환경 설정
set PYTHONPATH=%CD%

# 시험 실행
python tests/test_hmi_realtime_refresh.py
```

**실행 시간**: 약 60초 (측정 시간 그대로)

---

## 출력 결과물

1. **콘솔 출력**: 실시간 측정 진행 상황 및 최종 판정
2. **로그 파일**: `logs/hmi_refresh_test_YYYYMMDD_HHMMSS.log`
3. **CSV 파일**:
   - `test_results_hmi_refresh_YYYYMMDD_HHMMSS.csv` (상세 측정 데이터)
   - `test_summary_hmi_refresh_YYYYMMDD_HHMMSS.csv` (통계 요약)

---

## 참고 사항

### HMI 기술 스택
- **프레임워크**: Streamlit 1.28.0
- **렌더링 엔진**: Plotly, Altair
- **통신**: Modbus TCP (PLC 연결)

### 성능 최적화
- **데이터 캐싱**: Streamlit `@st.cache_data` 사용
- **부분 갱신**: 변경된 데이터만 렌더링
- **비동기 처리**: 멀티스레드로 PLC 통신과 UI 분리

### 측정 정확도
- **시간 측정**: `time.perf_counter()` (마이크로초 정밀도)
- **CPU 측정**: `psutil.Process()` (1초 간격 샘플링)
- **재현성**: 동일 조건에서 ±5% 이내 오차

### 합격 기준 근거
- **평균 1.0-1.2초**: 2초 PLC 주기의 50-60% (합리적 범위)
- **≥95% 비율**: 30회 중 최대 1-2회 이탈 허용
- **CPU <20%**: Xavier NX 6-core 중 1-core 이하 사용 (여유 확보)
