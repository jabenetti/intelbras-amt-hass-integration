# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0-fork] - 2026-05-16
**Fork de robsonfelix/intelbras-amt-hass-integration por @jabenetti**

### Fixed
- Response to ContactID requests (0xB0, 0xB4, 0xB5)

### Added
- AMT 2018 E SMART support

### Removed
- HTTP API client and server

## [1.4.3] - 2025-01-20

### Fixed
- Central panel now shows `armed_home` when any partition is armed in stay mode

## [1.4.2] - 2025-01-20

### Fixed
- Control server now uses proper `arm_stay_partition` method for partition stay

## [1.4.1] - 2025-01-20

### Added
- **Partition Stay Mode**: Partition panels now support ARM_HOME (stay mode)
  - Command `APA` (0x41 0x50 0x41) for partition A stay
  - Command `APB` (0x41 0x50 0x42) for partition B stay
  - Command `APC` (0x41 0x50 0x43) for partition C stay
  - Command `APD` (0x41 0x50 0x44) for partition D stay

## [1.4.0] - 2025-01-20

### Added
- **CLI Control Port**: HTTP REST API server on port 9019 for protocol testing
  - Allows sending raw hex commands through existing panel connection
  - Endpoints: `/status`, `/connected`, `/command/raw`, `/command/arm`, `/command/disarm`, `/command/stay`, `/command/siren`, `/command/pgm`
- **CLI Tool** (`tools/amt_cli.py`): Command-line tool for testing protocol commands
  - `amt_cli status` - Get panel status
  - `amt_cli raw "41 35" -p 1234` - Send raw hex commands
  - `amt_cli arm -P A --stay` - Test partition stay modes
  - Works with Python stdlib (no external dependencies required)

### Changed
- Internal data structure for storing coordinator and control server

## [1.3.0] - 2025-01-20

### Added
- Partition alarm control panels (A, B, C, D) with code requirement
- All arm/disarm operations now require security code

### Changed
- Partitions are now `alarm_control_panel` entities instead of switches (security improvement)
- Simplified configuration: removed partition password fields (code entered via UI)

### Removed
- `switch.amt_*_armar` - use main alarm panel instead
- `switch.amt_*_particao_X` - use partition alarm panels instead
- Partition password configuration fields

### Security
- All arming/disarming operations now require code entry (following industry standard)

## [1.2.2] - 2025-01-20

### Added
- Code requirement for alarm panel arm/disarm operations

### Security
- Alarm panel now requires numeric code to arm/disarm

## [1.2.1] - 2025-01-20

### Fixed
- TRIGGERED state now only shows when siren is on OR (alarm is armed AND triggered bit is set)
- Previously showed TRIGGERED incorrectly when disarmed due to zone violation memory

## [1.2.0] - 2025-01-20

### Changed
- **Breaking**: Switched from client mode to server mode
  - Home Assistant now listens on port 9009
  - AMT panel connects TO Home Assistant (not the other way around)
- Default port changed from 9015 to 9009
- Removed host configuration (not needed in server mode)

### Fixed
- Protocol password encoding (now ASCII)
- Checksum calculation (XOR with 0xFF)
- Status command changed to 0x5B for full status response

## [1.1.0] - 2025-01-19

### Added
- Siren switch control
- PGM switches 1-19
- Partition switches A/B/C/D
- Zone tamper sensors (1-18)
- Zone short-circuit sensors (1-18)
- Zone low battery sensors (1-40)
- Detailed problem binary sensors
- Zone count sensors

## [1.0.0] - 2025-01-18

### Added
- Initial release
- Alarm control panel with arm/disarm
- Zone binary sensors (open, violated, bypassed)
- Basic status sensors
- PGM buttons
- Bypass open zones button