"""
SQLite 데이터베이스 스키마 정의
256GB NVMe SSD 활용
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import os


class DatabaseManager:
    """데이터베이스 관리자"""

    def __init__(self, db_path: str = "data/ess_system.db"):
        """
        초기화

        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path

        # 데이터 디렉토리 생성
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # 데이터베이스 초기화
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """데이터베이스 연결 획득"""
        conn = sqlite3.Connection(self.db_path)
        conn.row_factory = sqlite3.Row  # dict-like access
        return conn

    def init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 1. sensor_data 테이블 (1분 단위 센서 데이터)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            T1 REAL,  -- SW Inlet
            T2 REAL,  -- No.1 Cooler SW Outlet
            T3 REAL,  -- No.2 Cooler SW Outlet
            T4 REAL,  -- FW Inlet
            T5 REAL,  -- FW Outlet
            T6 REAL,  -- E/R Temperature
            T7 REAL,  -- Outside Air
            PX1 REAL,  -- SW Discharge Pressure
            engine_load REAL,  -- Engine Load %
            latitude REAL,  -- GPS Latitude
            longitude REAL,  -- GPS Longitude
            speed REAL,  -- Speed (knots)
            heading REAL,  -- Heading (degrees)
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 인덱스 생성 (빠른 검색)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sensor_timestamp
        ON sensor_data(timestamp)
        """)

        # 2. control_data 테이블 (제어 명령 이력)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS control_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            sw_pump_count INTEGER,
            sw_pump_freq REAL,
            fw_pump_count INTEGER,
            fw_pump_freq REAL,
            er_fan_count INTEGER,
            er_fan_freq REAL,
            control_mode TEXT,  -- 'AI' or 'FIXED_60HZ'
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_control_timestamp
        ON control_data(timestamp)
        """)

        # 3. alarm_history 테이블 (알람 발생/해제 기록)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS alarm_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            priority TEXT,  -- 'CRITICAL', 'WARNING', 'INFO'
            equipment TEXT,
            message TEXT,
            status TEXT,  -- 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED'
            acknowledged_at DATETIME,
            resolved_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alarm_timestamp
        ON alarm_history(timestamp)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alarm_priority
        ON alarm_history(priority)
        """)

        # 4. performance_metrics 테이블 (성과 지표)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            period TEXT,  -- 'DAILY', 'WEEKLY', 'MONTHLY'
            energy_savings_avg REAL,  -- 평균 에너지 절감률 (%)
            energy_savings_sw_pump REAL,  -- SW 펌프 절감률
            energy_savings_fw_pump REAL,  -- FW 펌프 절감률
            energy_savings_er_fan REAL,  -- E/R 팬 절감률
            t5_accuracy REAL,  -- T5 목표 달성률 (%)
            t6_accuracy REAL,  -- T6 목표 달성률 (%)
            safety_compliance REAL,  -- 안전 준수율 (%)
            uptime_rate REAL,  -- 가동률 (%)
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_performance_timestamp
        ON performance_metrics(timestamp)
        """)

        # 5. equipment_runtime 테이블 (장비별 운전시간)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment_runtime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            equipment_id TEXT NOT NULL,  -- 'SW-P1', 'FW-P1', 'ER-F1', etc.
            total_runtime REAL,  -- 총 운전시간 (hours)
            daily_runtime REAL,  -- 금일 운전시간 (hours)
            continuous_runtime REAL,  -- 연속 운전시간 (hours)
            start_count INTEGER,  -- 기동 횟수
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_runtime_timestamp
        ON equipment_runtime(timestamp)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_runtime_equipment
        ON equipment_runtime(equipment_id)
        """)

        # 6. vfd_health 테이블 (VFD 건강도 및 진단)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vfd_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            equipment_id TEXT NOT NULL,
            status_bits INTEGER,  -- Danfoss StatusBits
            health_grade TEXT,  -- 'NORMAL', 'CAUTION', 'WARNING', 'CRITICAL'
            health_score REAL,  -- 0-100
            temperature REAL,  -- VFD 온도
            voltage REAL,  -- 전압
            current REAL,  -- 전류
            torque REAL,  -- 토크
            diagnostics TEXT,  -- JSON 형식 진단 정보
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_vfd_timestamp
        ON vfd_health(timestamp)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_vfd_equipment
        ON vfd_health(equipment_id)
        """)

        # 7. learning_history 테이블 (AI 학습 이력)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            learning_type TEXT,  -- 'BATCH', 'ONLINE', 'PARAMETER_TUNING'
            model_name TEXT,  -- 'POLYNOMIAL_REGRESSION', 'RANDOM_FOREST', etc.
            accuracy_before REAL,
            accuracy_after REAL,
            improvement REAL,  -- 개선률 (%)
            training_time REAL,  -- 학습 시간 (seconds)
            samples_count INTEGER,  -- 학습 샘플 수
            model_size REAL,  -- 모델 크기 (MB)
            metrics TEXT,  -- JSON 형식 상세 지표
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_learning_timestamp
        ON learning_history(timestamp)
        """)

        conn.commit()
        conn.close()

    def insert_sensor_data(self, data: Dict[str, Any]):
        """센서 데이터 삽입"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO sensor_data (
            timestamp, T1, T2, T3, T4, T5, T6, T7, PX1, engine_load,
            latitude, longitude, speed, heading
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('timestamp', datetime.now()),
            data.get('T1'), data.get('T2'), data.get('T3'), data.get('T4'),
            data.get('T5'), data.get('T6'), data.get('T7'), data.get('PX1'),
            data.get('engine_load'),
            data.get('latitude'), data.get('longitude'),
            data.get('speed'), data.get('heading')
        ))

        conn.commit()
        conn.close()

    def insert_control_data(self, data: Dict[str, Any]):
        """제어 데이터 삽입"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO control_data (
            timestamp, sw_pump_count, sw_pump_freq,
            fw_pump_count, fw_pump_freq,
            er_fan_count, er_fan_freq, control_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('timestamp', datetime.now()),
            data.get('sw_pump_count'), data.get('sw_pump_freq'),
            data.get('fw_pump_count'), data.get('fw_pump_freq'),
            data.get('er_fan_count'), data.get('er_fan_freq'),
            data.get('control_mode')
        ))

        conn.commit()
        conn.close()

    def insert_alarm(self, data: Dict[str, Any]):
        """알람 삽입"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO alarm_history (
            timestamp, priority, equipment, message, status
        ) VALUES (?, ?, ?, ?, ?)
        """, (
            data.get('timestamp', datetime.now()),
            data.get('priority'),
            data.get('equipment'),
            data.get('message'),
            data.get('status', 'ACTIVE')
        ))

        conn.commit()
        conn.close()

    def insert_performance_metrics(self, data: Dict[str, Any]):
        """성과 지표 삽입"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO performance_metrics (
            timestamp, period,
            energy_savings_avg, energy_savings_sw_pump,
            energy_savings_fw_pump, energy_savings_er_fan,
            t5_accuracy, t6_accuracy,
            safety_compliance, uptime_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('timestamp', datetime.now()),
            data.get('period'),
            data.get('energy_savings_avg'),
            data.get('energy_savings_sw_pump'),
            data.get('energy_savings_fw_pump'),
            data.get('energy_savings_er_fan'),
            data.get('t5_accuracy'),
            data.get('t6_accuracy'),
            data.get('safety_compliance'),
            data.get('uptime_rate')
        ))

        conn.commit()
        conn.close()

    def get_sensor_data(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """센서 데이터 조회"""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = """
        SELECT * FROM sensor_data
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, (start_time, end_time))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_performance_metrics(
        self,
        period: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """성과 지표 조회"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if start_time and end_time:
            cursor.execute("""
            SELECT * FROM performance_metrics
            WHERE period = ? AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
            """, (period, start_time, end_time))
        else:
            cursor.execute("""
            SELECT * FROM performance_metrics
            WHERE period = ?
            ORDER BY timestamp DESC
            LIMIT 30
            """, (period,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def cleanup_old_data(self):
        """
        데이터 순환 정책 적용
        - 최근 6개월: 고해상도 보관 (1분 단위)
        - 6개월-1년: 압축 저장 (10분 단위 평균)
        - 1년 이상: 핵심 패턴만 추출 (1시간 단위 평균)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        now = datetime.now()

        # 6개월 전
        six_months_ago = now - timedelta(days=180)

        # 1년 전
        one_year_ago = now - timedelta(days=365)

        # 1년 이상 된 데이터 삭제 (핵심 패턴만 보관)
        cursor.execute("""
        DELETE FROM sensor_data
        WHERE timestamp < ?
        AND id NOT IN (
            SELECT MIN(id) FROM sensor_data
            WHERE timestamp < ?
            GROUP BY strftime('%Y-%m-%d %H', timestamp)
        )
        """, (one_year_ago, one_year_ago))

        deleted_old = cursor.rowcount

        # 6개월-1년 데이터 압축 (10분 단위만 보관)
        cursor.execute("""
        DELETE FROM sensor_data
        WHERE timestamp BETWEEN ? AND ?
        AND id NOT IN (
            SELECT MIN(id) FROM sensor_data
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY strftime('%Y-%m-%d %H:%M', timestamp) / 10
        )
        """, (one_year_ago, six_months_ago, one_year_ago, six_months_ago))

        deleted_compressed = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted_old, deleted_compressed

    def backup_database(self, backup_path: Optional[str] = None):
        """
        데이터베이스 백업

        Args:
            backup_path: 백업 파일 경로 (기본값: data/backups/ess_system_YYYYMMDD.db)
        """
        if backup_path is None:
            backup_dir = "data/backups"
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(
                backup_dir,
                f"ess_system_{datetime.now().strftime('%Y%m%d')}.db"
            )

        # SQLite 백업
        source = self.get_connection()
        destination = sqlite3.connect(backup_path)

        source.backup(destination)

        source.close()
        destination.close()

        return backup_path

    def cleanup_old_backups(self, days: int = 7):
        """
        오래된 백업 파일 삭제

        Args:
            days: 보관 일수 (기본값: 7일)
        """
        backup_dir = "data/backups"
        if not os.path.exists(backup_dir):
            return 0

        now = datetime.now()
        deleted_count = 0

        for filename in os.listdir(backup_dir):
            if not filename.endswith('.db'):
                continue

            filepath = os.path.join(backup_dir, filename)
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

            if (now - file_time).days > days:
                os.remove(filepath)
                deleted_count += 1

        return deleted_count

    def get_database_size(self) -> int:
        """데이터베이스 크기 (bytes)"""
        if os.path.exists(self.db_path):
            return os.path.getsize(self.db_path)
        return 0

    def get_database_size_mb(self) -> float:
        """데이터베이스 크기 (MB)"""
        return self.get_database_size() / (1024 * 1024)

    def get_table_row_count(self, table_name: str) -> int:
        """테이블 행 개수"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]

        conn.close()
        return count
