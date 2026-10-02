# Firmware plan

The unit firmware is not written yet. This page records the plan.

- Board: Raspberry Pi Pico 2 W (RP2350 + CYW43439 radio).
- Toolchain: the official Pico SDK in C with CMake, built with the Raspberry Pi Pico VS Code extension. The capstone bans Arduino and ESP boards, so the project uses neither, and no Arduino-Pico core.
- BLE: passive scan on the Pico's own radio using BTstack, observer only.
- 2.4 GHz sweep: nRF24L01+PA+LNA on SPI0, 126 channels, RPD hits. Receive only.
- Network: Wi-Fi and MQTT (lwIP MQTT app) to Mosquitto on the laptop, SNTP for timestamps.
- Wi-Fi and Bluetooth share the CYW43 radio, so scan windows and send windows alternate, as the [MQTT contract](contract.md) requires.

Wiring is in the [README](../README.md#hardware).

## Planned modules

| Module | Job |
| --- | --- |
| `ble_scan` | BTstack passive scan, address hashing, boot-time test vector (see [hashing](hashing.md)) |
| `nrf_scan` | nRF24L01 channel sweep, RPD hit counts |
| `mqtt_link` | Broker connection, publishing, status messages |
| `config` | Settings from the gitignored secrets file, timing constants |
| `wifi_sta` | Wi-Fi station and SNTP clock |

## To measure on the real unit

These depend on hardware behavior, so they are tests to run, not numbers to assume:

- How long the scan window and send window should be, and how much quiet time is needed after the last publish before scanning restarts.
- How long one 126-channel sweep takes.
- Whether the unit's own Wi-Fi channel shows hits during scan windows.
- The byte order BTstack uses for addresses (see the [test vector](hashing.md#test-vector)).
