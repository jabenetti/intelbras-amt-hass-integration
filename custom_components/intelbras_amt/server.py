"""AMT TCP server for receiving connections from alarm panels."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable
from datetime import datetime, timedelta, timezone

from .const import (
    CMD_ARM,
    CMD_ARM_PARTITION_A,
    CMD_ARM_PARTITION_B,
    CMD_ARM_PARTITION_C,
    CMD_ARM_PARTITION_D,
    CMD_BYPASS,
    CMD_CONNECTION_INFO,
    CMD_CONTACTID_EVENT,
    CMD_CONTACTID_EVENT_DATETIME,
    CMD_CONTACTID_EVENT_PICTURE,
    CMD_DATETIME,
    CMD_DISARM,
    CMD_DISARM_PARTITION_A,
    CMD_DISARM_PARTITION_B,
    CMD_DISARM_PARTITION_C,
    CMD_DISARM_PARTITION_D,
    CMD_PGM_OFF_PREFIX,
    CMD_PGM_ON_PREFIX,
    CMD_SIREN_OFF,
    CMD_SIREN_ON,
    CMD_STAY,
    CMD_STAY_PARTITION_A,
    CMD_STAY_PARTITION_B,
    CMD_STAY_PARTITION_C,
    CMD_STAY_PARTITION_D,
    CMD_STATUS_5A,
    CMD_STATUS_5B,
    DATA_AC_POWER,
    DATA_ARMED,
    DATA_AUX_OVERLOAD,
    DATA_BATTERY_ABSENT,
    DATA_BATTERY_CONNECTED,
    DATA_BATTERY_LEVEL,
    DATA_BATTERY_LOW,
    DATA_BATTERY_SHORT,
    DATA_COMM_FAILURE,
    DATA_CONNECTED,
    DATA_DATETIME,
    DATA_FIRMWARE,
    DATA_MAX_ZONES,
    DATA_MODEL_ID,
    DATA_MODEL_NAME,
    DATA_PARTITIONS,
    DATA_PGMS,
    DATA_PHONE_LINE_CUT,
    DATA_PROBLEM,
    DATA_SIREN,
    DATA_SIREN_SHORT,
    DATA_SIREN_WIRE_CUT,
    DATA_STAY,
    DATA_TRIGGERED,
    DATA_ZONES_BYPASSED,
    DATA_ZONES_BYPASSED_COUNT,
    DATA_ZONES_LOW_BATTERY,
    DATA_ZONES_OPEN,
    DATA_ZONES_OPEN_COUNT,
    DATA_ZONES_SHORT_CIRCUIT,
    DATA_ZONES_TAMPER,
    DATA_ZONES_VIOLATED,
    DATA_ZONES_VIOLATED_COUNT,
    DEFAULT_SERVER_HOST,
    FRAME_ACK,
    FRAME_HEARTBEAT,
    FRAME_SEPARATOR,
    FRAME_START,
    MAX_PGMS,
    MAX_ZONES,
    MAX_ZONES_LOW_BATTERY,
    MAX_ZONES_SHORT_CIRCUIT,
    MAX_ZONES_TAMPER,
    MODEL_ID,
    MODEL_NAMES,
    NACK_MESSAGES,
    RESPONSE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class AMTServerError(Exception):
    """Base exception for AMT server errors."""


class AMTConnectionError(AMTServerError):
    """Connection error."""


class AMTProtocolError(AMTServerError):
    """Protocol error."""


class AMTNackError(AMTServerError):
    """NACK response received from the alarm panel."""

    def __init__(self, nack_code: int, message: str | None = None) -> None:
        """Initialize the NACK error."""
        self.nack_code = nack_code
        self.message = message or NACK_MESSAGES.get(nack_code, f"Erro desconhecido (0x{nack_code:02X})")
        super().__init__(self.message)


class AMTConnection:
    """Represents a connection from an AMT panel."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        address: tuple[str, int],
    ) -> None:
        """Initialize the connection."""
        self.reader = reader
        self.writer = writer
        self.address = address
        self.account: str | None = None
        self.mac_suffix: str | None = None
        self.panel_model: int | None = None
        self.pending_response: asyncio.Future | None = None
        self.last_heartbeat: float = 0
        self._lock = asyncio.Lock()

    @property
    def id(self) -> str:
        """Return connection identifier."""
        return f"{self.address[0]}:{self.address[1]}"

    async def close(self) -> None:
        """Close the connection."""
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass


