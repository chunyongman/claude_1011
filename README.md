# ESS AI 머신러닝 제어 시스템 (HMM 16K급)

NVIDIA Jetson Xavier NX 기반 3단계 진화형 AI ESS 제어 시스템

## 시스템 개요

- **하드웨어**: NVIDIA Jetson Xavier NX (21 TOPS, 8GB, 6-core CPU)
- **목표**: 펌프 46-52%, 팬 50-58% 에너지 절감
- **제어 방식**: 규칙 기반 → 패턴 학습 → 적응형 학습 (3단계 진화)
- **운전 주기**: 2초 실시간 제어
- **학습 주기**: 주 2회 배치 학습 (수요일, 일요일 심야 02:00-04:00)

## 단계 1: 기본 데이터 모델 및 3단계 AI 진화 시스템 구축 ✅

### 구현 완료 사항

#### 1. 센서 데이터 모델 (`src/models/sensor_data.py`)
- ✅ 냉각 시스템 온도 센서 (T1-T5)
- ✅ 환기 시스템 온도 센서 (T6-T7)
- ✅ 압력 센서 (PX1)
- ✅ 운전 조건 (엔진 부하, GPS)
- ✅ 3-시그마 필터링
- ✅ 센서별 변화율 제한
- ✅ 열교환 원리 검증

#### 2. 3단계 AI 진화 시스템 (`src/ai/evolution_system.py`)
- ✅ Stage 1 (0-6개월): 80% 규칙 + 20% ML
- ✅ Stage 2 (6-12개월): 70% 규칙 + 30% ML
- ✅ Stage 3 (12개월+): 60% 규칙 + 40% ML
- ✅ 학습 시작 조건 관리
- ✅ 배치 학습 스케줄 (수/일 02:00-04:00)
- ✅ 학습 중단 조건

#### 3. Xavier NX 리소스 관리 (`src/core/resource_manager.py`)
- ✅ 메모리 할당 계획 (8GB)
- ✅ 스토리지 할당 계획 (256GB)
- ✅ 데이터 순환 정책
- ✅ ML 모델 성능 활용 모니터링 (현재 10% 활용)
- ✅ 동작 모드 전환 (실시간 제어 ↔ 배치 학습)

#### 4. 안전 제약조건 (`src/core/safety_constraints.py`)
- ✅ 온도 제약조건 (절대 위반 불가)
  - T2/T3 ≥ 48°C → 강제 증속
  - T6 > 50°C → 전 팬 60Hz
  - T5 > 36°C → SW펌프 증속
- ✅ 주파수 제약 (40-60Hz, ±3Hz 학습 허용)
- ✅ 급격한 변화 금지 (5Hz/분)
- ✅ 운전 대수 제약
- ✅ 긴급 안전 오버라이드

#### 5. IO 매핑 시스템 (`src/io/io_manager.py`)
- ✅ YAML 기반 설정 관리
- ✅ Siemens PLC 태그 매핑
- ✅ Danfoss VFD 명령
- ✅ 시뮬레이션 모드 / 실제 운영 모드
- ✅ 동적 설정 변경

## 프로젝트 구조

```
Claude-code/
├── config/
│   └── io_mapping.yaml          # IO 매핑 설정
├── src/
│   ├── models/
│   │   └── sensor_data.py       # 센서 데이터 모델
│   ├── ai/
│   │   └── evolution_system.py  # 3단계 AI 진화 시스템
│   ├── core/
│   │   ├── resource_manager.py  # Xavier NX 리소스 관리
│   │   └── safety_constraints.py # 안전 제약조건
│   └── io/
│       └── io_manager.py        # IO 매핑 시스템
├── tests/
│   └── test_stage1.py           # 단계 1 테스트
├── requirements.txt             # Python 패키지
└── README.md
```

## 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 단계 1 테스트 실행
```bash
python tests/test_stage1.py
```

## 테스트 검증 기준

- ✅ 모든 센서의 범위 체크 정상 동작
- ✅ 설정 변경 후 즉시 반영
- ✅ 매핑 시스템 오류 없이 동작
- ✅ Xavier NX 메모리 사용량 계획 범위 내

## 제어 대상

### Main Cooling S.W Pump (3대)
- 용량: 132kW, 1,250 m³/h × 2.5 bar
- 운전: 최대 2대, 1대 대기

### LT F.W Cooling Pump (3대)
- 용량: 75kW, 740 m³/h × 2.5 bar
- 운전: 최대 2대, 1대 대기

### E/R 팬 (4대)
- 용량: 54.3kW, 3,200 m³/min × 72.6 mmAq
- 운전: 최소 2대

## 다음 단계

단계 1 완료 후, 다음을 진행합니다:
- 📌 단계 2: Stage 1 규칙 기반 제어 로직 구현
- 📌 단계 3: Polynomial Regression 온도 예측 모델
- 📌 단계 4: 세제곱 법칙 기반 에너지 최적화
- 📌 단계 5: 실시간 제어 루프 구현

## 라이선스

Proprietary - HMM 16K ESS AI System
