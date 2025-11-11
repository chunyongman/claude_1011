# EDGE AI REAL - 선박 엔진룸 온도 제어 시스템

## 프로젝트 개요
PLC 기반의 AI 예측 제어 시스템을 활용한 선박 엔진룸(E/R) 온도 관리 시스템

## 디렉토리 구조

```
EDGE_AI_REAL/
├── src/                          # 소스 코드
├── config/                       # 설정 파일
├── data/                         # 데이터 파일
├── tests/                        # 테스트 스크립트
├── test_results/                 # 테스트 결과 (CSV 파일)
├── E/                            # 추가 리소스
├── docs/                         # 문서 모음
│   ├── certification/           # 인증 관련 문서
│   │   ├── 인증기관_질의_답변서.md
│   │   ├── 인증기관_질의답변_1_PLC제어응답속도.md
│   │   ├── 인증기관_질의답변_2_AI예측제어정확도.md
│   │   ├── 인증기관_질의답변_3_HMI실시간반영주기.md
│   │   ├── 인증시험_실행절차서.md
│   │   ├── AI_예측_정확도_테스트_방법론.md
│   │   └── PLC_응답속도_측정방법_비교.md
│   ├── guides/                  # 사용 가이드
│   │   ├── HMI_DASHBOARD_README.md
│   │   ├── USAGE_GUIDE.md
│   │   ├── DASHBOARD_SCENARIO_GUIDE.md
│   │   └── 실행_가이드.md
│   ├── summaries/               # 개발 완료 요약
│   │   ├── COMPLETE_SYSTEM_SUMMARY.md
│   │   ├── STAGE9_COMPLETION_SUMMARY.md
│   │   ├── STAGE10_COMPLETION_SUMMARY.md
│   │   ├── INTEGRATION_COMPLETE_SUMMARY.md
│   │   └── HMI_예측제어_통합_완료.md
│   ├── control_scenarios/       # 제어 시나리오 문서
│   │   ├── ER_TEMPERATURE_CONTROL_SCENARIO.md
│   │   ├── ER_FAN_CONTROL_SCENARIOS.md
│   │   ├── SW_PUMP_CONTROL_SCENARIOS.md
│   │   ├── FW_PUMP_CONTROL_SCENARIOS.md
│   │   ├── ML_SAFETY_MECHANISM.md
│   │   └── T6_CONTROL_LOGIC_UPDATE.md
│   └── technical/               # 기술 문서
│       ├── PREDICTIVE_CONTROL_INTEGRATION.md
│       ├── PREDICTIVE_CONTROL_LOGIC_EXPLAINED.md
│       ├── 온도_예측_알고리즘_설명.md
│       ├── RULE_BASED_AI_MIGRATION.md
│       ├── PID_PREDICTIVE_CONTROL_INTEGRATION.md
│       ├── PID_GAIN_TUNING_GUIDE.md
│       └── 주파수_제어_문제_수정.md
├── requirements.txt             # Python 패키지 의존성
└── run_dashboard.bat            # 대시보드 실행 스크립트
```

## 시작하기

### 설치
```bash
pip install -r requirements.txt
```

### 실행
```bash
# Windows
run_dashboard.bat

# 또는 직접 실행
streamlit run src/dashboard/dashboard.py
```

## 주요 기능
- PLC 기반 실시간 온도 제어
- AI 예측 제어 시스템
- HMI 대시보드를 통한 실시간 모니터링
- E/R 팬, 냉각수 펌프 자동 제어

## 문서
- 사용 가이드: [docs/guides/](docs/guides/)
- 인증 관련: [docs/certification/](docs/certification/)
- 기술 문서: [docs/technical/](docs/technical/)

## 테스트
테스트 실행 방법은 [docs/certification/인증시험_실행절차서.md](docs/certification/인증시험_실행절차서.md)를 참조하세요.
