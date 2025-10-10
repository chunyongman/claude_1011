#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SystemManager 간단 테스트
"""

import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

from src.integration.system_manager import SystemManager

def main():
    print("\n" + "="*80)
    print("ESS AI 통합 시스템 테스트")
    print("="*80 + "\n")

    # 시스템 매니저 초기화
    manager = SystemManager()

    # 초기화 시도
    print("시스템 초기화 시도...")
    if manager.initialize():
        print("\n[SUCCESS] 시스템 초기화 성공!")

        # 상태 확인
        print("\n시스템 상태:")
        for key, value in manager.system_state.items():
            print(f"  {key}: {value}")

        print("\n운전 시작...")
        manager.start_operation()

        print("\n운전 중... (10초 후 종료)")
        import time
        time.sleep(10)

        print("\n시스템 종료...")
        manager.shutdown()
        print("\n[SUCCESS] 정상 종료 완료")
    else:
        print("\n[FAILED] 시스템 초기화 실패")

if __name__ == "__main__":
    main()
