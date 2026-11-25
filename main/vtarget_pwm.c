/**
 * @file vtarget_pwm.c
 * @brief Programmable VTarget voltage control using PWM on GPIO3
 *
 * Controls AP1117-ADJ output voltage (calibrated range 1.326V to 4.200V on the
 * default table) via PWM-controlled MOSFET in the feedback divider network.
 *
 * Circuit topology (values from the KiCad schematic, fitted on all PCBs):
 * - GPIO3 PWM → R4 (22k) → Q1 (YJL2304A MOSFET) Gate
 * - R5 (43k) pull-down on gate
 * - C2 (10uF / 25V) PWM filter: tau ~ (R4||R5)*C2 ~ 145 ms, so the gate is
 *   effectively a DC level and VTarget needs ~0.5-1 s to settle after a change
 * - AP1117-ADJ feedback divider R1 (1.2k) / R3 (2.7k) + Q1 drain-source
 * - R6/R7 (100k each) form the VTref sense divider to GPIO2 (ADC)
 * - C3 (10uF) output capacitor on VTarget
 *
 * Voltage → duty mapping is done by vtarget_cal.c (pure C, unit-tested on the
 * host). Each measured PCB has its own table; the table in use is stored in
 * NVS (namespace "vtarget", key "board") and defaults to CLUSTER.
 */

#include "vtarget_pwm.h"
#include "vtarget_cal.h"
#include "driver/ledc.h"
#include "esp_log.h"
#include "esp_idf_version.h"
#include "esp_timer.h"
#include "nvs.h"
#include <string.h>

static const char *TAG = "vtarget_pwm";

// PWM Configuration for ESP32-C3
#define VTARGET_PWM_TIMER       LEDC_TIMER_0
#define VTARGET_PWM_MODE        LEDC_LOW_SPEED_MODE
#define VTARGET_PWM_CHANNEL     LEDC_CHANNEL_0
#define VTARGET_PWM_GPIO        3                // GPIO3 for VTarget control
#define VTARGET_PWM_FREQUENCY   1000             // 1 kHz
#define VTARGET_PWM_RESOLUTION  LEDC_TIMER_10_BIT // 10-bit (0-1023)
#define VTARGET_PWM_MAX_DUTY    ((1 << 10) - 1)  // 1023

#define VTARGET_NVS_NAMESPACE   "vtarget"
#define VTARGET_NVS_KEY_BOARD   "board"

// Active calibration table, last request and time of the last duty change
static const vtarget_cal_table_t *s_table = NULL;
static uint16_t s_requested_mv = 0;   // 0 = nothing requested via vtarget_set_voltage yet
static int64_t s_last_change_us = 0;

static const vtarget_cal_table_t *active_table(void)
{
    if (s_table == NULL) {
        s_table = vtarget_cal_default();
    }
    return s_table;
}

static void mark_changed(void)
{
    s_last_change_us = esp_timer_get_time();
}

/** Read the stored board name from NVS into the active table (CLUSTER if unset/unknown). */
static void load_board_from_nvs(void)
{
    s_table = vtarget_cal_default();

    nvs_handle_t h;
    if (nvs_open(VTARGET_NVS_NAMESPACE, NVS_READONLY, &h) != ESP_OK) {
        return;   // namespace not created yet: default table
    }
    char name[VTARGET_CAL_NAME_MAX];
    size_t len = sizeof(name);
    if (nvs_get_str(h, VTARGET_NVS_KEY_BOARD, name, &len) == ESP_OK) {
        const vtarget_cal_table_t *t = vtarget_cal_find(name);
        if (t != NULL) {
            s_table = t;
        } else {
            ESP_LOGW(TAG, "Stored board '%s' has no calibration table, using %s",
                     name, s_table->name);
        }
    }
    nvs_close(h);
}

static esp_err_t apply_duty(uint32_t duty_cycle)
{
    esp_err_t ret = ledc_set_duty(VTARGET_PWM_MODE, VTARGET_PWM_CHANNEL, duty_cycle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set duty cycle: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = ledc_update_duty(VTARGET_PWM_MODE, VTARGET_PWM_CHANNEL);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to update duty: %s", esp_err_to_name(ret));
        return ret;
    }

    mark_changed();
    return ESP_OK;
}

