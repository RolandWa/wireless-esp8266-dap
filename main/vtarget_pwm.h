/**
 * @file vtarget_pwm.h
 * @brief Programmable VTarget voltage control using PWM
 * 
 * Provides functions to control the target board voltage (VTarget) from 1.326V to 4.200V
 * using PWM-controlled MOSFET in the AP1117-ADJ feedback network.
 * 
 * Hardware Requirements:
 * - GPIO3: PWM output
 * - R4 (22k): Gate series resistor
 * - R5 (43k): Gate pull-down
 * - C2 (10uF, 25V): PWM filter capacitor (tau ~ 145 ms; allow ~1 s to settle)
 * - Q1 (YJL2304A): N-channel MOSFET
 * - U2 (AP1117-ADJ): Adjustable LDO regulator
 * - R1 (1.2k), R3 (2.7k): AP1117-ADJ feedback divider
 * - R6, R7 (100k each): VTref sense divider to GPIO2 (ADC)
 * - C3 (10µF): Output capacitor
 *
 * Values are taken from the KiCad schematic and are fitted on all PCBs.
 */

#ifndef VTARGET_PWM_H
#define VTARGET_PWM_H

#include "esp_err.h"
#include "vtarget_cal.h"
#include <stdint.h>

/** Maximum board name length including NUL (e.g. "PCB-05", "CLUSTER"). */
#define VTARGET_BOARD_NAME_MAX VTARGET_CAL_NAME_MAX

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
 * - Interpolated between DMM-measured (duty, voltage) points of the active
 *   calibration table (see vtarget_cal.h)
 * - Default table CLUSTER: PWM count 358 → ~4.200V, 982 → ~1.326V
 * - Per-board tables (PCB-01 ... PCB-10) are selected with vtarget_set_board()
 *
 * Note: CLUSTER is the median PCB-04/08/09/10 response. Other boards are
 * within +/-5% only with their own table. Recalibrate (and regenerate
 * vtarget_cal_boards.c) if hardware changes (resistor values, MOSFET part,
 * load current). See
 * circuit_ESP32C3_Xiao/documentations/VTARGET_BATCH_ANALYSIS.md.
 *
 * The output needs ~VTARGET_SETTLE_MS to settle after each change (gate filter
 * tau ~ 145 ms); use vtarget_settle_remaining_ms() before trusting a reading.
 *
 * @param voltage_mv Target voltage in millivolts (within vtarget_get_range())
 * @return ESP_OK on success, ESP_ERR_INVALID_ARG if out of range
 */
esp_err_t vtarget_set_voltage(uint16_t voltage_mv);

/**
 * @brief Name of the calibration table in use ("CLUSTER" or "PCB-xx")
 */
const char *vtarget_get_board(void);

/**
 * @brief Select the calibration table for this board and persist it in NVS
 *
 * Re-applies the last requested voltage (clamped to the new table's range).
 *
 * @param name "CLUSTER" or "PCB-xx" (case-insensitive)
 * @return ESP_OK, ESP_ERR_NOT_FOUND for an unknown name, or an NVS/LEDC error
 */
esp_err_t vtarget_set_board(const char *name);

/**
 * @brief Voltage range accepted by vtarget_set_voltage() for the active table
 * @param min_mv Receives the lowest voltage (may be NULL)
 * @param max_mv Receives the highest voltage (may be NULL)
 */
void vtarget_get_range(uint16_t *min_mv, uint16_t *max_mv);

/**
 * @brief Last voltage requested via vtarget_set_voltage(), 0 if none/raw duty
 */
uint16_t vtarget_get_requested_mv(void);

/**
 * @brief Milliseconds until the output has settled after the last change
 * @return 0 when settled
 */
uint32_t vtarget_settle_remaining_ms(void);

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
