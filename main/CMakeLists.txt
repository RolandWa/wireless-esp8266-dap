set(COMPONENT_ADD_INCLUDEDIRS "${PROJECT_PATH}")
set(COMPONENT_SRCS
    main.c timer.c tcp_server.c usbip_server.c DAP_handle.c
    uart_bridge.c wifi_handle.c)

# VTarget PWM is only for ESP32-C3/ESP32-S3 XIAO boards
if(IDF_TARGET STREQUAL "esp32c3" OR IDF_TARGET STREQUAL "esp32s3")
    list(APPEND COMPONENT_SRCS "uart_bridge.c" "DAP_handle.c" "vtarget_pwm.c")
endif()

if(CONFIG_USE_WEBSOCKET_DAP)
    list(APPEND COMPONENT_SRCS "websocket_server.c")
endif()

register_component()