/**
 * @brief Initialize PWM for VTarget voltage control
 *
 * Configures GPIO3 as PWM output at 1 kHz with 10-bit resolution.
 * The PWM signal controls a MOSFET in the AP1117-ADJ feedback network
 * to adjust the output voltage over the active table's calibrated range.
 * Selects the calibration table stored in NVS (default CLUSTER).
 *
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t vtarget_pwm_init(void)
{
    esp_err_t ret;

    load_board_from_nvs();
    ESP_LOGI(TAG, "Calibration table: %s (%u-%u mV)", s_table->name,
             vtarget_cal_min_mv(s_table), vtarget_cal_max_mv(s_table));

    // Configure LEDC timer
    ledc_timer_config_t timer_conf = {
        .speed_mode = VTARGET_PWM_MODE,
        .duty_resolution = VTARGET_PWM_RESOLUTION,
        .timer_num = VTARGET_PWM_TIMER,
        .freq_hz = VTARGET_PWM_FREQUENCY,
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(4, 4, 0)
        .clk_cfg = LEDC_AUTO_CLK
#else
        .clk_cfg = LEDC_USE_APB_CLK  // Fallback for older ESP-IDF versions
#endif
    };
    ret = ledc_timer_config(&timer_conf);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure LEDC timer: %s", esp_err_to_name(ret));
        return ret;
    }

    // Configure LEDC channel
    ledc_channel_config_t channel_conf = {
        .gpio_num = VTARGET_PWM_GPIO,
        .speed_mode = VTARGET_PWM_MODE,
        .channel = VTARGET_PWM_CHANNEL,
        .intr_type = LEDC_INTR_DISABLE,
        .timer_sel = VTARGET_PWM_TIMER,
        .duty = 0,  // Start with 0% duty cycle (max voltage)
        .hpoint = 0
    };
    ret = ledc_channel_config(&channel_conf);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure LEDC channel: %s", esp_err_to_name(ret));
        return ret;
    }

    // Set initial duty cycle to 0% (MOSFET OFF = max voltage, ~4.2V)
    ret = apply_duty(0);
    if (ret != ESP_OK) {
        return ret;
    }

    ESP_LOGI(TAG, "VTarget PWM initialized: GPIO%d, %d Hz, %d-bit resolution",
             VTARGET_PWM_GPIO, VTARGET_PWM_FREQUENCY, VTARGET_PWM_RESOLUTION);

    return ESP_OK;
}

/**
 * @brief Set VTarget voltage using PWM duty cycle
 *
 * Looks up the requested voltage in the active calibration table and
 * interpolates between the two nearest measured points to find the PWM duty
 * cycle. The output needs ~VTARGET_SETTLE_MS to settle afterwards (see
 * vtarget_settle_remaining_ms()).
 *
 * @param voltage_mv Target voltage in millivolts (within vtarget_get_range())
 * @return ESP_OK on success, ESP_ERR_INVALID_ARG if out of range
 */
esp_err_t vtarget_set_voltage(uint16_t voltage_mv)
{
    const vtarget_cal_table_t *table = active_table();

    // Validate input range
    if (!vtarget_cal_in_range(table, voltage_mv)) {
        ESP_LOGE(TAG, "Voltage %d mV out of range (%u-%u mV, table %s)",
                 voltage_mv, vtarget_cal_min_mv(table), vtarget_cal_max_mv(table), table->name);
        return ESP_ERR_INVALID_ARG;
    }

    uint32_t duty_cycle = vtarget_cal_mv_to_duty(table, voltage_mv);

    esp_err_t ret = apply_duty(duty_cycle);
    if (ret != ESP_OK) {
        return ret;
    }
    s_requested_mv = voltage_mv;

    ESP_LOGI(TAG, "VTarget set to %d mV (duty cycle: %u / %d, table %s)",
             voltage_mv, (unsigned int)duty_cycle, VTARGET_PWM_MAX_DUTY, table->name);

    return ESP_OK;
}

