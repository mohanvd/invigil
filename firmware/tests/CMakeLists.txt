# Host tests for firmware/portable, built with the PC's own C compiler.
# No Pico SDK needed. From the repo root:
#   cmake -S firmware/tests -B firmware/build/tests
#   cmake --build firmware/build/tests
#   ctest --test-dir firmware/build/tests --output-on-failure
#   python firmware/tests/check_contract.py firmware/build/tests/samples.tsv

cmake_minimum_required(VERSION 3.13)
project(invigil_host_tests C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

option(INVIGIL_SANITIZE "Build the host tests with AddressSanitizer and UBSan (GCC or Clang)" OFF)

set(PORTABLE_DIR ${CMAKE_CURRENT_LIST_DIR}/../portable)

add_executable(test_portable
    test_portable.c
    ${PORTABLE_DIR}/addr_hash.c
    ${PORTABLE_DIR}/adv_data.c
    ${PORTABLE_DIR}/ble_ring.c
    ${PORTABLE_DIR}/nrf24.c
    ${PORTABLE_DIR}/payload.c
    ${PORTABLE_DIR}/sha256.c
    ${PORTABLE_DIR}/spectrum.c
)
target_include_directories(test_portable PRIVATE ${PORTABLE_DIR})

if(MSVC)
    target_compile_options(test_portable PRIVATE /W4 /WX)
    target_compile_definitions(test_portable PRIVATE _CRT_SECURE_NO_WARNINGS)
else()
    target_compile_options(test_portable PRIVATE -Wall -Wextra -Wpedantic -Werror)
    if(INVIGIL_SANITIZE)
        target_compile_options(test_portable PRIVATE -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer)
        target_link_options(test_portable PRIVATE -fsanitize=address,undefined)
    endif()
endif()

enable_testing()
add_test(NAME portable COMMAND test_portable ${CMAKE_CURRENT_BINARY_DIR}/samples.tsv)
