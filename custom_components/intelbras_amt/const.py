"""Constants for Intelbras AMT integration."""

from typing import Final

DOMAIN: Final = "intelbras_amt"

# Connection defaults
DEFAULT_PORT: Final = 9009
DEFAULT_CONTROL_PORT: Final = 9019  # HTTP control port for CLI access
DEFAULT_SCAN_INTERVAL: Final = 1  # seconds
CONNECTION_TIMEOUT: Final = 5  # seconds
RECONNECT_INTERVAL: Final = 10  # seconds

# Configuration keys
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_PASSWORD: Final = "password"
CONF_PASSWORD_A: Final = "password_a"
CONF_PASSWORD_B: Final = "password_b"
CONF_PASSWORD_C: Final = "password_c"
CONF_PASSWORD_D: Final = "password_d"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Protocol constants
FRAME_START: Final = 0xE9
FRAME_SEPARATOR: Final = 0x21
FRAME_HEARTBEAT: Final = 0xF7
FRAME_ACK: Final = 0xFE
CMD_CONNECTION_INFO: Final = 0x94  # Central sends this on connect

# Server mode defaults
DEFAULT_SERVER_HOST: Final = "0.0.0.0"
RESPONSE_TIMEOUT: Final = 8  # seconds

# Commands (ASCII)
CMD_STATUS_5A: Final = bytes([0x5A])  # 'Z' - Partial statis AMT 2018 E SMART (43 bytes response)
CMD_STATUS_5B: Final = bytes([0x5B])  # '[' - Full status (54 bytes response)
CMD_ARM: Final = bytes([0x41])  # 'A'
CMD_DISARM: Final = bytes([0x44])  # 'D'
CMD_STAY: Final = bytes([0x41, 0x50])  # 'AP'
CMD_ARM_PARTITION_A: Final = bytes([0x41, 0x41])  # 'AA'
CMD_ARM_PARTITION_B: Final = bytes([0x41, 0x42])  # 'AB'
CMD_ARM_PARTITION_C: Final = bytes([0x41, 0x43])  # 'AC'
CMD_ARM_PARTITION_D: Final = bytes([0x41, 0x44])  # 'AD'
CMD_STAY_PARTITION_A: Final = bytes([0x41, 0x50, 0x41])  # 'APA'
CMD_STAY_PARTITION_B: Final = bytes([0x41, 0x50, 0x42])  # 'APB'
CMD_STAY_PARTITION_C: Final = bytes([0x41, 0x50, 0x43])  # 'APC'
CMD_STAY_PARTITION_D: Final = bytes([0x41, 0x50, 0x44])  # 'APD'
CMD_DISARM_PARTITION_A: Final = bytes([0x44, 0x41])  # 'DA'
CMD_DISARM_PARTITION_B: Final = bytes([0x44, 0x42])  # 'DB'
CMD_DISARM_PARTITION_C: Final = bytes([0x44, 0x43])  # 'DC'
CMD_DISARM_PARTITION_D: Final = bytes([0x44, 0x44])  # 'DD'
CMD_PGM_ON_PREFIX: Final = bytes([0x50, 0x4C])  # 'PL'
CMD_PGM_OFF_PREFIX: Final = bytes([0x50, 0x44])  # 'PD'
CMD_BYPASS: Final = bytes([0x42])  # 'B'
CMD_SIREN_ON: Final = bytes([0x43])  # 'C' - Turn siren on
CMD_SIREN_OFF: Final = bytes([0x63])  # 'c' - Turn siren off

# NACK error codes
NACK_INVALID_PACKET: Final = 0xE0
NACK_WRONG_PASSWORD: Final = 0xE1
NACK_INVALID_COMMAND: Final = 0xE2
NACK_NOT_PARTITIONED: Final = 0xE3
NACK_ZONES_OPEN: Final = 0xE4
NACK_DISCONTINUED: Final = 0xE5
NACK_NO_BYPASS_PERMISSION: Final = 0xE6
NACK_NO_DEACTIVATE_PERMISSION: Final = 0xE7
NACK_BYPASS_NOT_ALLOWED: Final = 0xE8
NACK_NO_ZONES_IN_PARTITION: Final = 0xEA

NACK_MESSAGES: Final = {
    NACK_INVALID_PACKET: "Pacote inválido",
    NACK_WRONG_PASSWORD: "Senha incorreta",
    NACK_INVALID_COMMAND: "Comando inválido",
    NACK_NOT_PARTITIONED: "Central não particionada",
    NACK_ZONES_OPEN: "Zonas abertas",
    NACK_DISCONTINUED: "Função descontinuada",
    NACK_NO_BYPASS_PERMISSION: "Sem permissão para anular",
    NACK_NO_DEACTIVATE_PERMISSION: "Sem permissão para desativar",
    NACK_BYPASS_NOT_ALLOWED: "Anulação não permitida",
    NACK_NO_ZONES_IN_PARTITION: "Sem zonas na partição",
}