/**
 * @brief Set raw PWM duty cycle (for calibration/testing)
 *
 * @param duty_cycle Raw duty cycle value (0 to 1023)
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t vtarget_set_duty_raw(uint16_t duty_cycle)
{
    if (duty_cycle > VTARGET_PWM_MAX_DUTY) {
        ESP_LOGE(TAG, "Duty cycle %d exceeds max %d", duty_cycle, VTARGET_PWM_MAX_DUTY);
        return ESP_ERR_INVALID_ARG;
    }

    esp_err_t ret = apply_duty(duty_cycle);
    if (ret != ESP_OK) {
        return ret;
    }
    s_requested_mv = 0;   // no longer a calibrated request

    ESP_LOGI(TAG, "Raw duty cycle set: %d / %d", duty_cycle, VTARGET_PWM_MAX_DUTY);
    return ESP_OK;
}

/**
 * @brief Get current PWM duty cycle
 *
 * @return Current duty cycle value (0 to 1023)
 */
uint16_t vtarget_get_duty_raw(void)
{
    return ledc_get_duty(VTARGET_PWM_MODE, VTARGET_PWM_CHANNEL);
}

/**
 * @brief Disable VTarget PWM output
 *
 * Sets duty to 0% (MOSFET OFF, maximum voltage output)
 *
 * @return ESP_OK on success
 */
esp_err_t vtarget_pwm_disable(void)
{
    esp_err_t ret = ledc_stop(VTARGET_PWM_MODE, VTARGET_PWM_CHANNEL, 0);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to stop PWM: %s", esp_err_to_name(ret));
        return ret;
    }

    mark_changed();
    s_requested_mv = 0;
    ESP_LOGI(TAG, "VTarget PWM disabled");
    return ESP_OK;
}

const char *vtarget_get_board(void)
{
    return active_table()->name;
}

void vtarget_get_range(uint16_t *min_mv, uint16_t *max_mv)
{
    const vtarget_cal_table_t *table = active_table();
    if (min_mv != NULL) {
        *min_mv = vtarget_cal_min_mv(table);
    }
    if (max_mv != NULL) {
        *max_mv = vtarget_cal_max_mv(table);
    }
}

uint16_t vtarget_get_requested_mv(void)
{
    return s_requested_mv;
}

uint32_t vtarget_settle_remaining_ms(void)
{
    int64_t elapsed_us = esp_timer_get_time() - s_last_change_us;
    uint32_t elapsed_ms = (elapsed_us < 0) ? 0 : (uint32_t)(elapsed_us / 1000);
    return vtarget_cal_settle_remaining_ms(elapsed_ms, VTARGET_SETTLE_MS);
}

/**
 * @brief Select the calibration table for this board and store it in NVS
 *
 * Re-applies the last requested voltage, clamped to the new table's range, so
 * the output follows the new calibration immediately.
 *
 * @param name "CLUSTER" or a board id such as "PCB-05" (case-insensitive)
 * @return ESP_OK, ESP_ERR_NOT_FOUND for an unknown name, or an NVS/LEDC error
 */
esp_err_t vtarget_set_board(const char *name)
{
    const vtarget_cal_table_t *table = vtarget_cal_find(name);
    if (table == NULL) {
        ESP_LOGE(TAG, "Unknown board '%s'", name ? name : "(null)");
        return ESP_ERR_NOT_FOUND;
    }

    nvs_handle_t h;
    esp_err_t ret = nvs_open(VTARGET_NVS_NAMESPACE, NVS_READWRITE, &h);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "NVS open failed: %s", esp_err_to_name(ret));
        return ret;
    }
    ret = nvs_set_str(h, VTARGET_NVS_KEY_BOARD, table->name);
    if (ret == ESP_OK) {
        ret = nvs_commit(h);
    }
    nvs_close(h);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "NVS write failed: %s", esp_err_to_name(ret));
        return ret;
    }

    s_table = table;
    ESP_LOGI(TAG, "Calibration table set to %s (%u-%u mV)", table->name,
             vtarget_cal_min_mv(table), vtarget_cal_max_mv(table));

    // Re-apply the last calibrated request on the new table (clamped to its range)
    if (s_requested_mv != 0) {
        uint16_t mv = s_requested_mv;
        uint16_t lo = vtarget_cal_min_mv(table);
        uint16_t hi = vtarget_cal_max_mv(table);
        if (mv < lo) mv = lo;
        if (mv > hi) mv = hi;
        return vtarget_set_voltage(mv);
    }
    return ESP_OK;
}
