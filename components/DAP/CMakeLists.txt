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

# ESP32/ESP32-C3/ESP32-S3 need esp_adc_cal for VTarget sensing
# ESP8266 doesn't have this component, so conditionally add it
if(IDF_TARGET STREQUAL "esp32" OR IDF_TARGET STREQUAL "esp32c3" OR IDF_TARGET STREQUAL "esp32s3")
    set(COMPONENT_REQUIRES esp_adc_cal driver)
else()
    set(COMPONENT_REQUIRES driver)
endif()

register_component()