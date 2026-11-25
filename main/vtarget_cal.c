/**
 * @file vtarget_cal.c
 * @brief VTarget calibration lookup and interpolation (pure C, host-testable)
 *
 * Per-board tables live in vtarget_cal_boards.c (generated from the DMM
 * measurements in tests/test_results by
 * circuit_ESP32C3_Xiao/scripts/generate_vtarget_cal_boards.py).
 */

#include "vtarget_cal.h"

// Calibration curve measured with the VirtualBench DMM (2026-09-08), duty
// ascending / voltage descending. This is the median response of the
// PCB-04/PCB-08/PCB-09/PCB-10 cluster, the only group of measured boards whose
// curves agreed closely enough (worst 1.9%, mean 0.5% vs +/-5% target) to share
// one table. See circuit_ESP32C3_Xiao/documentations/VTARGET_BATCH_ANALYSIS.md.
// Boards outside the cluster use their own table from vtarget_cal_boards.c.
static const vtarget_cal_point_t CLUSTER_POINTS[] = {
    { 358, 4200 }, { 559, 4072 }, { 612, 3943 }, { 647, 3811 }, { 678, 3650 },
    { 699, 3514 }, { 716, 3385 }, { 732, 3250 }, { 747, 3110 }, { 763, 2945 },
    { 775, 2813 }, { 787, 2674 }, { 797, 2552 }, { 808, 2418 }, { 819, 2281 },
    { 831, 2132 }, { 841, 2010 }, { 851, 1892 }, { 862, 1772 }, { 872, 1673 },
    { 883, 1575 }, { 898, 1465 }, { 912, 1397 }, { 929, 1361 }, { 982, 1326 },
};

// Board tables (generated), see vtarget_cal_boards.c
extern const vtarget_cal_table_t VTARGET_CAL_BOARD_TABLES[];
extern const size_t VTARGET_CAL_BOARD_TABLE_COUNT;

#define CLUSTER_COUNT (sizeof(CLUSTER_POINTS) / sizeof(CLUSTER_POINTS[0]))

static const vtarget_cal_table_t CLUSTER_TABLE = {
    VTARGET_CAL_DEFAULT_NAME, CLUSTER_POINTS, CLUSTER_COUNT
};

static char ascii_lower(char c)
{
    return (c >= 'A' && c <= 'Z') ? (char)(c + ('a' - 'A')) : c;
}

static bool name_equal(const char *a, const char *b)
{
    while (*a && *b) {
        if (ascii_lower(*a) != ascii_lower(*b)) {
            return false;
        }
        a++;
        b++;
    }
    return *a == '\0' && *b == '\0';
}

const vtarget_cal_table_t *vtarget_cal_default(void)
{
    return &CLUSTER_TABLE;
}

size_t vtarget_cal_table_count(void)
{
    return 1 + VTARGET_CAL_BOARD_TABLE_COUNT;
}

const vtarget_cal_table_t *vtarget_cal_table_at(size_t index)
{
    if (index == 0) {
        return &CLUSTER_TABLE;
    }
    if (index - 1 < VTARGET_CAL_BOARD_TABLE_COUNT) {
        return &VTARGET_CAL_BOARD_TABLES[index - 1];
    }
    return NULL;
}

const vtarget_cal_table_t *vtarget_cal_find(const char *name)
{
    if (name == NULL) {
        return NULL;
    }
    if (name_equal(name, CLUSTER_TABLE.name)) {
        return &CLUSTER_TABLE;
    }
    for (size_t i = 0; i < VTARGET_CAL_BOARD_TABLE_COUNT; i++) {
        if (name_equal(name, VTARGET_CAL_BOARD_TABLES[i].name)) {
            return &VTARGET_CAL_BOARD_TABLES[i];
        }
    }
    return NULL;
}

bool vtarget_cal_table_valid(const vtarget_cal_table_t *table)
{
    if (table == NULL || table->points == NULL || table->count < 2) {
        return false;
    }
    for (size_t i = 1; i < table->count; i++) {
        if (table->points[i].duty <= table->points[i - 1].duty) {
            return false;
        }
        if (table->points[i].voltage_mv >= table->points[i - 1].voltage_mv) {
            return false;
        }
    }
    return true;
}

uint16_t vtarget_cal_min_mv(const vtarget_cal_table_t *table)
{
    if (table == NULL || table->points == NULL || table->count == 0) {
        return 0;
    }
    return table->points[table->count - 1].voltage_mv;
}

