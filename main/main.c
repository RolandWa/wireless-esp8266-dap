/* BSD Socket API Example

   This example code is in the Public Domain (or CC0 licensed, at your option.)

   Unless required by applicable law or agreed to in writing, this
   software is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
   CONDITIONS OF ANY KIND, either express or implied.
*/
#include <string.h>
#include <stdint.h>
#include <sys/param.h>

#include "sdkconfig.h"
#include "main/tcp_server.h"
#include "main/tcp_netconn.h"
#include "main/kcp_server.h"
#include "main/uart_bridge.h"
#include "main/timer.h"
#include "main/wifi_configuration.h"
#include "main/wifi_handle.h"
#include "main/vtarget_pwm.h"

#if defined(CONFIG_IDF_TARGET_ESP32C3) || defined(CONFIG_IDF_TARGET_ESP32S3)
void vtarget_log_boot_reading(void);
uint16_t vtarget_read_mv_public(void);
#endif

#include "components/corsacOTA/src/corsacOTA.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event_loop.h"
#include "esp_log.h"
#include "nvs_flash.h"

#include "lwip/err.h"
#include "lwip/sockets.h"
#include "lwip/sys.h"
#include <lwip/netdb.h>

#include "mdns.h"
#include "driver/uart.h"
#include "esp_heap_caps.h"
#include "esp_netif.h"

extern void DAP_Setup(void);
extern void DAP_Thread(void *argument);
extern void SWO_Thread();

static const char *DBG_TAG = "debug";

static void print_debug_status(void) {
    // Free heap
    uint32_t free_heap = esp_get_free_heap_size();

    // WiFi RSSI and IP
    wifi_ap_record_t ap_info;
    char ip_str[16] = "0.0.0.0";
    int8_t rssi = 0;
    if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
        rssi = ap_info.rssi;
    }
    esp_netif_ip_info_t ip_info;
    esp_netif_t *netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (netif && esp_netif_get_ip_info(netif, &ip_info) == ESP_OK) {
        snprintf(ip_str, sizeof(ip_str), IPSTR, IP2STR(&ip_info.ip));
    }

#if defined(CONFIG_IDF_TARGET_ESP32C3) || defined(CONFIG_IDF_TARGET_ESP32S3)
    uint16_t vtref_mv = vtarget_read_mv_public();
    if (vtref_mv == 0xFFFF)
        ESP_LOGI(DBG_TAG, "--- STATUS --- IP:%s  RSSI:%ddBm  VTref:ERR  Heap:%"PRIu32"B",
                 ip_str, rssi, free_heap);
    else
        ESP_LOGI(DBG_TAG, "--- STATUS --- IP:%s  RSSI:%ddBm  VTref:%dmV(%.2fV)  Heap:%"PRIu32"B",
                 ip_str, rssi, vtref_mv, vtref_mv / 1000.0f, free_heap);
#else
    ESP_LOGI(DBG_TAG, "--- STATUS --- IP:%s  RSSI:%ddBm  Heap:%"PRIu32"B",
             ip_str, rssi, free_heap);
#endif
}

static void print_help(void) {
    ESP_LOGI(DBG_TAG, "=== UART Debug Commands ===");
    ESP_LOGI(DBG_TAG, "  v - Read VTref voltage");
    ESP_LOGI(DBG_TAG, "  s - Print full status");
    ESP_LOGI(DBG_TAG, "  h - Print this help");
    ESP_LOGI(DBG_TAG, "  r - Reboot device");
    ESP_LOGI(DBG_TAG, "===========================");
}

static void debug_task(void *arg) {
    // Configure UART0 for command input (same port as serial monitor)
    uart_config_t uart_cfg = {
        .baud_rate  = 115200,
        .data_bits  = UART_DATA_8_BITS,
        .parity     = UART_PARITY_DISABLE,
        .stop_bits  = UART_STOP_BITS_1,
        .flow_ctrl  = UART_HW_FLOWCTRL_DISABLE,
    };
    uart_param_config(UART_NUM_0, &uart_cfg);
    uart_driver_install(UART_NUM_0, 256, 0, 0, NULL, 0);

    ESP_LOGI(DBG_TAG, "Debug task started. Press 'h' for commands.");
    print_help();

    TickType_t last_status = xTaskGetTickCount();
    const TickType_t STATUS_INTERVAL = pdMS_TO_TICKS(5000); // 5s periodic

    while (1) {
        // Periodic status log
        if ((xTaskGetTickCount() - last_status) >= STATUS_INTERVAL) {
            print_debug_status();
            last_status = xTaskGetTickCount();
        }

        // Check for UART command
        uint8_t cmd;
        int len = uart_read_bytes(UART_NUM_0, &cmd, 1, pdMS_TO_TICKS(100));
        if (len > 0) {
            switch (cmd) {
                case 'v': case 'V':
#if defined(CONFIG_IDF_TARGET_ESP32C3) || defined(CONFIG_IDF_TARGET_ESP32S3)
                    {
                        uint16_t mv = vtarget_read_mv_public();
                        if (mv == 0xFFFF)
                            ESP_LOGI(DBG_TAG, "VTref: ADC read error");
                        else
                            ESP_LOGI(DBG_TAG, "VTref: %d mV (%.3f V)", mv, mv / 1000.0f);
                    }
#else
                    ESP_LOGI(DBG_TAG, "VTref sensing not supported on this target");
#endif
                    break;
                case 's': case 'S':
                    print_debug_status();
                    break;
                case 'h': case 'H': case '?':
                    print_help();
                    break;
                case 'r': case 'R':
                    ESP_LOGW(DBG_TAG, "Rebooting...");
                    vTaskDelay(pdMS_TO_TICKS(200));
                    esp_restart();
                    break;
                default:
                    break;
            }
        }
    }
}