class AMTServer:
    """AMT TCP server that accepts connections from alarm panels."""

    def __init__(
        self,
        port: int,
        password: str,
        host: str = DEFAULT_SERVER_HOST,
    ) -> None:
        """Initialize the AMT server."""
        self._host = host
        self._port = port
        self._password = password
        self._server: asyncio.Server | None = None
        self._connection: AMTConnection | None = None
        self._running = False
        self._lock = asyncio.Lock()
        self._partition_passwords: dict[str, str] = {}
        self._status_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self._last_status: dict[str, Any] | None = None

    def set_partition_passwords(
        self,
        password_a: str | None = None,
        password_b: str | None = None,
        password_c: str | None = None,
        password_d: str | None = None,
    ) -> None:
        """Set partition passwords."""
        if password_a:
            self._partition_passwords["A"] = password_a
        if password_b:
            self._partition_passwords["B"] = password_b
        if password_c:
            self._partition_passwords["C"] = password_c
        if password_d:
            self._partition_passwords["D"] = password_d

    def set_status_callback(
        self, callback: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Set callback for status updates."""
        self._status_callback = callback

    @property
    def connected(self) -> bool:
        """Return True if a panel is connected."""
        return self._connection is not None

    @property
    def last_status(self) -> dict[str, Any] | None:
        """Return the last received status."""
        return self._last_status

    async def start(self) -> None:
        """Start the TCP server."""
        if self._running:
            return

        self._server = await asyncio.start_server(
            self._handle_client,
            self._host,
            self._port,
            reuse_address=True,
        )

        self._running = True
        _LOGGER.info("AMT server started on %s:%s", self._host, self._port)

    async def stop(self) -> None:
        """Stop the TCP server."""
        self._running = False

        if self._connection:
            await self._connection.close()
            self._connection = None

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        _LOGGER.info("AMT server stopped")

    def _calculate_checksum(self, data: bytes) -> int:
        """Calculate XOR checksum for the frame (XOR all bytes, then XOR with 0xFF)."""
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum ^ 0xFF

    def _build_frame(self, command: bytes, password: str | None = None) -> bytes:
        """Build a protocol frame with checksum."""
        pwd = password or self._password
        # Password is sent as ASCII characters
        pwd_bytes = pwd.encode('ascii')

        # Frame: [Length] [0xE9] [0x21] [PASSWORD_ASCII] [COMMAND] [0x21] [CHECKSUM]
        inner = bytes([FRAME_START, FRAME_SEPARATOR]) + pwd_bytes + command + bytes([FRAME_SEPARATOR])

        # Length = command byte + content (not including length byte and checksum)
        length = len(inner)

        frame_without_checksum = bytes([length]) + inner
        checksum = self._calculate_checksum(frame_without_checksum)
        return frame_without_checksum + bytes([checksum])

    def _build_ack_frame(self) -> bytes:
        """Build a simple ACK frame."""
        # ACK frame: [02] [FE] [checksum]
        frame = bytes([0x01, FRAME_ACK])
        checksum = self._calculate_checksum(frame)
        return frame + bytes([checksum])

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle incoming client connection."""
        addr = writer.get_extra_info('peername')
        _LOGGER.info("Panel connected from %s:%s", addr[0], addr[1])

        # Close existing connection if any
        if self._connection:
            _LOGGER.warning("Closing existing connection from %s", self._connection.id)
            await self._connection.close()

        connection = AMTConnection(reader, writer, addr)
        self._connection = connection

        try:
            buffer = bytearray()
            while self._running:
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=60)
                    if not data:
                        break

                    buffer.extend(data)
                    _LOGGER.debug("Received data: %s", data.hex())

                    # Process complete frames from buffer
                    while len(buffer) > 0:
                        frame = self._extract_frame(buffer)
                        if frame is None:
                            break
                        await self._process_frame(connection, frame)

                except asyncio.TimeoutError:
                    # No data for 60 seconds, but connection still valid
                    continue

        except Exception as e:
            _LOGGER.error("Error handling client: %s", e)
        finally:
            if self._connection == connection:
                self._connection = None
            await connection.close()
            _LOGGER.info("Panel disconnected from %s:%s", addr[0], addr[1])

    def _extract_frame(self, buffer: bytearray) -> bytes | None:
        """Extract a complete frame from the buffer."""
        if len(buffer) < 1:
            return None

        # Check for heartbeat (single byte 0xF7)
        if buffer[0] == FRAME_HEARTBEAT:
            frame = bytes([buffer.pop(0)])
            return frame

        # Normal frame: first byte is length
        if len(buffer) < 3:
            return None

        length = buffer[0]
        total_size = length + 2  # length byte + content + checksum

        if len(buffer) < total_size:
            return None

        frame = bytes(buffer[:total_size])
        del buffer[:total_size]

        # Validate checksum
        if not self._validate_checksum(frame):
            _LOGGER.warning("Invalid checksum in frame: %s", frame.hex())
            return None

        return frame

    def _validate_checksum(self, frame: bytes) -> bool:
        """Validate frame checksum."""
        if len(frame) < 2:
            return False
        data = frame[:-1]
        expected = self._calculate_checksum(data)
        return frame[-1] == expected

    async def _process_frame(self, connection: AMTConnection, frame: bytes) -> None:
        """Process a received frame."""
        # Heartbeat
        if len(frame) == 1 and frame[0] == FRAME_HEARTBEAT:
            _LOGGER.debug("Heartbeat received, sending ACK")
            ack = self._build_ack_frame()
            connection.writer.write(ack)
            await connection.writer.drain()
            connection.last_heartbeat = asyncio.get_event_loop().time()
            return

        if len(frame) < 3:
            return

        command = frame[1]
        content = frame[2:-1] if len(frame) > 3 else bytes()

        _LOGGER.debug("Frame: cmd=0x%02X, content=%s", command, content.hex())

        # Connection info (0x94) - panel identifying itself
        if command == CMD_CONNECTION_INFO:
            await self._handle_connection_info(connection, content)
            return
        elif command == CMD_DATETIME:
            await self._handle_datetime(connection, content)
            return

        # Check if this is a response to a pending command
        if connection.pending_response and not connection.pending_response.done():
            connection.pending_response.set_result(frame)
            return
        
        # Contact_ID events (0xB0, 0xB4, 0xB5)
        if command in (CMD_CONTACTID_EVENT, CMD_CONTACTID_EVENT_DATETIME, CMD_CONTACTID_EVENT_PICTURE):
            _LOGGER.info("Contact ID event received: cmd=0x%02X, content=%s", command, content.hex())
            ack = self._build_ack_frame()
            connection.writer.write(ack)
            await connection.writer.drain()

        # ISECMobile frame (0xE9) - could be unsolicited status
        if command == FRAME_START:
            # This might be a status update or response
            _LOGGER.debug("ISECMobile frame received: %s", content.hex())

    async def _handle_connection_info(
        self, connection: AMTConnection, content: bytes
    ) -> None:
        """Handle connection info command (0x94)."""
        # Parse account and MAC from content if available
        if len(content) >= 4:
            connection.account = content[:4].decode('ascii', errors='replace')
        if len(content) >= 10:
            connection.mac_suffix = content[4:10].hex()

        _LOGGER.info(
            "Panel identified: account=%s, mac=%s",
            connection.account,
            connection.mac_suffix,
        )

        # Send ACK
        ack = self._build_ack_frame()
        connection.writer.write(ack)
        await connection.writer.drain()

    async def _handle_datetime(
            self, connection: AMTConnection, content: bytes
    ) -> None:
        """Handle date/time request (0x80)."""
        tz_offset_hours = content[0] if len(content) > 0 else 0
        utc_now = datetime.now(timezone.utc)
        local_dt = utc_now - timedelta(hours=tz_offset_hours)
        day = local_dt.day
        month = local_dt.month
        year_byte = local_dt.year % 100
        # Sunday=1, Monday=2, ..., Saturday=7
        # Python isoweekday(): Mon=1 ... Sun=7 -> ( % 7 ) + 1 -> Sun=1, Mon=2, ...
        weekday = (local_dt.isoweekday() % 7) + 1
        hour = local_dt.hour
        minute = local_dt.minute
        second = local_dt.second
        response_content = bytes([0x80, day, month, year_byte, weekday, hour, minute, second])
        length = len(response_content)  # 8
        frame_no_checksum = bytes([length]) + response_content
        checksum = self._calculate_checksum(frame_no_checksum)
        response_frame = frame_no_checksum + bytes([checksum])
        connection.writer.write(response_frame)
        await connection.writer.drain()
        _LOGGER.debug("Date/time response sent (tz_offset_hours=%d)", tz_offset_hours)

    async def _send_command(self, command: bytes, password: str | None = None) -> bytes:
        """Send a command and wait for response."""
        if not self._connection:
            raise AMTConnectionError("No panel connected")

        async with self._connection._lock:
            frame = self._build_frame(command, password)
            _LOGGER.debug("Sending command: %s", frame.hex())

            # Set up response future
            self._connection.pending_response = asyncio.get_event_loop().create_future()

            try:
                self._connection.writer.write(frame)
                await self._connection.writer.drain()

                # Wait for response
                response = await asyncio.wait_for(
                    self._connection.pending_response,
                    timeout=RESPONSE_TIMEOUT,
                )
                _LOGGER.debug("Response received: %s", response.hex())

                # Check for NACK
                if len(response) >= 3 and response[1] == FRAME_START:
                    resp_content = response[2:-1]
                    if len(resp_content) >= 1 and 0xE0 <= resp_content[0] <= 0xEF:
                        raise AMTNackError(resp_content[0])

                return response

            except asyncio.TimeoutError as err:
                raise AMTConnectionError("Response timeout") from err
            finally:
                self._connection.pending_response = None

    def _parse_zones(self, data: bytes, offset: int, length: int) -> list[bool]:
        """Parse zone status bytes into a list of booleans."""
        zones = []
        for byte_idx in range(length):
            if offset + byte_idx >= len(data):
                break
            byte = data[offset + byte_idx]
            for bit in range(8):
                zones.append(bool(byte & (1 << bit)))
        return zones

