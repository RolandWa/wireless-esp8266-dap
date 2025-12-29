set(COMPONENT_ADD_INCLUDEDIRS "config include $ENV{IDF_PATH}/components/esp_ringbuf/include/ $ENV{IDF_PATH}/components/")
set(COMPONENT_SRCS
    "./source/DAP.c"
    "./source/DAP_vendor.c"
    "./source/JTAG_DP.c"
    "./source/SW_DP.c"
    "./source/SWO.c"
    "./source/spi_op.c"
    "./source/spi_switch.c"
    "./source/dap_utility.c"
    "./source/swd_host.c")

# UART.c only for ESP32-C3 and ESP32-S3 (not available on ESP8266 and original ESP32)
if(IDF_TARGET STREQUAL "esp32c3" OR IDF_TARGET STREQUAL "esp32s3")
    list(APPEND COMPONENT_SRCS "./source/UART.c")
endif()

# ESP32/ESP32-C3/ESP32-S3 need esp_adc_cal for VTarget sensing
# ESP8266 doesn't need explicit component requirements
if(IDF_TARGET STREQUAL "esp32" OR IDF_TARGET STREQUAL "esp32c3" OR IDF_TARGET STREQUAL "esp32s3")
    set(COMPONENT_REQUIRES esp_adc_cal driver)
endif()

register_component()