#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
통합 시스템 운전 스크립트
"""

from src.integration.system_manager import SystemManager
import time


def main():
    """메인 함수"""
    print("\n" + "="*80)
    print("ESS AI 통합 시스템 - 시작")
    print("="*80 + "\n")

    # 시스템 매니저 초기화
    manager = SystemManager()

    # 4단계 초기화
    print("시스템 초기화 중...")
    if manager.initialize():
        print("[OK] 시스템 초기화 완료\n")

        # 운전 시작 (5개 독립 스레드)
        print("운전 시작 (5개 독립 스레드)...")
        manager.start_operation()
        print("[OK] 운전 시작 완료\n")

        # 24시간 무인 운전
        try:
            print("무인 운전 모드 - 1분마다 상태 출력")
            print("종료: Ctrl+C\n")

            while True:
                # 시스템 상태 모니터링
                status = manager.get_system_status()

                print(f"\n{'='*80}")
                print(f"[상태] 가동 시간: {status['uptime_hours']:.2f}h")
                print(f"[리소스] CPU: {status['resource_usage']['cpu_percent_avg']:.1f}% | "
                      f"메모리: {status['resource_usage']['memory_gb_avg']:.2f} GB")
                print(f"[성능] 오류: {status['performance']['total_errors']}건 | "
                      f"가용성: {manager.get_availability():.2f}%")
                print(f"{'='*80}")

                time.sleep(60)  # 1분마다 상태 확인

        except KeyboardInterrupt:
            # Graceful shutdown
            print("\n\n시스템 종료 시작...")
            manager.shutdown()
            print("[OK] 시스템 정상 종료 완료")
    else:
        print("[ERROR] 시스템 초기화 실패")


if __name__ == "__main__":
    main()
