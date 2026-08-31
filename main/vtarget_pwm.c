/**
 * @file vtarget_pwm.c
 * @brief Programmable VTarget voltage control using PWM on GPIO3
 * 
 * Controls AP1117-ADJ output voltage (1.25V to 5V) via PWM-controlled MOSFET
 * in the feedback divider network.
 * 
 * Circuit topology:
 * - GPIO3 PWM → R4 (39k) → Q1 (YJL2304A MOSFET) Gate
 * - R5 (10k) pull-down on gate
 * - C2 (10nF) PWM filter
 * - AP1117-ADJ with R6/R7 (100k each) + MOSFET in feedback
 * - C3 (10uF) output capacitor on VTarget
 */

#include "vtarget_pwm.h"
#include "driver/ledc.h"
#include "esp_log.h"
#include "esp_idf_version.h"

static const char *TAG = "vtarget_pwm";

// PWM Configuration for ESP32-C3
#define VTARGET_PWM_TIMER       LEDC_TIMER_0
#define VTARGET_PWM_MODE        LEDC_LOW_SPEED_MODE
#define VTARGET_PWM_CHANNEL     LEDC_CHANNEL_0
#define VTARGET_PWM_GPIO        3                // GPIO3 for VTarget control
#define VTARGET_PWM_FREQUENCY   1000             // 1 kHz
#define VTARGET_PWM_RESOLUTION  LEDC_TIMER_10_BIT // 10-bit (0-1023)
#define VTARGET_PWM_MAX_DUTY    ((1 << 10) - 1)  // 1023

// Calibration curve measured with the VirtualBench DMM (2026-08-31), duty
// ascending / voltage descending. Replaces a two-point linear guess because
// the Q1/AP1117 feedback response is nonlinear across the duty range.
typedef struct {
    uint16_t duty;
    uint16_t voltage_mv;
} vtarget_cal_point_t;

static const vtarget_cal_point_t VTARGET_CAL_TABLE[] = {
    { 358, 4206 }, { 389, 4197 }, { 420, 4183 }, { 451, 4166 }, { 482, 4131 },
    { 514, 4080 }, { 545, 4006 }, { 576, 3902 }, { 607, 3757 }, { 638, 3569 },
    { 670, 3312 }, { 701, 3012 }, { 732, 2654 }, { 763, 2269 }, { 794, 1892 },
    { 826, 1569 }, { 857, 1396 }, { 888, 1357 }, { 919, 1343 }, { 950, 1329 },
    { 982, 1326 },
};
#define VTARGET_CAL_POINTS (sizeof(VTARGET_CAL_TABLE) / sizeof(VTARGET_CAL_TABLE[0]))

#define VTARGET_MIN_VOLTAGE_MV  1326   // VTARGET_CAL_TABLE last entry
#define VTARGET_MAX_VOLTAGE_MV  4206   // VTARGET_CAL_TABLE first entry

/**
 * @brief Map a requested voltage to a PWM duty using the calibration table
 *
 * Performs piecewise-linear interpolation between the two bracketing
 * measured points instead of assuming a straight line across the full range.
 */
static uint32_t vtarget_interp_duty(uint16_t voltage_mv)
{
    size_t last = VTARGET_CAL_POINTS - 1;

    if (voltage_mv >= VTARGET_CAL_TABLE[0].voltage_mv) {
        return VTARGET_CAL_TABLE[0].duty;
    }
    if (voltage_mv <= VTARGET_CAL_TABLE[last].voltage_mv) {
        return VTARGET_CAL_TABLE[last].duty;
    }

    for (size_t i = 0; i < last; i++) {
        uint16_t v_hi = VTARGET_CAL_TABLE[i].voltage_mv;
        uint16_t v_lo = VTARGET_CAL_TABLE[i + 1].voltage_mv;
        if (voltage_mv <= v_hi && voltage_mv >= v_lo) {
            uint16_t duty_lo = VTARGET_CAL_TABLE[i].duty;
            uint16_t duty_hi = VTARGET_CAL_TABLE[i + 1].duty;
            uint32_t span_v = v_hi - v_lo;
            uint32_t offset_v = v_hi - voltage_mv;
            return duty_lo + ((uint32_t)(duty_hi - duty_lo) * offset_v) / span_v;
        }
    }

    return VTARGET_CAL_TABLE[last].duty;
}

/**
 * @brief Initialize PWM for VTarget voltage control
 * 
 * Configures GPIO3 as PWM output at 1 kHz with 10-bit resolution.
 * The PWM signal controls a MOSFET in the AP1117-ADJ feedback network
 * to adjust the output voltage from 1.25V to 5V.
 * 
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t vtarget_pwm_init(void)
{
    esp_err_t ret;

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

    // Set initial duty cycle to 0% (MOSFET OFF = max voltage = 5V)
    ret = ledc_set_duty(VTARGET_PWM_MODE, VTARGET_PWM_CHANNEL, 0);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set initial duty: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = ledc_update_duty(VTARGET_PWM_MODE, VTARGET_PWM_CHANNEL);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to update duty: %s", esp_err_to_name(ret));
        return ret;
    }

    ESP_LOGI(TAG, "VTarget PWM initialized: GPIO%d, %d Hz, %d-bit resolution",
             VTARGET_PWM_GPIO, VTARGET_PWM_FREQUENCY, VTARGET_PWM_RESOLUTION);

    return ESP_OK;
}

/**
 * @brief Set VTarget voltage using PWM duty cycle
 * 
 * Looks up the requested voltage in VTARGET_CAL_TABLE and interpolates
 * between the two nearest measured points to find the PWM duty cycle.
 * 
 * @param voltage_mv Target voltage in millivolts (1326 to 4206)
 * @return ESP_OK on success, ESP_ERR_INVALID_ARG if out of range
 */
esp_err_t vtarget_set_voltage(uint16_t voltage_mv)
{
    // Validate input range
    if (voltage_mv < VTARGET_MIN_VOLTAGE_MV || voltage_mv > VTARGET_MAX_VOLTAGE_MV) {
        ESP_LOGE(TAG, "Voltage %d mV out of range (%d-%d mV)",
                 voltage_mv, VTARGET_MIN_VOLTAGE_MV, VTARGET_MAX_VOLTAGE_MV);
        return ESP_ERR_INVALID_ARG;
    }

    uint32_t duty_cycle = vtarget_interp_duty(voltage_mv);

    // Set the PWM duty cycle
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

    ESP_LOGI(TAG, "VTarget set to %d mV (duty cycle: %u / %d)",
             voltage_mv, (unsigned int)duty_cycle, VTARGET_PWM_MAX_DUTY);

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

    esp_err_t ret = ledc_set_duty(VTARGET_PWM_MODE, VTARGET_PWM_CHANNEL, duty_cycle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set raw duty: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = ledc_update_duty(VTARGET_PWM_MODE, VTARGET_PWM_CHANNEL);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to update raw duty: %s", esp_err_to_name(ret));
        return ret;
    }

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

    ESP_LOGI(TAG, "VTarget PWM disabled");
    return ESP_OK;
}
