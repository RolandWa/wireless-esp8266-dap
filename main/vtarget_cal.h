/**
 * @file vtarget_cal.h
 * @brief VTarget calibration tables and pure mapping logic (no ESP-IDF dependency)
 *
 * The Q1/AP1117-ADJ feedback response is nonlinear and differs from board to
 * board, so the requested voltage is mapped to a PWM duty by piecewise-linear
 * interpolation through a DMM-measured table. One table exists per measured
 * PCB plus a shared "CLUSTER" table (median of PCB-04/08/09/10, the default).
 *
 * Everything here is plain C so it can be unit-tested on the host
 * (tests/unit, WSL gcc). Hardware access lives in vtarget_pwm.c.
 *
 * Table convention: points sorted by duty ascending, voltage strictly
 * descending (more duty = Q1 more on = lower voltage).
 */

#ifndef VTARGET_CAL_H
#define VTARGET_CAL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Name of the table used when no board is selected. */
#define VTARGET_CAL_DEFAULT_NAME "CLUSTER"

/** Maximum board name length including the terminating NUL. */
#define VTARGET_CAL_NAME_MAX 16

/**
 * VTarget needs this long after a duty change to settle: the Q1 gate filter
 * (R4=22k, R5=43k, C2=10uF) has tau ~ 145 ms, so ~5 tau ~ 0.7 s, rounded up.
 */
#define VTARGET_SETTLE_MS 1000

typedef struct {
    uint16_t duty;        /**< PWM duty count (0-1023) */
    uint16_t voltage_mv;  /**< Measured VTarget at that duty, mV */
} vtarget_cal_point_t;

typedef struct {
    const char *name;                    /**< "CLUSTER" or "PCB-xx" */
    const vtarget_cal_point_t *points;   /**< duty ascending, voltage descending */
    size_t count;
} vtarget_cal_table_t;

/** Number of tables (CLUSTER + one per measured board). */
size_t vtarget_cal_table_count(void);

/** Table by index; index 0 is the default (CLUSTER). NULL if out of range. */
const vtarget_cal_table_t *vtarget_cal_table_at(size_t index);

/** Find a table by name (ASCII case-insensitive). NULL if unknown or name is NULL. */
const vtarget_cal_table_t *vtarget_cal_find(const char *name);

/** The default table (CLUSTER). */
const vtarget_cal_table_t *vtarget_cal_default(void);

/** Table sanity: >= 2 points, duty strictly ascending, voltage strictly descending. */
bool vtarget_cal_table_valid(const vtarget_cal_table_t *table);

/** Lowest / highest voltage the table can produce (mV). 0 for a NULL/empty table. */
uint16_t vtarget_cal_min_mv(const vtarget_cal_table_t *table);
uint16_t vtarget_cal_max_mv(const vtarget_cal_table_t *table);

/** True if voltage_mv lies inside [min, max] of the table (inclusive). */
bool vtarget_cal_in_range(const vtarget_cal_table_t *table, uint16_t voltage_mv);

/**
 * Map a requested voltage to a PWM duty (piecewise-linear, integer math).
 * Values outside the table are clamped to the first/last duty.
 */
uint32_t vtarget_cal_mv_to_duty(const vtarget_cal_table_t *table, uint16_t voltage_mv);

/**
 * Forward mapping: voltage the table predicts for a duty count.
 * Duty outside the table is clamped to the first/last point.
 */
uint16_t vtarget_cal_duty_to_mv(const vtarget_cal_table_t *table, uint32_t duty);

/** Milliseconds still to wait for settling, given the time since the last change. */
uint32_t vtarget_cal_settle_remaining_ms(uint32_t elapsed_ms, uint32_t settle_ms);

/** Content of the DAP Vendor3 (0x83) "VTarget info" response. */
typedef struct {
    uint16_t min_mv;         /**< lowest voltage of the active table */
    uint16_t max_mv;         /**< highest voltage of the active table */
    uint16_t requested_mv;   /**< last voltage requested via Vendor2, 0 = none */
    uint32_t settle_ms;      /**< ms still to wait for the output to settle, 0 = settled */
    const char *name;        /**< active table name */
} vtarget_info_t;

/** Largest encoded Vendor3 payload: 10 fixed bytes + table name (without NUL). */
#define VTARGET_INFO_MAX_LEN (10 + VTARGET_CAL_NAME_MAX)

/**
 * Encode the Vendor3 response payload (everything after the command id byte):
 *   [flags, min_lo, min_hi, max_lo, max_hi, req_lo, req_hi,
 *    settle_ms_lo, settle_ms_hi, name_len, name...]
 * flags bit0 = settled (settle_ms == 0). settle_ms is saturated to 0xFFFF.
 * Names longer than VTARGET_CAL_NAME_MAX - 1 are truncated.
 *
 * @return number of bytes written, or 0 if info/out is NULL or cap is too small
 */
size_t vtarget_cal_encode_info(uint8_t *out, size_t cap, const vtarget_info_t *info);

#ifdef __cplusplus
}
#endif

#endif // VTARGET_CAL_H
