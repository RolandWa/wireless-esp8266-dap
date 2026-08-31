/**
 * @file vtarget_pwm.h
 * @brief Programmable VTarget voltage control using PWM
 * 
 * Provides functions to control the target board voltage (VTarget) from 1.324V to 4.204V
 * using PWM-controlled MOSFET in the AP1117-ADJ feedback network.
 * 
 * Hardware Requirements:
 * - GPIO3: PWM output
 * - R4 (100R): Gate series resistor
 * - R5 (43k): Gate pull-down
 * - C2 (10uF, 25V): PWM filter capacitor
 * - Q1 (YJL2304A): N-channel MOSFET
 * - U2 (AP1117-ADJ): Adjustable LDO regulator
 * - R6, R7 (100k each): Feedback voltage divider
 * - C3 (10µF): Output capacitor
 */

#ifndef VTARGET_PWM_H
#define VTARGET_PWM_H

#include "esp_err.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize PWM for VTarget voltage control
 * 
 * Configures GPIO3 as PWM output at 1 kHz with 10-bit resolution (0-1023).
 * Must be called before using other vtarget functions.
 * 
 * PWM Configuration:
 * - Frequency: 1 kHz
 * - Resolution: 10-bit (1024 steps)
 * - GPIO: GPIO3
 * - Initial state: 0% duty
 * 
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t vtarget_pwm_init(void);

/**
 * @brief Set VTarget output voltage
 * 
 * Adjusts the PWM duty cycle to achieve the desired output voltage using a
 * piecewise-linear calibration table measured with a DMM, since the
 * MOSFET/AP1117-ADJ feedback response is not linear across the range.
 * 
 * Voltage Control:
 * - Interpolated between 21 DMM-measured (duty, voltage) points
 * - PWM count 358 → approximately 4.206V output
 * - PWM count 982 → approximately 1.326V output
 * 
 * Note: Recalibrate VTARGET_CAL_TABLE in vtarget_pwm.c if hardware changes
 * (resistor values, MOSFET part, load current).
 * 
 * @param voltage_mv Target voltage in millivolts (1326 to 4206)
 * @return ESP_OK on success, ESP_ERR_INVALID_ARG if out of range
 */
esp_err_t vtarget_set_voltage(uint16_t voltage_mv);

/**
 * @brief Set raw PWM duty cycle
 * 
 * Directly sets the PWM duty cycle without voltage calculation.
 * Useful for calibration and testing.
 * 
 * @param duty_cycle Raw duty cycle value (0 to 1023)
 *                   Values outside the calibrated 358-982 range are for testing only.
 * @return ESP_OK on success, ESP_ERR_INVALID_ARG if out of range
 */
esp_err_t vtarget_set_duty_raw(uint16_t duty_cycle);

/**
 * @brief Get current PWM duty cycle
 * 
 * Returns the current duty cycle setting (not the actual voltage).
 * 
 * @return Current duty cycle value (0 to 1023)
 */
uint16_t vtarget_get_duty_raw(void);

/**
 * @brief Disable VTarget PWM output
 * 
 * Stops the PWM output and sets duty to 0%.
 * 
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t vtarget_pwm_disable(void);

// Convenience macros for common voltages
#define VTARGET_SET_1V8()   vtarget_set_voltage(1800)
#define VTARGET_SET_3V0()   vtarget_set_voltage(3000)
#define VTARGET_SET_3V3()   vtarget_set_voltage(3300)
#define VTARGET_SET_4V2()   vtarget_set_voltage(4200)

#ifdef __cplusplus
}
#endif

#endif // VTARGET_PWM_H