#        zones = []
#        for byte_idx in range(8):  # 8 bytes = 64 zones max
#            if offset + byte_idx >= len(data):
#                break
#            byte = data[offset + byte_idx]
#            for bit in range(8):
#                zone_num = byte_idx * 8 + bit
#                if zone_num >= max_zones:
#                    break
#                zones.append(bool(byte & (1 << bit)))
#        return zones[:max_zones]

    def _parse_partition_status(self, status_byte: int) -> dict[str, bool]:
        """Parse partition status byte."""
        return {
            "armed": bool(status_byte & 0x01),
            "stay": bool(status_byte & 0x02),
            "triggered": bool(status_byte & 0x04),
        }

    def _parse_response(self, data: bytes) -> dict[str, Any]:
        """Parse status response into structured data."""
        # Response format: [length] [0xE9] [content...] [checksum]
        # Content is the status data (43 bytes for 0x5A command, 54 bytes for 0x5B command)
        if len(data) < 10:
            raise AMTProtocolError(f"Response too short: {len(data)} bytes")

        # Skip length byte, command byte (0xE9), get content excluding checksum
        content = data[2:-1]
        _LOGGER.debug("Parsing status content (%d bytes): %s", len(content), content.hex())

        # For 0x5A response, content is 43 bytes
        # Based on the actual response we received:
        # Bytes 0-5: Zones open (48 zones)
        # Bytes 6-11: Zones violated
        # Bytes 12-17: Zones bypassed (likely)
        # Byte 18: Model ID
        # Byte 19: Firmware version
        # Byte 20: Partitioning enabled (0-1)
        # Byte 21: Active partitions (bit 0=A, bit 1=B)
        # Byte 22: General status
        # Byte 23: Hour
        # Byte 24: Minute
        # Byte 25: Day
        # Byte 26: Month
        # Byte 27: Year (2-digit)
        # Byte 28: Power status
        # Byte 29: BUS errors
        # Byte 30: Battery level
        # Byte 31: Keypad tamper
        # Byte 32: System errors
        # Bytes 33-34: Zones tamper
        # Bytes 35-36: Zones short circuit
        # Byte 37: Siren/PGM status
        # Bytes 38-42: Low battery in wireless sensors

        # For 0x5B response, content is 54 bytes
        # Based on the actual response we received:
        # Bytes 0-7: Zones open (64 zones)
        # Bytes 8-15: Zones violated
        # Bytes 16-23: Zones bypassed (likely)
        # Byte 24: Model ID
        # Byte 25: Firmware version
        # Byte 26: Partitioning enabled (0-1)
        # Byte 27: Active partitions A/B (bit 0=A, bit 1=B)
        # Byte 28: Active partitions C/D (bit 0=C, bit 1=D)
        # Byte 29: General status
        # Byte 30: Hour
        # Byte 31: Minute
        # Byte 32: Day
        # Byte 33: Month
        # Byte 34: Year (2-digit)
        # Byte 35: Power status
        # Bytes 36-39: BUS errors
        # Byte 40: Battery level
        # Byte 41: Keypad tamper
        # Byte 42: System errors
        # Byte 43: Zones tamper
        # Byte 44: Zones short circuit
        # Byte 45: Siren/PGM status
        # Bytes 46-51: Low battery in wireless sensors
        # Bytes 52-53: PGM extender status

        # Identify response type
        short_response = len(content) == 43
        long_response = len(content) == 54
        if not short_response and not long_response:
            raise AMTProtocolError(f"Unexpected response length: {len(content)} bytes")

        # Parse panel model
        model_id = content[18] if short_response else content[24] if long_response else None
        model_name = MODEL_NAMES[model_id]
        if model_id is None:
            raise AMTProtocolError(f"Invalid model number in status response: {len(data)} bytes. HEX: {content.hex}")

        max_zones = MAX_ZONES[model_id]

        # Parse zone lists from content
        zones_open = self._parse_zones(content, 0, 8 if long_response else 6)
        zones_violated = self._parse_zones(content, 8 if long_response else 6, 8 if long_response else 6)
        zones_bypassed = self._parse_zones(content, 16 if long_response else 12, 8 if long_response else 6)

        # Adjust max zones based on model
        zones_open = zones_open[:max_zones]
        zones_violated = zones_violated[:max_zones]
        zones_bypassed = zones_bypassed[:max_zones]

        # Calculate zone counts
        zones_open_count = sum(zones_open)
        zones_violated_count = sum(zones_violated)
        zones_bypassed_count = sum(zones_bypassed)

        # Parse firmware
        firmware_byte = content[25] if long_response else content[19]
        firmware = f"{(firmware_byte >> 4) & 0x0F}.{firmware_byte & 0x0F}"

        # Parse partition status
        part_ab = content[27] if long_response else content[21]
        part_cd = content[28] if long_response else 0
        partitions = {
            "A": self._parse_partition_status(part_ab & 0x0F),
            "B": self._parse_partition_status((part_ab >> 4) & 0x0F),
            "C": self._parse_partition_status(part_cd & 0x0F),
            "D": self._parse_partition_status((part_cd >> 4) & 0x0F),
        }

        # Parse central status
        central_status = content[29] if long_response else content[22]
        armed = bool(central_status & 0x08)
        stay = bool(central_status & 0x10)
        triggered = bool(central_status & 0x04)

        # Parse power/battery status
        power_status = content[35] if long_response else content[28]
        ac_power = bool(power_status & 0x80)
        battery_connected = not bool(power_status & 0x40)
        battery_low = bool(power_status & 0x20)

        # Battery level
        battery_level = content[40] if long_response else content[30]
        if battery_level > 100:
            battery_level = 100

        # PGM/Siren status
        pgm_byte = content[41] if long_response else content[37]
        siren = bool(pgm_byte & 0x04)
        pgms = [False] * MAX_PGMS
        for i in range(min(8, MAX_PGMS)):
            pgms[i] = bool(pgm_byte & (1 << (i + 1))) if i < 7 else False

        # Initialize empty tamper/short-circuit/low-battery arrays
        zones_tamper = [False] * MAX_ZONES_TAMPER
        zones_short_circuit = [False] * MAX_ZONES_SHORT_CIRCUIT
        zones_low_battery = [False] * MAX_ZONES_LOW_BATTERY

        return {
            DATA_CONNECTED: True,
            DATA_MODEL_ID: model_id,
            DATA_MODEL_NAME: model_name,
            DATA_MAX_ZONES: max_zones,
            DATA_FIRMWARE: firmware,
            DATA_ZONES_OPEN: zones_open,
            DATA_ZONES_VIOLATED: zones_violated,
            DATA_ZONES_BYPASSED: zones_bypassed,
            DATA_ZONES_TAMPER: zones_tamper,
            DATA_ZONES_SHORT_CIRCUIT: zones_short_circuit,
            DATA_ZONES_LOW_BATTERY: zones_low_battery,
            DATA_ZONES_OPEN_COUNT: zones_open_count,
            DATA_ZONES_VIOLATED_COUNT: zones_violated_count,
            DATA_ZONES_BYPASSED_COUNT: zones_bypassed_count,
            DATA_PARTITIONS: partitions,
            DATA_ARMED: armed,
            DATA_STAY: stay,
            DATA_TRIGGERED: triggered,
            DATA_AC_POWER: ac_power,
            DATA_BATTERY_CONNECTED: battery_connected,
            DATA_BATTERY_LEVEL: battery_level,
            DATA_SIREN: siren,
            DATA_PGMS: pgms,
            DATA_PROBLEM: battery_low or not battery_connected,
            DATA_BATTERY_LOW: battery_low,
            DATA_BATTERY_ABSENT: not battery_connected,
            DATA_BATTERY_SHORT: False,
            DATA_AUX_OVERLOAD: False,
            DATA_SIREN_WIRE_CUT: False,
            DATA_SIREN_SHORT: False,
            DATA_PHONE_LINE_CUT: False,
            DATA_COMM_FAILURE: False,
            DATA_DATETIME: None,
        }

    async def get_status(self) -> dict[str, Any]:
        """Get current status from the panel."""
        if self.model is None or self._connection.panel_model == MODEL_ID.AMT_2018_E_SMART:
            response = await self._send_command(CMD_STATUS_5A)
        else:
            response = await self._send_command(CMD_STATUS_5B)

        status = self._parse_response(response)
        self._last_status = status
        if self._status_callback:
            await self._status_callback(status)
        return status

    async def arm(self, password: str | None = None) -> None:
        """Arm the alarm panel."""
        await self._send_command(CMD_ARM, password)

    async def disarm(self, password: str | None = None) -> None:
        """Disarm the alarm panel."""
        await self._send_command(CMD_DISARM, password)

    async def arm_stay(self, password: str | None = None) -> None:
        """Arm in stay mode."""
        await self._send_command(CMD_STAY, password)

    async def arm_partition(self, partition: str, password: str | None = None) -> None:
        """Arm a specific partition."""
        commands = {
            "A": CMD_ARM_PARTITION_A,
            "B": CMD_ARM_PARTITION_B,
            "C": CMD_ARM_PARTITION_C,
            "D": CMD_ARM_PARTITION_D,
        }
        if partition not in commands:
            raise ValueError(f"Invalid partition: {partition}")

        pwd = password or self._partition_passwords.get(partition) or self._password
        await self._send_command(commands[partition], pwd)

    async def arm_stay_partition(self, partition: str, password: str | None = None) -> None:
        """Arm a specific partition in stay mode."""
        commands = {
            "A": CMD_STAY_PARTITION_A,
            "B": CMD_STAY_PARTITION_B,
            "C": CMD_STAY_PARTITION_C,
            "D": CMD_STAY_PARTITION_D,
        }
        if partition not in commands:
            raise ValueError(f"Invalid partition: {partition}")

        pwd = password or self._partition_passwords.get(partition) or self._password
        await self._send_command(commands[partition], pwd)

    async def disarm_partition(self, partition: str, password: str | None = None) -> None:
        """Disarm a specific partition."""
        commands = {
            "A": CMD_DISARM_PARTITION_A,
            "B": CMD_DISARM_PARTITION_B,
            "C": CMD_DISARM_PARTITION_C,
            "D": CMD_DISARM_PARTITION_D,
        }
        if partition not in commands:
            raise ValueError(f"Invalid partition: {partition}")

        pwd = password or self._partition_passwords.get(partition) or self._password
        await self._send_command(commands[partition], pwd)

    async def activate_pgm(self, pgm_number: int) -> None:
        """Activate a PGM output."""
        if pgm_number < 1 or pgm_number > MAX_PGMS:
            raise ValueError(f"Invalid PGM number: {pgm_number}")

        if pgm_number < 10:
            command = CMD_PGM_ON_PREFIX + bytes([0x30, 0x30 + pgm_number])
        else:
            command = CMD_PGM_ON_PREFIX + bytes([0x31, 0x30 + (pgm_number - 10)])
        await self._send_command(command)

    async def deactivate_pgm(self, pgm_number: int) -> None:
        """Deactivate a PGM output."""
        if pgm_number < 1 or pgm_number > MAX_PGMS:
            raise ValueError(f"Invalid PGM number: {pgm_number}")

        if pgm_number < 10:
            command = CMD_PGM_OFF_PREFIX + bytes([0x30, 0x30 + pgm_number])
        else:
            command = CMD_PGM_OFF_PREFIX + bytes([0x31, 0x30 + (pgm_number - 10)])
        await self._send_command(command)

    async def siren_on(self) -> None:
        """Turn siren on."""
        await self._send_command(CMD_SIREN_ON)

    async def siren_off(self) -> None:
        """Turn siren off."""
        await self._send_command(CMD_SIREN_OFF)

    async def bypass_zones(self, zone_mask: list[bool]) -> None:
        """Bypass zones specified in the mask."""
        mask_bytes = []
        for i in range(0, len(zone_mask), 8):
            byte = 0
            for bit in range(8):
                if i + bit < len(zone_mask) and zone_mask[i + bit]:
                    byte |= 1 << bit
            mask_bytes.append(byte)

        command = CMD_BYPASS + bytes(mask_bytes)
        await self._send_command(command)

    async def bypass_open_zones(self, open_zones: list[bool]) -> None:
        """Bypass all currently open zones."""
        await self.bypass_zones(open_zones)

    async def test_connection(self) -> bool:
        """Test if a panel is connected and responding."""
        try:
            await self.get_status()
            return True
        except AMTServerError:
            return False

    async def send_raw_command(
        self, command_hex: str, password: str | None = None
    ) -> dict[str, Any]:
        """Send a raw command and return the response.

        Args:
            command_hex: Command as hex string (e.g., "41 35" for partition A stay)
            password: Optional password override

        Returns:
            dict with 'success', 'response_hex', 'error' keys
        """
        try:
            command_bytes = bytes.fromhex(command_hex.replace(" ", ""))
            _LOGGER.info("Sending raw command: %s", command_bytes.hex())
            response = await self._send_command(command_bytes, password)
            _LOGGER.info("Raw command response: %s", response.hex())
            return {
                "success": True,
                "response_hex": response.hex(),
                "response_length": len(response),
            }
        except AMTNackError as e:
            _LOGGER.warning("Raw command NACK: %s (code=0x%02X)", e.message, e.nack_code)
            return {
                "success": False,
                "error": e.message,
                "nack_code": e.nack_code,
            }
        except AMTServerError as e:
            _LOGGER.error("Raw command error: %s", e)
            return {
                "success": False,
                "error": str(e),
            }
