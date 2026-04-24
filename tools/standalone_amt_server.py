#!/usr/bin/env python3
"""
Standalone Intelbras AMT server para pruebas de protocolo.
Replica exactamente el startup y polling de Home Assistant, sin dependencias HA.
Usa importlib para cargar módulos core evitando __init__.py.
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Any

import importlib.util

LOGGER = logging.getLogger(__name__)

def load_core_module(name: str, path: str) -> Any:
    """Carga módulo por path, simulando paquete para imports relativos."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    mod.__package__ = "intelbras_amt"
    spec.loader.exec_module(mod)
    return mod

import os

CORE_DIR = os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'intelbras_amt')

# Cargar en orden: const primero (no deps), luego server (usa .const), control (usa .const .server)
const_mod = load_core_module("intelbras_amt.const", os.path.join(CORE_DIR, "const.py"))
server_mod = load_core_module("intelbras_amt.server", os.path.join(CORE_DIR, "server.py"))
control_mod = load_core_module("intelbras_amt.control_server", os.path.join(CORE_DIR, "control_server.py"))

AMTServer = server_mod.AMTServer
AMTControlServer = control_mod.AMTControlServer

DEFAULT_PORT = const_mod.DEFAULT_PORT
DEFAULT_CONTROL_PORT = const_mod.DEFAULT_CONTROL_PORT
DEFAULT_SCAN_INTERVAL = const_mod.DEFAULT_SCAN_INTERVAL
DEFAULT_SERVER_HOST = const_mod.DEFAULT_SERVER_HOST

async def status_callback(status: dict[str, Any]) -> None:
    """Callback para updates del panel (cambios unsolicited)."""
    print(f"\n[{datetime.now().isoformat()}] UPDATE DEL PANEL:\n{json.dumps(status, indent=2)}\n")

async def poll_loop(server: AMTServer, interval: float) -> None:
    """Polling periódico como en HA coordinator."""
    while True:
        try:
            if server.connected:
                status = await server.get_status()
                print(f"\n[{datetime.now().isoformat()}] POLL STATUS:\n{json.dumps(status, indent=2)}\n")
            else:
                print(f"[{datetime.now().isoformat()}] Panel no conectado")
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Error en poll: {e}")
        await asyncio.sleep(interval)

async def shutdown_servers(server: AMTServer, control: AMTControlServer | None, poll_task: asyncio.Task) -> None:
    """Graceful shutdown."""
    poll_task.cancel()
    try:
        await poll_task
    except asyncio.CancelledError:
        pass
    await server.stop()
    if control:
        await control.stop()
    LOGGER.info("Servidores detenidos")

async def main(args: argparse.Namespace) -> None:
    """Main async."""
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(name)s %(levelname)s: %(message)s")

    LOGGER.info("Iniciando standalone AMT server")

    server = AMTServer(
        port=args.tcp_port,
        password=args.password,
        host=DEFAULT_SERVER_HOST,
    )

    # Partition passwords como en HA
    kwargs = {}
    if args.password_a: kwargs["password_a"] = args.password_a
    if args.password_b: kwargs["password_b"] = args.password_b
    if args.password_c: kwargs["password_c"] = args.password_c
    if args.password_d: kwargs["password_d"] = args.password_d
    if kwargs:
        server.set_partition_passwords(**kwargs)

    server.set_status_callback(status_callback)

    await server.start()
    LOGGER.info("AMT TCP server iniciado en %s:%s", DEFAULT_SERVER_HOST, args.tcp_port)

    control: AMTControlServer | None = None
    if not args.no_http:
        control = AMTControlServer(server, args.control_port)
        await control.start()
        LOGGER.info("Control HTTP iniciado en puerto %s (usa amt_cli.py)", args.control_port)
        print(f"Control HTTP: http://localhost:{args.control_port}")

    print(f"AMT TCP server: {DEFAULT_SERVER_HOST}:{args.tcp_port}")
    print("Esperando conexión del panel de alarma...")
    print(f"Polling cada {args.scan_interval}s. Ctrl+C para detener.")

    poll_task = asyncio.create_task(poll_loop(server, args.scan_interval))

    # Signal handlers
    loop = asyncio.get_running_loop()
    stop_future = asyncio.Future()

    def handle_shutdown():
        stop_future.set_result(None)

    for sig in (signal.SIGTERM, signal.SIGINT):
        if sig == signal.SIGINT or sig == signal.SIGTERM:
            loop.add_signal_handler(sig, handle_shutdown)

    try:
        await stop_future
    finally:
        await shutdown_servers(server, control, poll_task)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Standalone Intelbras AMT server (TCP + HTTP control). Replica HA.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python tools/standalone_amt_server.py --tcp-port 9009 --password 1234
  python tools/standalone_amt_server.py --tcp-port 9009 --password 1234 --no-http --scan-interval 5
  # Test con panel conectado, o amt_cli:
  python tools/amt_cli.py status
        """
    )
    parser.add_argument("--tcp-port", type=int, default=DEFAULT_PORT, help=f"TCP port para panel (default: {DEFAULT_PORT})")
    parser.add_argument("--password", required=True, help="Password principal de la central (obligatorio)")
    parser.add_argument("--control-port", type=int, default=DEFAULT_CONTROL_PORT, help=f"HTTP control port (default: {DEFAULT_CONTROL_PORT})")
    parser.add_argument("--scan-interval", type=float, default=DEFAULT_SCAN_INTERVAL, help=f"Polling intervalo en seg (default: {DEFAULT_SCAN_INTERVAL})")
    parser.add_argument("--no-http", action="store_true", help="No iniciar servidor HTTP control")
    parser.add_argument("--password-a", help="Password partición A")
    parser.add_argument("--password-b", help="Password partición B")
    parser.add_argument("--password-c", help="Password partición C")
    parser.add_argument("--password-d", help="Password partición D")
    parser.add_argument("--verbose", "-v", action="store_true", help="Logging DEBUG")

    args = parser.parse_args()
    asyncio.run(main(args))