TaskHandle_t kDAPTaskHandle = NULL;

static const char *MDNS_TAG = "server_common";

#if defined(CONFIG_IDF_TARGET_ESP32S3)
#define DAP_TASK_AFFINITY 1
#else
#define DAP_TASK_AFFINITY 0
#endif

void mdns_setup() {
    // initialize mDNS
    int ret;
    ret = mdns_init();
    if (ret != ESP_OK) {
        ESP_LOGW(MDNS_TAG, "mDNS initialize failed:%d", ret);
        return;
    }

    // set mDNS hostname
    ret = mdns_hostname_set(MDNS_HOSTNAME);
    if (ret != ESP_OK) {
        ESP_LOGW(MDNS_TAG, "mDNS set hostname failed:%d", ret);
        return;
    }
    ESP_LOGI(MDNS_TAG, "mDNS hostname set to: [%s]", MDNS_HOSTNAME);

    // set default mDNS instance name
    ret = mdns_instance_name_set(MDNS_INSTANCE);
    if (ret != ESP_OK) {
        ESP_LOGW(MDNS_TAG, "mDNS set instance name failed:%d", ret);
        return;
    }
    ESP_LOGI(MDNS_TAG, "mDNS instance name set to: [%s]", MDNS_INSTANCE);
}

void app_main() {
    // struct rst_info *rtc_info = system_get_rst_info();

    // os_printf("reset reason: %x\n", rtc_info->reason);

    // if (rtc_info->reason == REASON_WDT_RST ||
    //     rtc_info->reason == REASON_EXCEPTION_RST ||
    //     rtc_info->reason == REASON_SOFT_WDT_RST)
    // {
    // if (rtc_info->reason == REASON_EXCEPTION_RST)
    // {
    //     os_printf("Fatal exception (%d):\n", rtc_info->exccause);
    // }
    // os_printf("epc1=0x%08x, epc2=0x%08x, epc3=0x%08x,excvaddr=0x%08x, depc=0x%08x\n",
    //             rtc_info->epc1, rtc_info->epc2, rtc_info->epc3,
    //             rtc_info->excvaddr, rtc_info->depc);
    // }

    ESP_ERROR_CHECK(nvs_flash_init());

#if (USE_UART_BRIDGE == 1)
    uart_bridge_init();
#endif
    wifi_init();
    DAP_Setup();
    timer_init();

#if defined(CONFIG_IDF_TARGET_ESP32C3)
    // Initialize VTarget PWM control (GPIO3)
    ESP_ERROR_CHECK(vtarget_pwm_init());
    // Set default VTarget to 3.3V
    vtarget_set_voltage(3300);
    vtarget_log_boot_reading();
#endif

#if (USE_MDNS == 1)
    mdns_setup();
#endif


#if (USE_OTA == 1)
    co_handle_t handle;
    co_config_t config = {
        .thread_name = "corsacOTA",
        .stack_size = 3192,
        .thread_prio = 8,
        .listen_port = 3241,
        .max_listen_num = 2,
        .wait_timeout_sec = 60,
        .wait_timeout_usec = 0,
    };

    corsacOTA_init(&handle, &config);
#endif

    // Specify the usbip server task
#if (USE_TCP_NETCONN == 1)
    xTaskCreatePinnedToCore(tcp_netconn_task, "tcp_server", 4096, NULL, 14, NULL, DAP_TASK_AFFINITY);
#else // BSD style
    xTaskCreatePinnedToCore(tcp_server_task, "tcp_server", 4096, NULL, 14, NULL,
                            DAP_TASK_AFFINITY);
#endif

    // DAP handle task
    xTaskCreatePinnedToCore(DAP_Thread, "DAP_Task", 2048, NULL, 10, &kDAPTaskHandle,
                            DAP_TASK_AFFINITY);

#if defined CONFIG_IDF_TARGET_ESP8266
    #define UART_BRIDGE_TASK_STACK_SIZE 2048  // Increased from 1024 to prevent stack overflow
#else
    #define UART_BRIDGE_TASK_STACK_SIZE 2048
#endif

#if (USE_UART_BRIDGE == 1)
    xTaskCreate(uart_bridge_task, "uart_server", UART_BRIDGE_TASK_STACK_SIZE, NULL, 2, NULL);
#endif

    // Debug status task — logs every 5s, accepts UART commands on COM12
    xTaskCreate(debug_task, "debug", 3072, NULL, 3, NULL);
}
