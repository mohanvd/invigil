# Invigil sensor unit firmware: Raspberry Pi Pico 2 W, official Pico SDK, C.
# Build with the Raspberry Pi Pico VS Code extension (docs/firmware.md), or:
#   cmake -S firmware -B firmware/build -DPICO_SDK_PATH=/path/to/pico-sdk
#   cmake --build firmware/build
# Output: firmware/build/invigil.uf2

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Pinned versions. CI reads sdkVersion and toolchainVersion from these lines.
# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.3.1)
set(toolchainVersion 15_2_Rel1)
set(picotoolVersion 2.3.1)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
set(PICO_BOARD pico2_w CACHE STRING "Board type")

if(NOT PICO_BOARD STREQUAL "pico2_w")
    message(FATAL_ERROR "Invigil runs on the Raspberry Pi Pico 2 W only (PICO_BOARD pico2_w), not ${PICO_BOARD}")
endif()

if(NOT EXISTS ${CMAKE_CURRENT_LIST_DIR}/secrets.h)
    message(FATAL_ERROR
        "firmware/secrets.h is missing.\n"
        "Copy firmware/secrets.h.example to firmware/secrets.h and fill it in (see docs/firmware.md).")
endif()

include(pico_sdk_import.cmake)

project(invigil_fw VERSION 0.1.1 LANGUAGES C CXX ASM)

pico_sdk_init()

if(NOT PICO_SDK_VERSION_STRING STREQUAL sdkVersion)
    message(WARNING "Building with Pico SDK ${PICO_SDK_VERSION_STRING}, but the firmware is pinned to ${sdkVersion}")
endif()

set(INVIGIL_SOURCES
    src/main.c
    src/ble_scan.c
    src/mqtt_link.c
    src/nrf_scan.c
    src/wifi_sta.c
    portable/addr_hash.c
    portable/adv_data.c
    portable/ble_ring.c
    portable/nrf24.c
    portable/payload.c
    portable/sha256.c
    portable/spectrum.c
)

add_executable(invigil ${INVIGIL_SOURCES})

pico_set_program_name(invigil "invigil")
pico_set_program_version(invigil "${PROJECT_VERSION}")

target_compile_definitions(invigil PRIVATE
    INVIGIL_FW_VERSION="${PROJECT_VERSION}"
)

# secrets.h, then lwipopts.h and btstack_config.h, which the SDK libraries
# look for on the include path.
target_include_directories(invigil PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}
    ${CMAKE_CURRENT_LIST_DIR}/src
    ${CMAKE_CURRENT_LIST_DIR}/portable
)

# Warnings for this project's files only, not the SDK's.
set_source_files_properties(${INVIGIL_SOURCES} PROPERTIES COMPILE_OPTIONS "-Wall;-Wextra")

target_link_libraries(invigil
    pico_stdlib
    pico_cyw43_arch_lwip_threadsafe_background
    pico_btstack_ble
    pico_btstack_cyw43
    pico_lwip_mqtt
    pico_lwip_sntp
    hardware_spi
    hardware_watchdog
)

# Log on USB serial, not UART.
pico_enable_stdio_usb(invigil 1)
pico_enable_stdio_uart(invigil 0)

pico_add_extra_outputs(invigil)
