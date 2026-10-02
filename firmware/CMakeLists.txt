cmake_minimum_required(VERSION 3.16)

# Firmware version, sent as "fw" in every status message.
set(PROJECT_VER "0.1.0")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(invigil_node)
