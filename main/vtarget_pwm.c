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

static const char *TAG = "vtarget_pwm";

// PWM Configuration for ESP32-C3
#define VTARGET_PWM_TIMER       LEDC_TIMER_0
#define VTARGET_PWM_MODE        LEDC_LOW_SPEED_MODE
#define VTARGET_PWM_CHANNEL     LEDC_CHANNEL_0
#define VTARGET_PWM_GPIO        3                // GPIO3 for VTarget control
#define VTARGET_PWM_FREQUENCY   1000             // 1 kHz
#define VTARGET_PWM_RESOLUTION  LEDC_TIMER_10_BIT // 10-bit (0-1023)
#define VTARGET_PWM_MAX_DUTY    ((1 << 10) - 1)  // 1023

// Voltage calibration constants
#define VTARGET_MIN_VOLTAGE_MV  1250   // Minimum output: 1.25V
#define VTARGET_MAX_VOLTAGE_MV  5000   // Maximum output: 5.0V

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
 * Controls the MOSFET gate voltage to adjust the AP1117-ADJ feedback
 * network and set the desired output voltage.
 * 
 * PWM Duty Cycle vs. Output Voltage:
 * - 0% duty → MOSFET OFF → High resistance → 5.0V output
 * - 100% duty → MOSFET ON → Low resistance → 1.25V output
 * 
 * @param voltage_mv Target voltage in millivolts (1250 to 5000)
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

    // Calculate duty cycle (inverse relationship)
    // Higher voltage → Lower duty cycle (MOSFET more OFF)
    // Lower voltage → Higher duty cycle (MOSFET more ON)
    uint32_t duty_cycle;
    
    if (voltage_mv >= VTARGET_MAX_VOLTAGE_MV) {
        duty_cycle = 0;  // Maximum voltage, MOSFET OFF
    } else if (voltage_mv <= VTARGET_MIN_VOLTAGE_MV) {
        duty_cycle = VTARGET_PWM_MAX_DUTY;  // Minimum voltage, MOSFET ON
    } else {
        // Linear interpolation (may need calibration)
        // duty = MAX_DUTY * (MAX_V - target_V) / (MAX_V - MIN_V)
        uint32_t voltage_range = VTARGET_MAX_VOLTAGE_MV - VTARGET_MIN_VOLTAGE_MV;
        uint32_t voltage_offset = VTARGET_MAX_VOLTAGE_MV - voltage_mv;
        duty_cycle = (VTARGET_PWM_MAX_DUTY * voltage_offset) / voltage_range;
    }

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
