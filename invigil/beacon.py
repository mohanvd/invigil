"""Broadcast the broker beacon, so the unit finds the laptop by itself.

Once a second, on every network the laptop is on, one UDP datagram goes to the
broadcast address on port 18830:

    invigil broker <mqtt port> <tag>

The unit listens for it, checks the tag, and connects to the address the
datagram came from. The laptop's IP address can then change freely, as it does
on a phone hotspot.

tag is the first 16 hex chars of HMAC-SHA256 with the hash salt as the key and
"invigil broker <mqtt port> <laptop IPv4>" as the message. The unit computes
the same thing from the sender address it sees, so another device that copies
the beacon cannot point the unit at itself. firmware/portable/beacon.c is the
unit's side.

The launcher starts this with the broker and stops it with the rest:
    python -m invigil.beacon
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import socket
import sys
import time

from invigil import broker
from server.config import load_config

UDP_PORT = 18830
PERIOD_S = 1.0
PREFIX = "invigil broker"
TAG_LEN = 16
BROADCAST = "255.255.255.255"


def tag(salt: str, mqtt_port: int, ip: str) -> str:
    message = f"{PREFIX} {mqtt_port} {ip}".encode()
    return hmac.new(salt.encode("utf-8"), message, hashlib.sha256).hexdigest()[:TAG_LEN]


def payload(salt: str, mqtt_port: int, ip: str) -> bytes:
    """The datagram the laptop sends from the address ip."""
    return f"{PREFIX} {mqtt_port} {tag(salt, mqtt_port, ip)}".encode()


def usable(ip: str) -> bool:
    """True for an address a unit could reach: not loopback, not self-assigned."""
    try:
        addr = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    return not (addr.is_loopback or addr.is_link_local or addr.is_unspecified or addr.is_multicast)


def local_ipv4() -> list[str]:
    """The laptop's IPv4 addresses, one per network it is on."""
    found: list[str] = []
    try:
        found += socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        pass
    # The address of the default route. Connecting a UDP socket sends nothing.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            found.append(s.getsockname()[0])
    except OSError:
        pass
    return sorted({ip for ip in found if usable(ip)})


def send_once(
    salt: str, mqtt_port: int, ips: list[str], udp_port: int = UDP_PORT, dest: str = BROADCAST
) -> list[str]:
    """Send one beacon from each address. Returns the addresses it went out from."""
    sent = []
    for ip in ips:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                # Binding to the address picks the network the broadcast goes out on.
                s.bind((ip, 0))
                s.sendto(payload(salt, mqtt_port, ip), (dest, udp_port))
            sent.append(ip)
        except OSError:
            pass  # that network just went away; it is looked up again next time
    return sent


def run(salt: str, mqtt_port: int, period_s: float = PERIOD_S) -> None:
    last: list[str] | None = None
    while True:
        sent = send_once(salt, mqtt_port, local_ipv4())
        if sent != last:
            where = ", ".join(sent) if sent else "nowhere: the laptop has no network address"
            print(f"beacon: UDP port {UDP_PORT}, MQTT port {mqtt_port}, from {where}", flush=True)
            last = sent
        time.sleep(period_s)


def main() -> int:
    cfg = load_config()
    if not cfg.hash_salt:
        print("beacon: hash_salt in server/config.toml is empty. The beacon is signed with it.")
        return 1
    try:
        run(cfg.hash_salt, broker.MQTT_PORT)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
