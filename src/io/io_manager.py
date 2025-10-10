"""
ESS AI System - IO 매핑 시스템
PLC/VFD 통신 및 시뮬레이션 모드
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from datetime import datetime
from pathlib import Path
import yaml
from enum import Enum
import random


class IOMode(Enum):
    """IO 동작 모드"""
    SIMULATION = "simulation"  # 시뮬레이션 모드 (실제 PLC 없이 테스트)
    PRODUCTION = "production"  # 실제 운영 모드 (PLC/VFD 연결)


@dataclass
class PLCTag:
    """PLC 태그 정보"""
    tag_name: str
    description: str
    data_type: str  # REAL, INT, BOOL 등
    address: str  # DB100.DBD0 등
    unit: Optional[str] = None
    value: Any = None
    last_update: Optional[datetime] = None


@dataclass
class VFDCommand:
    """VFD 명령"""
    vfd_id: str
    description: str
    frequency_hz: float = 0.0
    start_stop: bool = False
    feedback_frequency: Optional[float] = None
    last_command_time: Optional[datetime] = None


class IOManager:
    """IO 매핑 관리자"""

    def __init__(self, config_path: str, mode: IOMode = IOMode.SIMULATION):
        self.config_path = Path(config_path)
        self.mode = mode
        self.config: Dict = {}
        self.input_tags: Dict[str, PLCTag] = {}
        self.output_tags: Dict[str, PLCTag] = {}
        self.vfd_commands: Dict[str, VFDCommand] = {}

        # 시뮬레이션 데이터
        self.simulation_data: Dict[str, float] = {}

        self.load_config()
        self.initialize_tags()

    def load_config(self) -> None:
        """설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            print(f"✅ IO 설정 로드 완료: {self.config_path}")
        except FileNotFoundError:
            print(f"⚠️ 설정 파일 없음: {self.config_path}")
            self.config = self._create_default_config()
        except Exception as e:
            print(f"❌ 설정 로드 실패: {e}")
            self.config = self._create_default_config()

    def _create_default_config(self) -> Dict:
        """기본 설정 생성"""
        return {
            "system_info": {
                "version": "1.0.0",
                "mode": "simulation"
            },
            "input_sensors": {},
            "output_controls": {}
        }

    def initialize_tags(self) -> None:
        """태그 초기화"""
        # 입력 센서 태그 생성
        if "input_sensors" in self.config:
            self._init_input_tags(self.config["input_sensors"])

        # 출력 제어 태그 생성
        if "output_controls" in self.config:
            self._init_output_tags(self.config["output_controls"])

    def _init_input_tags(self, sensors_config: Dict) -> None:
        """입력 태그 초기화"""
        # 냉각 시스템 온도
        if "cooling_temp" in sensors_config:
            for sensor_id, sensor_info in sensors_config["cooling_temp"].items():
                tag = PLCTag(
                    tag_name=sensor_info["plc_tag"],
                    description=sensor_info["description"],
                    data_type="REAL",
                    address=sensor_info["plc_tag"],
                    unit=sensor_info["unit"]
                )
                self.input_tags[sensor_id] = tag

        # 환기 시스템 온도
        if "ventilation_temp" in sensors_config:
            for sensor_id, sensor_info in sensors_config["ventilation_temp"].items():
                tag = PLCTag(
                    tag_name=sensor_info["plc_tag"],
                    description=sensor_info["description"],
                    data_type="REAL",
                    address=sensor_info["plc_tag"],
                    unit=sensor_info["unit"]
                )
                self.input_tags[sensor_id] = tag

        # 압력
        if "pressure" in sensors_config:
            for sensor_id, sensor_info in sensors_config["pressure"].items():
                tag = PLCTag(
                    tag_name=sensor_info["plc_tag"],
                    description=sensor_info["description"],
                    data_type="REAL",
                    address=sensor_info["plc_tag"],
                    unit=sensor_info["unit"]
                )
                self.input_tags[sensor_id] = tag

        # 운전 조건
        if "operating" in sensors_config:
            for sensor_id, sensor_info in sensors_config["operating"].items():
                tag = PLCTag(
                    tag_name=sensor_info["plc_tag"],
                    description=sensor_info["description"],
                    data_type="REAL",
                    address=sensor_info["plc_tag"],
                    unit=sensor_info.get("unit")
                )
                self.input_tags[sensor_id] = tag

    def _init_output_tags(self, controls_config: Dict) -> None:
        """출력 태그 초기화"""
        # SW Pumps
        if "sw_pumps" in controls_config:
            for pump_id, pump_info in controls_config["sw_pumps"].items():
                vfd = VFDCommand(
                    vfd_id=pump_info["vfd_address"],
                    description=pump_info["description"]
                )
                self.vfd_commands[f"sw_pump_{pump_id}"] = vfd

                # 주파수 명령 태그
                tag = PLCTag(
                    tag_name=pump_info["frequency_cmd"],
                    description=f"{pump_info['description']} - Frequency",
                    data_type="REAL",
                    address=pump_info["frequency_cmd"],
                    unit="Hz"
                )
                self.output_tags[f"sw_pump_{pump_id}_freq"] = tag

        # FW Pumps
        if "fw_pumps" in controls_config:
            for pump_id, pump_info in controls_config["fw_pumps"].items():
                vfd = VFDCommand(
                    vfd_id=pump_info["vfd_address"],
                    description=pump_info["description"]
                )
                self.vfd_commands[f"fw_pump_{pump_id}"] = vfd

                tag = PLCTag(
                    tag_name=pump_info["frequency_cmd"],
                    description=f"{pump_info['description']} - Frequency",
                    data_type="REAL",
                    address=pump_info["frequency_cmd"],
                    unit="Hz"
                )
                self.output_tags[f"fw_pump_{pump_id}_freq"] = tag

        # E/R Fans
        if "er_fans" in controls_config:
            for fan_id, fan_info in controls_config["er_fans"].items():
                vfd = VFDCommand(
                    vfd_id=fan_info["vfd_address"],
                    description=fan_info["description"]
                )
                self.vfd_commands[f"er_fan_{fan_id}"] = vfd

                tag = PLCTag(
                    tag_name=fan_info["frequency_cmd"],
                    description=f"{fan_info['description']} - Frequency",
                    data_type="REAL",
                    address=fan_info["frequency_cmd"],
                    unit="Hz"
                )
                self.output_tags[f"er_fan_{fan_id}_freq"] = tag

    def read_input(self, tag_id: str) -> Optional[float]:
        """입력 태그 읽기"""
        if self.mode == IOMode.SIMULATION:
            return self._read_simulation_input(tag_id)
        else:
            return self._read_plc_input(tag_id)

    def _read_simulation_input(self, tag_id: str) -> Optional[float]:
        """시뮬레이션 입력 데이터 생성"""
        # 정상 운전 상태의 시뮬레이션 값 생성
        simulation_defaults = {
            "T1": 28.0 + random.uniform(-1.0, 1.0),  # 해수 입구
            "T2": 42.0 + random.uniform(-2.0, 2.0),  # SW 출구 1
            "T3": 43.0 + random.uniform(-2.0, 2.0),  # SW 출구 2
            "T4": 45.0 + random.uniform(-1.5, 1.5),  # FW 입구
            "T5": 33.0 + random.uniform(-1.0, 1.0),  # FW 출구
            "T6": 43.0 + random.uniform(-1.0, 1.0),  # E/R 온도
            "T7": 32.0 + random.uniform(-2.0, 2.0),  # 외기 온도
            "PX1": 2.0 + random.uniform(-0.2, 0.2),  # 압력
            "engine_load": 75.0 + random.uniform(-10.0, 10.0),  # 엔진 부하
            "gps_latitude": 14.5,
            "gps_longitude": 120.5,
            "gps_speed": 18.5 + random.uniform(-1.0, 1.0),
            "utc_time": datetime.now().timestamp()
        }

        value = simulation_defaults.get(tag_id)
        if value is not None and tag_id in self.input_tags:
            self.input_tags[tag_id].value = value
            self.input_tags[tag_id].last_update = datetime.now()

        return value

    def _read_plc_input(self, tag_id: str) -> Optional[float]:
        """실제 PLC에서 입력 읽기"""
        # TODO: Siemens PLC 통신 구현
        # S7 프로토콜을 사용한 실제 데이터 읽기
        print(f"⚠️ PLC 통신 미구현: {tag_id}")
        return None

    def write_output(self, tag_id: str, value: float) -> bool:
        """출력 태그 쓰기"""
        if self.mode == IOMode.SIMULATION:
            return self._write_simulation_output(tag_id, value)
        else:
            return self._write_plc_output(tag_id, value)

    def _write_simulation_output(self, tag_id: str, value: float) -> bool:
        """시뮬레이션 출력 쓰기"""
        if tag_id in self.output_tags:
            self.output_tags[tag_id].value = value
            self.output_tags[tag_id].last_update = datetime.now()
            print(f"📤 [SIM] {tag_id}: {value:.1f}Hz")
            return True
        return False

    def _write_plc_output(self, tag_id: str, value: float) -> bool:
        """실제 PLC에 출력 쓰기"""
        # TODO: Siemens PLC 통신 구현
        # Danfoss VFD로 주파수 명령 전송
        print(f"⚠️ PLC 통신 미구현: {tag_id} = {value}")
        return False

    def read_all_inputs(self) -> Dict[str, float]:
        """모든 입력 읽기"""
        data = {}
        for tag_id in self.input_tags.keys():
            value = self.read_input(tag_id)
            if value is not None:
                data[tag_id] = value
        return data

    def write_all_outputs(self, outputs: Dict[str, float]) -> bool:
        """모든 출력 쓰기"""
        success = True
        for tag_id, value in outputs.items():
            if not self.write_output(tag_id, value):
                success = False
        return success

    def switch_mode(self, new_mode: IOMode) -> bool:
        """모드 전환"""
        if self.mode == new_mode:
            return True

        print(f"🔄 IO 모드 전환: {self.mode.value} → {new_mode.value}")

        if new_mode == IOMode.PRODUCTION:
            # 실제 운영 모드로 전환시 PLC 연결 확인
            if not self._check_plc_connection():
                print("❌ PLC 연결 실패 - 시뮬레이션 모드 유지")
                return False

        self.mode = new_mode

        # 설정 파일 업데이트
        if "system_info" in self.config:
            self.config["system_info"]["mode"] = new_mode.value
            self.save_config()

        return True

    def _check_plc_connection(self) -> bool:
        """PLC 연결 확인"""
        # TODO: 실제 PLC 연결 테스트
        return False

    def save_config(self) -> None:
        """설정 저장"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            print(f"✅ 설정 저장 완료: {self.config_path}")
        except Exception as e:
            print(f"❌ 설정 저장 실패: {e}")

    def get_io_status(self) -> Dict:
        """IO 상태 조회"""
        return {
            "mode": self.mode.value,
            "config_path": str(self.config_path),
            "input_tags_count": len(self.input_tags),
            "output_tags_count": len(self.output_tags),
            "vfd_commands_count": len(self.vfd_commands),
            "input_tags": {tag_id: {
                "description": tag.description,
                "value": tag.value,
                "unit": tag.unit,
                "last_update": tag.last_update.isoformat() if tag.last_update else None
            } for tag_id, tag in self.input_tags.items()},
            "output_tags": {tag_id: {
                "description": tag.description,
                "value": tag.value,
                "unit": tag.unit,
                "last_update": tag.last_update.isoformat() if tag.last_update else None
            } for tag_id, tag in self.output_tags.items()}
        }

    def get_tag_mapping_summary(self) -> str:
        """태그 매핑 요약"""
        summary = []
        summary.append(f"=== IO Mapping Summary ({self.mode.value}) ===\n")

        summary.append("📥 Input Tags:")
        for tag_id, tag in self.input_tags.items():
            summary.append(f"  {tag_id:15s} → {tag.address:15s} ({tag.description})")

        summary.append("\n📤 Output Tags:")
        for tag_id, tag in self.output_tags.items():
            summary.append(f"  {tag_id:25s} → {tag.address:15s} ({tag.description})")

        return "\n".join(summary)


def create_io_manager(config_path: str, mode: IOMode = IOMode.SIMULATION) -> IOManager:
    """IO 매니저 생성"""
    return IOManager(config_path, mode)