# Response byte offsets (AMT 4010 - 0x37 response)
# After removing frame header, data starts at index 0
OFFSET_ZONES_OPEN_START: Final = 2
OFFSET_ZONES_OPEN_END: Final = 10  # 8 bytes = 64 zones
OFFSET_ZONES_VIOLATED_START: Final = 10
OFFSET_ZONES_VIOLATED_END: Final = 18
OFFSET_ZONES_BYPASSED_START: Final = 18
OFFSET_ZONES_BYPASSED_END: Final = 26
OFFSET_MODEL_ID: Final = 26
OFFSET_FIRMWARE: Final = 27
OFFSET_PARTITION_AB: Final = 28
OFFSET_PARTITION_CD: Final = 29
OFFSET_CENTRAL_STATUS: Final = 30
OFFSET_POWER_STATUS: Final = 36
OFFSET_BATTERY_LEVEL: Final = 41
OFFSET_PGM_SIREN_STATUS: Final = 46

# Model IDs
MODEL_AMT_4010_SMART: Final = 0x41
MODEL_AMT_2018: Final = 0x39
MODEL_AMT_1016: Final = 0x38
MODEL_AMT_2018_E_SMART: Final = 0x34

MODEL_NAMES: Final = {
    MODEL_AMT_4010_SMART: "AMT 4010 SMART",
    MODEL_AMT_2018: "AMT 2018",
    MODEL_AMT_1016: "AMT 1016",
    MODEL_AMT_2018_E_SMART: "AMT 2018 E SMART"
}

# Status bits
BIT_ARMED: Final = 0x08  # bit 3
BIT_AC_POWER: Final = 0x01  # bit 0
BIT_BATTERY_CONNECTED: Final = 0x04  # bit 2
BIT_SIREN: Final = 0x01  # bit 0 in PGM/Siren byte
BIT_PROBLEM: Final = 0x10  # bit 4

# Partition status bits
PARTITION_ARMED_BIT: Final = 0x01
PARTITION_STAY_BIT: Final = 0x02
PARTITION_TRIGGERED_BIT: Final = 0x04

# Number of zones/partitions/PGMs by model
MAX_ZONES_4010: Final = 64
MAX_ZONES_2018: Final = 18
MAX_ZONES_1016: Final = 16
MAX_ZONES_2018_E_SMART: Final = 48
MAX_PARTITIONS: Final = 4
MAX_PGMS: Final = 19  # Expanded from 3 to 19

# Zone sensor limits
MAX_ZONES_TAMPER: Final = 18
MAX_ZONES_SHORT_CIRCUIT: Final = 18
MAX_ZONES_LOW_BATTERY: Final = 40

# Entity prefixes
ENTITY_PREFIX: Final = "amt"

# Data keys for coordinator
DATA_ZONES_OPEN: Final = "zones_open"
DATA_ZONES_VIOLATED: Final = "zones_violated"
DATA_ZONES_BYPASSED: Final = "zones_bypassed"
DATA_ZONES_TAMPER: Final = "zones_tamper"
DATA_ZONES_SHORT_CIRCUIT: Final = "zones_short_circuit"
DATA_ZONES_LOW_BATTERY: Final = "zones_low_battery"
DATA_MODEL_ID: Final = "model_id"
DATA_MODEL_NAME: Final = "model_name"
DATA_FIRMWARE: Final = "firmware"
DATA_PARTITIONS: Final = "partitions"
DATA_ARMED: Final = "armed"
DATA_STAY: Final = "stay"
DATA_TRIGGERED: Final = "triggered"
DATA_AC_POWER: Final = "ac_power"
DATA_BATTERY_CONNECTED: Final = "battery_connected"
DATA_BATTERY_LEVEL: Final = "battery_level"
DATA_SIREN: Final = "siren"
DATA_PROBLEM: Final = "problem"
DATA_PGMS: Final = "pgms"
DATA_CONNECTED: Final = "connected"
DATA_MAX_ZONES: Final = "max_zones"

# Detailed problem data keys
DATA_BATTERY_LOW: Final = "battery_low"
DATA_BATTERY_ABSENT: Final = "battery_absent"
DATA_BATTERY_SHORT: Final = "battery_short"
DATA_AUX_OVERLOAD: Final = "aux_overload"
DATA_SIREN_WIRE_CUT: Final = "siren_wire_cut"
DATA_SIREN_SHORT: Final = "siren_short"
DATA_PHONE_LINE_CUT: Final = "phone_line_cut"
DATA_COMM_FAILURE: Final = "comm_failure"

# Zone count data keys
DATA_ZONES_OPEN_COUNT: Final = "zones_open_count"
DATA_ZONES_VIOLATED_COUNT: Final = "zones_violated_count"
DATA_ZONES_BYPASSED_COUNT: Final = "zones_bypassed_count"

# Date/time from central
DATA_DATETIME: Final = "datetime"

# Partition names
PARTITION_NAMES: Final = {
    0: "A",
    1: "B",
    2: "C",
    3: "D",
}