uint16_t vtarget_cal_max_mv(const vtarget_cal_table_t *table)
{
    if (table == NULL || table->points == NULL || table->count == 0) {
        return 0;
    }
    return table->points[0].voltage_mv;
}

bool vtarget_cal_in_range(const vtarget_cal_table_t *table, uint16_t voltage_mv)
{
    if (table == NULL || table->points == NULL || table->count == 0) {
        return false;
    }
    return voltage_mv >= vtarget_cal_min_mv(table) && voltage_mv <= vtarget_cal_max_mv(table);
}

uint32_t vtarget_cal_mv_to_duty(const vtarget_cal_table_t *table, uint16_t voltage_mv)
{
    if (table == NULL || table->points == NULL || table->count == 0) {
        return 0;
    }
    const vtarget_cal_point_t *p = table->points;
    size_t last = table->count - 1;

    if (voltage_mv >= p[0].voltage_mv) {
        return p[0].duty;
    }
    if (voltage_mv <= p[last].voltage_mv) {
        return p[last].duty;
    }

    for (size_t i = 0; i < last; i++) {
        uint16_t v_hi = p[i].voltage_mv;
        uint16_t v_lo = p[i + 1].voltage_mv;
        if (voltage_mv <= v_hi && voltage_mv >= v_lo) {
            uint16_t duty_lo = p[i].duty;
            uint16_t duty_hi = p[i + 1].duty;
            uint32_t span_v = (uint32_t)(v_hi - v_lo);
            uint32_t offset_v = (uint32_t)(v_hi - voltage_mv);
            if (span_v == 0) {
                return duty_lo;
            }
            return duty_lo + ((uint32_t)(duty_hi - duty_lo) * offset_v) / span_v;
        }
    }

    return p[last].duty;
}

uint16_t vtarget_cal_duty_to_mv(const vtarget_cal_table_t *table, uint32_t duty)
{
    if (table == NULL || table->points == NULL || table->count == 0) {
        return 0;
    }
    const vtarget_cal_point_t *p = table->points;
    size_t last = table->count - 1;

    if (duty <= p[0].duty) {
        return p[0].voltage_mv;
    }
    if (duty >= p[last].duty) {
        return p[last].voltage_mv;
    }

    for (size_t i = 0; i < last; i++) {
        uint32_t duty_lo = p[i].duty;
        uint32_t duty_hi = p[i + 1].duty;
        if (duty >= duty_lo && duty <= duty_hi) {
            uint32_t span_d = duty_hi - duty_lo;
            if (span_d == 0) {
                return p[i].voltage_mv;
            }
            uint32_t drop = ((uint32_t)(p[i].voltage_mv - p[i + 1].voltage_mv) * (duty - duty_lo)
                             + span_d / 2) / span_d;   // rounded
            return (uint16_t)(p[i].voltage_mv - drop);
        }
    }

    return p[last].voltage_mv;
}

uint32_t vtarget_cal_settle_remaining_ms(uint32_t elapsed_ms, uint32_t settle_ms)
{
    return (elapsed_ms >= settle_ms) ? 0 : (settle_ms - elapsed_ms);
}

size_t vtarget_cal_encode_info(uint8_t *out, size_t cap, const vtarget_info_t *info)
{
    if (out == NULL || info == NULL || info->name == NULL) {
        return 0;
    }

    size_t name_len = 0;
    while (info->name[name_len] != '\0' && name_len < VTARGET_CAL_NAME_MAX - 1) {
        name_len++;
    }

    size_t total = 10 + name_len;
    if (cap < total) {
        return 0;
    }

    uint16_t settle16 = (info->settle_ms > 0xFFFFU) ? 0xFFFFU : (uint16_t)info->settle_ms;

    out[0] = (info->settle_ms == 0) ? 0x01 : 0x00;
    out[1] = (uint8_t)(info->min_mv & 0xFF);
    out[2] = (uint8_t)(info->min_mv >> 8);
    out[3] = (uint8_t)(info->max_mv & 0xFF);
    out[4] = (uint8_t)(info->max_mv >> 8);
    out[5] = (uint8_t)(info->requested_mv & 0xFF);
    out[6] = (uint8_t)(info->requested_mv >> 8);
    out[7] = (uint8_t)(settle16 & 0xFF);
    out[8] = (uint8_t)(settle16 >> 8);
    out[9] = (uint8_t)name_len;
    for (size_t i = 0; i < name_len; i++) {
        out[10 + i] = (uint8_t)info->name[i];
    }
    return total;
}
