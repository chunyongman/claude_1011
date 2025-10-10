# ESS AI 시스템 사용 가이드
**NVIDIA Jetson Xavier NX 기반 HMM 16K급 선박 ESS 최적화 시스템**

---

## 📚 목차
1. [시스템 개요](#시스템-개요)
2. [설치 및 환경 설정](#설치-및-환경-설정)
3. [기본 사용법](#기본-사용법)
4. [단계별 테스트 실행](#단계별-테스트-실행)
5. [시뮬레이션 모드](#시뮬레이션-모드)
6. [HMI 사용법](#hmi-사용법)
7. [데이터베이스 및 리포트](#데이터베이스-및-리포트)
8. [통합 운전](#통합-운전)
9. [문제 해결](#문제-해결)

---

## 시스템 개요

### 주요 기능
- **AI 기반 에너지 최적화**: 60Hz 고정 대비 펌프 46-52%, 팬 50-58% 절감
- **자동 온도 제어**: T5 34-36°C, T6 42-44°C 정밀 제어
- **지능형 장비 관리**: 운전시간 균등화, 예방 진단
- **GPS 기반 환경 최적화**: 열대/온대/극지 해역별 자동 조정
- **24시간 무인 운전**: 99.5% 이상 가용성 보장

### 시스템 사양
- **플랫폼**: NVIDIA Jetson Xavier NX (8GB RAM, 256GB SSD)
- **AI 모델**: Polynomial Regression (온도 예측) + Random Forest (제어 최적화)
- **통신**: Modbus TCP (PLC), Danfoss FC302 VFD
- **데이터베이스**: SQLite (6개월 데이터 150GB 이내)

---

## 설치 및 환경 설정

### 1. Python 환경 설정
```bash
# Python 3.8 이상 필요
python --version

# 필요한 패키지 설치
pip install numpy pandas scikit-learn pymodbus psutil openpyxl
```

### 2. 프로젝트 구조 확인
```
Claude-code/
├── src/                    # 소스 코드
│   ├── ai/                # AI 진화 시스템
│   ├── control/           # 제어 로직
│   ├── ml/                # 머신러닝 모델
│   ├── hmi/               # 사용자 인터페이스
│   ├── database/          # 데이터베이스
│   ├── reports/           # 리포트 생성
│   ├── simulation/        # 시뮬레이션 엔진
│   ├── integration/       # 시스템 통합
│   └── ...
├── tests/                 # 단계별 테스트
│   ├── test_stage1.py ~ test_stage12.py
│   └── ...
├── data/                  # 데이터 저장소 (자동 생성)
│   ├── ess_system.db     # SQLite 데이터베이스
│   └── backups/          # 백업 파일
└── USAGE_GUIDE.md        # 이 문서
```

### 3. 시스템 초기화 확인
```bash
# 데이터 디렉토리 생성
mkdir -p data/backups

# Stage 1 테스트로 환경 검증
python tests/test_stage1.py
```

---

## 기본 사용법

### 방법 1: 개별 모듈 사용

#### 온도 예측 (Polynomial Regression)
```python
from src.ml.temperature_predictor import TemperaturePredictor

# 예측기 초기화
predictor = TemperaturePredictor()

# 학습 데이터 준비
training_data = [
    {'engine_load': 50, 'T1': 25.0, 'pump_freq': 45, 'T5': 35.0, 'T6': 43.0},
    # ... 더 많은 데이터
]
predictor.train(training_data)

# 온도 예측
future_temps = predictor.predict(engine_load=60, T1=26.0, pump_freq=48)
print(f"예측 T5: {future_temps['T5_predicted']:.1f}°C")
print(f"예측 T6: {future_temps['T6_predicted']:.1f}°C")
```

#### 주파수 최적화 (Random Forest)
```python
from src.ml.random_forest_optimizer import RandomForestOptimizer

# 최적화기 초기화
optimizer = RandomForestOptimizer()

# 학습 (과거 운전 데이터 필요)
optimizer.train(historical_data)

# 최적 주파수 추천
current_state = {
    'T5': 35.2, 'T6': 43.5, 'engine_load': 65,
    'T1': 26.0, 'PX1': 1.8
}
optimal_freq = optimizer.optimize(current_state, mode='pump')
print(f"최적 펌프 주파수: {optimal_freq:.1f} Hz")
```

#### HMI 대시보드
```python
from src.hmi.dashboard import Dashboard

# 대시보드 초기화
dashboard = Dashboard()

# 센서 데이터 업데이트 (1초마다 자동 갱신)
sensor_data = {
    'T1': 25.5, 'T2': 45.0, 'T3': 46.0, 'T4': 45.5,
    'T5': 35.2, 'T6': 43.5, 'T7': 42.0, 'PX1': 1.8,
    'engine_load': 65.0, 'gps': {'lat': 35.1, 'lon': 129.0}
}
dashboard.update_sensor_display(sensor_data)

# 제어 모드 변경
dashboard.switch_control_mode('AI')  # 또는 '60Hz_FIXED'

# 알람 표시
dashboard.add_alarm('CRITICAL', 'PX1 압력 1.0 bar 미만')

# 에너지 절감률 표시
dashboard.update_energy_savings(pump_savings=48.5, fan_savings=53.2)
```

---

## 단계별 테스트 실행

### 전체 테스트 실행 (권장)
```bash
# Stage 1-12 전체 테스트
for i in {1..12}; do
    echo "=== Stage $i 테스트 ==="
    python tests/test_stage$i.py
done
```

### 개별 Stage 테스트

#### Stage 1: 기초 모델 및 데이터 처리
```bash
python tests/test_stage1.py
# 검증: 센서 데이터, 안전 제약조건, Modbus 통신, GPS 기본 기능
```

#### Stage 2: 핵심 제어 로직
```bash
python tests/test_stage2.py
# 검증: PID 제어, 펌프/팬 대수 제어, 에너지 절감 계산
```

#### Stage 3: AI/ML 기반 예측 및 최적화
```bash
python tests/test_stage3.py
# 검증: 온도 예측, Random Forest 최적화, 예측 제어기
```

#### Stage 4: 학습 시스템
```bash
python tests/test_stage4.py
# 검증: 배치 학습, 파라미터 튜닝, 패턴 분류, 시나리오 DB
```

#### Stage 5: 지능형 진단
```bash
python tests/test_stage5.py
# 검증: VFD 예방 진단, Edge AI/PLC 이중화, 주파수 편차 모니터링, 센서 이상 감지
```

#### Stage 6: GPS 기반 최적화
```bash
python tests/test_stage6.py
# 검증: GPS 데이터 처리, 해역별 최적화 (열대/온대/극지)
```

#### Stage 7: 통합 제어기
```bash
python tests/test_stage7.py
# 검증: 60Hz 고정/AI 제어 모드, 통합 제어 로직
```

#### Stage 8: AI 진화 시스템
```bash
python tests/test_stage8.py
# 검증: 4단계 진화 (초기 학습 → 패턴 학습 → 적응 제어 → 최적 제어)
```

#### Stage 9: HMI
```bash
python tests/test_stage9.py
# 검증: 대시보드, 알람, 운전시간 모니터링, 학습 성과 시각화
```

#### Stage 10: 시뮬레이션 및 테스트
```bash
python tests/test_stage10.py
# 검증: 물리 엔진, 어댑터 패턴, 테스트 프레임워크
```

#### Stage 11: 데이터베이스 및 리포트
```bash
python tests/test_stage11.py
# 검증: SQLite DB (7 tables), 일/주/월 리포트, 백업/복구
```

#### Stage 12: 최종 통합 검증
```bash
python tests/test_stage12.py
# 검증: 24시간 연속 운전, Xavier NX 성능, 모든 요구사항
```

---

## 시뮬레이션 모드

### 시뮬레이션 엔진 사용
```python
from src.simulation.physics_engine import PhysicsEngine
from src.adapter.sim_adapter import SimulationAdapter

# 시뮬레이션 엔진 초기화
engine = PhysicsEngine()
adapter = SimulationAdapter(engine)

# 초기 상태 설정
initial_state = {
    'T1_seawater': 25.0,
    'engine_load': 50.0,
    'pump_count': 3,
    'pump_freq': 45.0,
    'fan_count': 2,
    'fan_freq': 50.0
}
engine.set_state(initial_state)

# 시뮬레이션 실행 (1분 = 60초)
for t in range(60):
    # 제어 명령 (예: AI가 계산한 주파수)
    control = {'pump_freq': 48.0, 'fan_freq': 52.0}

    # 1초 시뮬레이션
    state = engine.simulate_step(delta_t=1.0, control=control)

    print(f"{t}초: T5={state['T5']:.1f}°C, T6={state['T6']:.1f}°C")
```

### 시나리오 기반 테스트
```python
from src.testing.test_framework import TestFramework

# 테스트 프레임워크 초기화
framework = TestFramework()

# 시나리오 1: 엔진 부하 급증
result = framework.run_scenario('load_surge', duration=300)
print(f"시나리오 결과: {result['success']}")
print(f"안전 위반: {result['safety_violations']}")

# 시나리오 2: 열대 해역 진입
result = framework.run_scenario('tropical_entry', duration=600)

# 시나리오 3: 펌프 1대 트립
result = framework.run_scenario('pump_trip', duration=180)

# 모든 시나리오 자동 실행
all_results = framework.run_all_scenarios()
```

---

## HMI 사용법

### 3가지 운전 모드

#### 1. 정상 운전 모드 (Normal)
```python
from src.hmi.hmi_state_manager import HMIStateManager

state_mgr = HMIStateManager()

# 정상 운전 모드로 전환
state_mgr.set_mode('NORMAL')

# AI 제어 활성화
state_mgr.set_control_mode('AI')

# 현재 상태 확인
status = state_mgr.get_current_state()
print(f"운전 모드: {status['mode']}")
print(f"제어 모드: {status['control_mode']}")
print(f"학습 가능: {status['learning_enabled']}")
```

#### 2. 학습 모드 (Learning)
```python
# 학습 모드로 전환 (수요일/일요일 02:00-04:00 자동)
state_mgr.set_mode('LEARNING')

# 학습 중에는 제어 변경 최소화
print(f"학습 진행 중: {state_mgr.is_learning_in_progress()}")
```

#### 3. 안전 모드 (Safety)
```python
# 안전 모드로 강제 전환 (비상시)
state_mgr.set_mode('SAFETY')

# 안전 모드에서는 60Hz 고정 운전
print(f"안전 모드 활성: {state_mgr.is_safety_mode()}")
```

### 알람 관리
```python
from src.hmi.dashboard import Dashboard

dashboard = Dashboard()

# 알람 등록 (3가지 우선순위)
dashboard.add_alarm('CRITICAL', 'PX1 압력 0.8 bar - 즉시 조치 필요')
dashboard.add_alarm('WARNING', 'T5 온도 36.5°C - 주의 관찰')
dashboard.add_alarm('INFO', 'SW 펌프 운전시간 10,000시간 도달')

# 알람 목록 조회
alarms = dashboard.get_alarms()
for alarm in alarms:
    print(f"[{alarm['priority']}] {alarm['message']} - {alarm['timestamp']}")

# 알람 확인 처리
dashboard.acknowledge_alarm(alarm_id=1)

# 알람 초기화
dashboard.clear_alarms()
```

### 실시간 모니터링
```python
import time
from src.hmi.dashboard import Dashboard

dashboard = Dashboard()

# 1초 간격 실시간 모니터링
while True:
    # 센서 데이터 수집 (실제로는 PLC에서 읽음)
    sensor_data = get_sensor_data_from_plc()

    # 대시보드 업데이트
    dashboard.update_sensor_display(sensor_data)

    # 입력조건-목표주파수 반영 상태
    reflection = dashboard.get_input_target_reflection()
    print(f"엔진부하 {reflection['engine_load']}% → "
          f"펌프 {reflection['pump_count']}대 {reflection['pump_freq']:.1f}Hz")

    # 60Hz 대비 절약률
    savings = dashboard.calculate_savings_vs_60hz(sensor_data)
    print(f"현재 절약률: 펌프 {savings['pump']:.1f}%, 팬 {savings['fan']:.1f}%")

    time.sleep(1)
```

---

## 데이터베이스 및 리포트

### 데이터베이스 사용

#### DB 초기화 및 데이터 저장
```python
from src.database.db_schema import DatabaseManager
from datetime import datetime

# DB 매니저 초기화
db = DatabaseManager(db_path='data/ess_system.db')
db.init_database()

# 센서 데이터 저장 (1분 간격)
sensor_data = {
    'timestamp': datetime.now(),
    'T1': 25.5, 'T2': 45.0, 'T3': 46.0, 'T4': 45.5,
    'T5': 35.2, 'T6': 43.5, 'T7': 42.0,
    'PX1': 1.8,
    'engine_load': 65.0,
    'gps_lat': 35.1, 'gps_lon': 129.0
}
db.insert_sensor_data(sensor_data)

# 제어 데이터 저장
control_data = {
    'timestamp': datetime.now(),
    'pump_count': 3,
    'pump_freq_avg': 48.0,
    'fan_count': 2,
    'fan_freq_avg': 52.0,
    'control_mode': 'AI'
}
db.insert_control_data(control_data)

# 알람 저장
db.insert_alarm({
    'timestamp': datetime.now(),
    'priority': 'WARNING',
    'message': 'T5 온도 36.5°C',
    'status': 'ACTIVE'
})
```

#### 데이터 조회
```python
from datetime import datetime, timedelta

# 최근 24시간 센서 데이터
end_time = datetime.now()
start_time = end_time - timedelta(hours=24)
recent_data = db.query_sensor_data(start_time, end_time)

# 성과 지표 조회
metrics = db.get_latest_performance_metrics()
print(f"에너지 절감: {metrics['energy_savings_percent']:.1f}%")
print(f"T5 정확도: {metrics['T5_accuracy_percent']:.1f}%")
print(f"T6 정확도: {metrics['T6_accuracy_percent']:.1f}%")

# VFD 건강 상태
vfd_health = db.query_vfd_health('SW_PUMP_1')
print(f"건강 등급: {vfd_health['health_grade']}")
```

#### 데이터 정리 및 백업
```python
# 6개월 이상 오래된 데이터 정리
db.cleanup_old_data()

# 백업 생성 (매일 자동 실행)
backup_path = db.backup_database()
print(f"백업 완료: {backup_path}")

# 백업 복구
db.restore_from_backup('data/backups/ess_system_20250107.db')
```

### 리포트 생성

#### 일일 리포트 (운영팀, 07:00)
```python
from src.reports.daily_report import DailyReportGenerator
from datetime import datetime

# 리포트 생성기 초기화
daily_gen = DailyReportGenerator(db)

# 어제 날짜 리포트 생성
target_date = datetime(2025, 1, 7)
report = daily_gen.generate_report(target_date)

# 텍스트 리포트 출력
text_report = daily_gen.format_text_report(report)
print(text_report)

# 주요 내용:
# - 핵심 지표: 에너지 절감률, T5/T6 정확도
# - 안전 현황: 위반, 알람, VFD 이상
# - 장비 운전시간
# - 어제 대비 변화
# - 내일 예보 (GPS 기반)
```

#### 주간 리포트 (관리팀, 월요일 09:00)
```python
from src.reports.weekly_report import WeeklyReportGenerator

weekly_gen = WeeklyReportGenerator(db)

# 지난 주 리포트 생성
report = weekly_gen.generate_report(week_start=datetime(2025, 1, 6))

text_report = weekly_gen.format_text_report(report)
print(text_report)

# 주요 내용:
# - 7일간 성과 및 안정성 점수
# - 장비 효율 순위
# - 운전시간 균등화 분석
# - 환경 적응 (열대/온대/극지)
# - 시스템 학습 개선
# - 유지보수 권장사항
```

#### 월간 리포트 (경영진, 매월 2일 10:00)
```python
from src.reports.monthly_report import MonthlyReportGenerator

monthly_gen = MonthlyReportGenerator(db)

# 지난 달 리포트 생성
report = monthly_gen.generate_report(year=2025, month=1)

text_report = monthly_gen.format_text_report(report)
print(text_report)

# 주요 내용:
# - 경영 지표: 비용 절감 (USD), 절감 전력량 (kWh)
# - ROI 분석: 연간 절감 예상, 투자 회수 기간, CO2 감축
# - 전략적 분석: 전월 대비 개선, AI 진화 단계, 12개월 전망
# - 기술적 성과: Xavier NX 활용, ML 정확도
```

---

## 통합 운전

### 전체 시스템 시작
```python
from src.integration.system_manager import SystemManager
import time

# 시스템 매니저 초기화
manager = SystemManager()

# 4단계 초기화
if manager.initialize():
    print("시스템 초기화 완료")

    # 운전 시작 (5개 독립 스레드)
    manager.start_operation()

    # 24시간 무인 운전
    try:
        while True:
            # 시스템 상태 모니터링
            status = manager.get_system_status()

            print(f"가동 시간: {status['uptime_hours']:.2f}h")
            print(f"CPU: {status['resource_usage']['cpu_percent_avg']:.1f}%")
            print(f"메모리: {status['resource_usage']['memory_gb_avg']:.2f} GB")
            print(f"오류: {status['performance']['total_errors']}건")
            print(f"가용성: {manager.get_availability():.2f}%")

            time.sleep(60)  # 1분마다 상태 확인

    except KeyboardInterrupt:
        # Graceful shutdown
        print("\n시스템 종료 시작...")
        manager.shutdown()
        print("시스템 정상 종료 완료")
else:
    print("시스템 초기화 실패")
```

### 24시간 연속 운전 테스트
```python
from src.integration.continuous_operation_test import ContinuousOperationTest

# 테스터 초기화
tester = ContinuousOperationTest(test_duration_hours=24.0)

# 실시간 24시간 테스트 (또는 accelerated=True로 24초 압축)
results = tester.run_test(accelerated=False)

# 결과 출력
tester.print_results(results)

# 핵심 성공 기준 확인:
# - 펌프 에너지 절감: 46-52%
# - 팬 에너지 절감: 50-58%
# - T5/T6 정확도: 90% 이상
# - AI 응답시간: 2초 주기 100% 준수
# - 시스템 가용성: 99.5% 이상
# - 메모리: 8GB 이하
```

### Xavier NX 성능 검증
```python
from src.integration.xavier_nx_verification import XavierNXVerification

verifier = XavierNXVerification()

# 1. ML 추론 성능 (1000회)
inference_results = verifier.verify_ml_inference_performance(num_cycles=1000)
print(f"Poly Regression: {inference_results['polynomial_regression']['avg_ms']:.2f}ms")
print(f"Random Forest: {inference_results['random_forest']['avg_ms']:.2f}ms")

# 2. 2초 주기 안정성 (60분)
cycle_results = verifier.verify_2s_cycle_stability(duration_minutes=60)
print(f"준수율: {cycle_results['deadline_compliance_percent']:.2f}%")

# 3. 주 2회 배치 학습 효과 (4주)
learning_results = verifier.verify_biweekly_learning(weeks=4)
print(f"성능 개선: +{learning_results['total_improvement']:.1f}%p")

# 4. 메모리 및 스토리지
memory_results = verifier.verify_memory_storage()
print(f"메모리: {memory_results['memory']['used_gb']:.2f} GB / 8.0 GB")
print(f"6개월 데이터: {memory_results['storage_6_months']['estimated_gb']:.2f} GB")

# 전체 결과 출력
verifier.print_verification_results(
    inference_results,
    cycle_results,
    learning_results,
    memory_results
)
```

---

## 문제 해결

### 일반적인 문제

#### 1. 모듈 import 오류
```bash
# 문제: ModuleNotFoundError: No module named 'src'
# 해결: 프로젝트 루트에서 실행하거나 PYTHONPATH 설정
export PYTHONPATH="${PYTHONPATH}:/path/to/Claude-code"
python tests/test_stage1.py

# Windows
set PYTHONPATH=%CD%
python tests/test_stage1.py
```

#### 2. 데이터베이스 오류
```python
# 문제: database is locked
# 해결: DB 연결 종료 후 재시도
from src.database.db_schema import DatabaseManager

db = DatabaseManager()
db.close()  # 명시적 종료

# 또는 컨텍스트 매니저 사용
with DatabaseManager() as db:
    data = db.query_sensor_data(start, end)
```

#### 3. 메모리 부족
```python
# 문제: 메모리 8GB 초과
# 해결: 데이터 정리 및 배치 크기 조정

# 오래된 데이터 정리
db.cleanup_old_data()

# ML 학습 배치 크기 축소
from src.ml.batch_learning import BatchLearningSystem

learning = BatchLearningSystem()
learning.train(batch_size=100)  # 기본 1000에서 축소
```

#### 4. AI 모델 예측 정확도 저하
```python
# 문제: 예측 오차 증가
# 해결: 재학습 또는 파라미터 튜닝

from src.ml.temperature_predictor import TemperaturePredictor
from src.ml.parameter_tuner import ParameterTuner

# 재학습
predictor = TemperaturePredictor()
recent_data = db.query_sensor_data(last_7_days_start, now)
predictor.train(recent_data)

# 파라미터 튜닝
tuner = ParameterTuner(predictor)
best_params = tuner.tune(validation_data)
predictor.set_parameters(best_params)
```

#### 5. 통신 장애 (PLC/VFD)
```python
# 문제: Modbus 통신 실패
# 해결: 재연결 및 백업 모드

from src.communication.modbus_client import ModbusClient

client = ModbusClient(host='192.168.1.10', port=502)

try:
    data = client.read_holding_registers(address=0, count=10)
except Exception as e:
    print(f"통신 오류: {e}")

    # 재연결 시도
    client.reconnect()

    # 백업 모드로 전환 (60Hz 고정 운전)
    from src.hmi.hmi_state_manager import HMIStateManager
    state_mgr = HMIStateManager()
    state_mgr.set_mode('SAFETY')
```

### 로그 확인
```python
# 시스템 로그 설정
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('data/system.log'),
        logging.StreamHandler()
    ]
)

# 특정 모듈 디버그 모드
logging.getLogger('src.ml').setLevel(logging.DEBUG)
logging.getLogger('src.control').setLevel(logging.DEBUG)
```

### 성능 모니터링
```python
import psutil
import os

# 현재 프로세스 리소스 확인
process = psutil.Process(os.getpid())

print(f"CPU: {process.cpu_percent(interval=1)}%")
print(f"메모리: {process.memory_info().rss / 1024 / 1024:.1f} MB")
print(f"스레드: {process.num_threads()}개")

# Xavier NX GPU 모니터링 (실제 하드웨어에서)
# nvidia-smi 명령어 또는 jetson-stats 사용
```

---

## 📞 지원 및 문의

### 기술 지원
- **이메일**: support@hmm-ess-ai.com (예시)
- **문서**: [GitHub Repository](https://github.com/your-repo/hmm-ess-ai)
- **FAQ**: TROUBLESHOOTING.md

### 시스템 정보
- **버전**: 1.0.0
- **최종 업데이트**: 2025-01-07
- **라이선스**: Proprietary

---

## 📌 빠른 참조

### 자주 사용하는 명령어
```bash
# 전체 테스트
python -m pytest tests/ -v

# 특정 Stage 테스트
python tests/test_stage12.py

# 시뮬레이션 실행
python src/simulation/physics_engine.py

# 데이터베이스 백업
python -c "from src.database.db_schema import DatabaseManager; db = DatabaseManager(); db.backup_database()"

# 일일 리포트 생성
python -c "from src.reports.daily_report import DailyReportGenerator; from src.database.db_schema import DatabaseManager; from datetime import datetime; gen = DailyReportGenerator(DatabaseManager()); print(gen.format_text_report(gen.generate_report(datetime.now())))"
```

### 주요 설정값
- **AI 추론 주기**: 2초
- **센서 데이터 수집**: 1분 간격
- **배치 학습**: 수요일/일요일 02:00-04:00
- **일일 리포트**: 매일 07:00
- **주간 리포트**: 월요일 09:00
- **월간 리포트**: 매월 2일 10:00
- **데이터 백업**: 매일 자정

### 성능 목표
- **펌프 절감**: 46-52% (60Hz 대비)
- **팬 절감**: 50-58% (60Hz 대비)
- **T5 정확도**: 90% 이상 (34-36°C)
- **T6 정확도**: 90% 이상 (42-44°C)
- **시스템 가용성**: 99.5% 이상
- **AI 응답**: <2초
- **ML 추론**: <10ms
- **메모리**: <8GB
- **ROI**: <12개월

---

**끝**
