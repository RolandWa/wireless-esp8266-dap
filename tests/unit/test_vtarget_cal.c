/**
 * Host unit tests for main/vtarget_cal.c (+ generated vtarget_cal_boards.c).
 *
 * Build/run:  make -C tests/unit test          (gcc, run it in WSL on Windows)
 * Usage:      ./test_vtarget_cal [measurements_dir]
 *
 * With a measurements dir (default ../test_results) the per-board tables are
 * also checked against the DMM sweeps they were generated from.
 */

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtarget_cal.h"

static int g_checks = 0;
static int g_failures = 0;
static const char *g_test = "";

#define CHECK(cond)                                                                   \
    do {                                                                              \
        g_checks++;                                                                   \
        if (!(cond)) {                                                                \
            g_failures++;                                                             \
            printf("  FAIL [%s] %s:%d: %s\n", g_test, __FILE__, __LINE__, #cond);     \
        }                                                                             \
    } while (0)

#define CHECK_EQ(actual, expected)                                                    \
    do {                                                                              \
        long long a_ = (long long)(actual), e_ = (long long)(expected);               \
        g_checks++;                                                                   \
        if (a_ != e_) {                                                               \
            g_failures++;                                                             \
            printf("  FAIL [%s] %s:%d: %s == %lld, expected %lld\n", g_test,          \
                   __FILE__, __LINE__, #actual, a_, e_);                              \
        }                                                                             \
    } while (0)

#define RUN(fn)                                                                       \
    do {                                                                              \
        int before_ = g_failures;                                                     \
        g_test = #fn;                                                                 \
        fn();                                                                         \
        printf("%s %s\n", (g_failures == before_) ? "ok  " : "FAIL", #fn);            \
    } while (0)

static const char *g_csv_dir = "../test_results";

/* ------------------------------------------------------------------ lookup */

static void test_find_by_name(void)
{
    const vtarget_cal_table_t *t = vtarget_cal_find("CLUSTER");
    CHECK(t != NULL);
    CHECK(t == vtarget_cal_default());

    CHECK(vtarget_cal_find("cluster") == t);   /* case-insensitive */
    CHECK(vtarget_cal_find("ClUsTeR") == t);

    const vtarget_cal_table_t *p5 = vtarget_cal_find("PCB-05");
    CHECK(p5 != NULL);
    CHECK(strcmp(p5->name, "PCB-05") == 0);
    CHECK(vtarget_cal_find("pcb-05") == p5);

    CHECK(vtarget_cal_find(NULL) == NULL);
    CHECK(vtarget_cal_find("") == NULL);
    CHECK(vtarget_cal_find("PCB-99") == NULL);
    CHECK(vtarget_cal_find("PCB-0") == NULL);        /* prefix is not a match */
    CHECK(vtarget_cal_find("PCB-055") == NULL);
    CHECK(vtarget_cal_find("CLUSTERX") == NULL);
    CHECK(vtarget_cal_find("CLUSTE") == NULL);
    CHECK(vtarget_cal_find(" PCB-05") == NULL);
}

static void test_table_registry(void)
{
    size_t n = vtarget_cal_table_count();
    CHECK(n >= 2);
    CHECK(vtarget_cal_table_at(0) == vtarget_cal_default());
    CHECK(vtarget_cal_table_at(n) == NULL);
    CHECK(vtarget_cal_table_at((size_t)-1) == NULL);

    /* names are unique and every table is reachable by its own name */
    for (size_t i = 0; i < n; i++) {
        const vtarget_cal_table_t *a = vtarget_cal_table_at(i);
        CHECK(a != NULL);
        CHECK(vtarget_cal_find(a->name) == a);
        CHECK(strlen(a->name) < VTARGET_CAL_NAME_MAX);
        for (size_t j = i + 1; j < n; j++) {
            CHECK(strcmp(a->name, vtarget_cal_table_at(j)->name) != 0);
        }
    }
}

/* ------------------------------------------------------- table consistency */

static void test_all_tables_valid(void)
{
    for (size_t i = 0; i < vtarget_cal_table_count(); i++) {
        const vtarget_cal_table_t *t = vtarget_cal_table_at(i);
        CHECK(vtarget_cal_table_valid(t));
        CHECK(t->count >= 2 && t->count <= 32);
        CHECK(vtarget_cal_min_mv(t) < vtarget_cal_max_mv(t));
        for (size_t k = 0; k < t->count; k++) {
            CHECK(t->points[k].duty <= 1023);
        }
    }
}

static void test_table_valid_rejects_bad_tables(void)
{
    static const vtarget_cal_point_t ok[] = { { 100, 4000 }, { 500, 2000 }, { 900, 1400 } };
    static const vtarget_cal_point_t dup_duty[] = { { 100, 4000 }, { 100, 2000 } };
    static const vtarget_cal_point_t back_duty[] = { { 500, 4000 }, { 100, 2000 } };
    static const vtarget_cal_point_t rising_v[] = { { 100, 2000 }, { 500, 4000 } };
    static const vtarget_cal_point_t flat_v[] = { { 100, 2000 }, { 500, 2000 } };
    static const vtarget_cal_point_t one[] = { { 100, 2000 } };

    vtarget_cal_table_t t_ok = { "OK", ok, 3 };
    vtarget_cal_table_t t_dup = { "DUP", dup_duty, 2 };
    vtarget_cal_table_t t_back = { "BACK", back_duty, 2 };
    vtarget_cal_table_t t_rise = { "RISE", rising_v, 2 };
    vtarget_cal_table_t t_flat = { "FLAT", flat_v, 2 };
    vtarget_cal_table_t t_one = { "ONE", one, 1 };
    vtarget_cal_table_t t_null_pts = { "NULLPTS", NULL, 3 };

    CHECK(vtarget_cal_table_valid(&t_ok));
    CHECK(!vtarget_cal_table_valid(&t_dup));
    CHECK(!vtarget_cal_table_valid(&t_back));
    CHECK(!vtarget_cal_table_valid(&t_rise));
    CHECK(!vtarget_cal_table_valid(&t_flat));
    CHECK(!vtarget_cal_table_valid(&t_one));
    CHECK(!vtarget_cal_table_valid(&t_null_pts));
    CHECK(!vtarget_cal_table_valid(NULL));
}

/* -------------------------------------------- default table = old behaviour */

static void test_default_table_unchanged(void)
{
    /* The default table must keep behaving exactly like the table that used to
     * live in vtarget_pwm.c (values verified against the firmware mapping). */
    const vtarget_cal_table_t *t = vtarget_cal_default();
    CHECK(strcmp(t->name, "CLUSTER") == 0);
    CHECK_EQ(t->count, 25);
    CHECK_EQ(vtarget_cal_min_mv(t), 1326);
    CHECK_EQ(vtarget_cal_max_mv(t), 4200);
    CHECK_EQ(t->points[0].duty, 358);
    CHECK_EQ(t->points[24].duty, 982);

    CHECK_EQ(vtarget_cal_mv_to_duty(t, 4200), 358);
    CHECK_EQ(vtarget_cal_mv_to_duty(t, 3300), 726);
    CHECK_EQ(vtarget_cal_mv_to_duty(t, 2500), 801);
    CHECK_EQ(vtarget_cal_mv_to_duty(t, 1800), 859);
    CHECK_EQ(vtarget_cal_mv_to_duty(t, 1326), 982);
}

/* ------------------------------------------------------------------- range */

static void test_range_checks(void)
{
    const vtarget_cal_table_t *t = vtarget_cal_default();
    CHECK(!vtarget_cal_in_range(t, 1325));
    CHECK(vtarget_cal_in_range(t, 1326));
    CHECK(vtarget_cal_in_range(t, 3300));
    CHECK(vtarget_cal_in_range(t, 4200));
    CHECK(!vtarget_cal_in_range(t, 4201));
    CHECK(!vtarget_cal_in_range(t, 0));
    CHECK(!vtarget_cal_in_range(t, 5000));
    CHECK(!vtarget_cal_in_range(NULL, 3300));

    CHECK_EQ(vtarget_cal_min_mv(NULL), 0);
    CHECK_EQ(vtarget_cal_max_mv(NULL), 0);

    /* The restricted-range board accepts less than the default table */
    const vtarget_cal_table_t *p7 = vtarget_cal_find("PCB-07");
    CHECK(p7 != NULL);
    CHECK(vtarget_cal_min_mv(p7) > 1800);
    CHECK(!vtarget_cal_in_range(p7, 1500));
    CHECK(vtarget_cal_in_range(p7, 3300));
}

/* ---------------------------------------------------------- interpolation */

static void test_mv_to_duty_points_and_clamping(void)
{
    const vtarget_cal_table_t *t = vtarget_cal_default();

    /* exact table points map to their duty */
    for (size_t i = 0; i < t->count; i++) {
        CHECK_EQ(vtarget_cal_mv_to_duty(t, t->points[i].voltage_mv), t->points[i].duty);
    }
    /* clamped outside the table */
    CHECK_EQ(vtarget_cal_mv_to_duty(t, 4201), 358);
    CHECK_EQ(vtarget_cal_mv_to_duty(t, 65535), 358);
    CHECK_EQ(vtarget_cal_mv_to_duty(t, 1325), 982);
    CHECK_EQ(vtarget_cal_mv_to_duty(t, 0), 982);
    CHECK_EQ(vtarget_cal_mv_to_duty(NULL, 3000), 0);
}

static void test_interpolation_between_points(void)
{
    const vtarget_cal_table_t *t = vtarget_cal_default();
    /* segment {732,3250}..{747,3110}: 3180 mV is half way -> 732 + 15*70/140 = 739 */
    CHECK_EQ(vtarget_cal_mv_to_duty(t, 3180), 739);
    /* forward: 739 -> 3250 - round(140*7/15) = 3250 - 65 = 3185 */
    CHECK_EQ(vtarget_cal_duty_to_mv(t, 739), 3185);

    CHECK_EQ(vtarget_cal_duty_to_mv(t, 358), 4200);
    CHECK_EQ(vtarget_cal_duty_to_mv(t, 982), 1326);
    CHECK_EQ(vtarget_cal_duty_to_mv(t, 0), 4200);       /* clamped below */
    CHECK_EQ(vtarget_cal_duty_to_mv(t, 1023), 1326);    /* clamped above */
    CHECK_EQ(vtarget_cal_duty_to_mv(NULL, 500), 0);
}

static void test_monotonic_over_full_range(void)
{
    for (size_t i = 0; i < vtarget_cal_table_count(); i++) {
        const vtarget_cal_table_t *t = vtarget_cal_table_at(i);
        uint32_t prev_duty = 0xFFFFFFFFu;
        /* walking the voltage upwards the duty must never increase */
        for (uint32_t mv = vtarget_cal_min_mv(t); mv <= vtarget_cal_max_mv(t); mv++) {
            uint32_t d = vtarget_cal_mv_to_duty(t, (uint16_t)mv);
            if (d > prev_duty) {
                CHECK(d <= prev_duty);
                printf("    %s: duty rose at %u mV (%u > %u)\n", t->name, mv, d, prev_duty);
                break;
            }
            prev_duty = d;
        }
        /* walking the duty upwards the voltage must never rise */
        uint16_t prev_mv = 0xFFFF;
        for (uint32_t d = t->points[0].duty; d <= t->points[t->count - 1].duty; d++) {
            uint16_t mv = vtarget_cal_duty_to_mv(t, d);
            if (mv > prev_mv) {
                CHECK(mv <= prev_mv);
                printf("    %s: voltage rose at duty %u\n", t->name, d);
                break;
            }
            prev_mv = mv;
        }
    }
    CHECK(1);
}

static void test_roundtrip_within_one_duty_step(void)
{
    /* request -> duty -> predicted voltage may only differ by the voltage that one
     * PWM count is worth (steepest segment of any table is ~13 mV/count). */
    for (size_t i = 0; i < vtarget_cal_table_count(); i++) {
        const vtarget_cal_table_t *t = vtarget_cal_table_at(i);
        int worst = 0;
        for (uint32_t mv = vtarget_cal_min_mv(t); mv <= vtarget_cal_max_mv(t); mv++) {
            uint32_t d = vtarget_cal_mv_to_duty(t, (uint16_t)mv);
            int diff = abs((int)vtarget_cal_duty_to_mv(t, d) - (int)mv);
            if (diff > worst) worst = diff;
        }
        if (worst > 15) printf("    %s: worst round-trip error %d mV\n", t->name, worst);
        CHECK(worst <= 15);
    }
}

/* ------------------------------------------------------------------ settle */

static void test_settle_remaining(void)
{
    CHECK_EQ(vtarget_cal_settle_remaining_ms(0, 1000), 1000);
    CHECK_EQ(vtarget_cal_settle_remaining_ms(400, 1000), 600);
    CHECK_EQ(vtarget_cal_settle_remaining_ms(999, 1000), 1);
    CHECK_EQ(vtarget_cal_settle_remaining_ms(1000, 1000), 0);
    CHECK_EQ(vtarget_cal_settle_remaining_ms(5000, 1000), 0);
    CHECK_EQ(vtarget_cal_settle_remaining_ms(0, 0), 0);
    CHECK_EQ(vtarget_cal_settle_remaining_ms(UINT32_MAX, 1000), 0);
    CHECK(VTARGET_SETTLE_MS >= 700);   /* >= ~5 tau of the gate filter */
}

/* ------------------------------------------------------- Vendor3 encoding */

static void test_encode_info_layout(void)
{
    vtarget_info_t info = {
        .min_mv = 1326, .max_mv = 4200, .requested_mv = 3300,
        .settle_ms = 600, .name = "PCB-05",
    };
    uint8_t buf[VTARGET_INFO_MAX_LEN];
    size_t n = vtarget_cal_encode_info(buf, sizeof(buf), &info);

    /* 1326=0x052E 4200=0x1068 3300=0x0CE4 600=0x0258 */
    static const uint8_t expect[] = {
        0x00,             /* flags: not settled */
        0x2E, 0x05,       /* min */
        0x68, 0x10,       /* max */
        0xE4, 0x0C,       /* requested */
        0x58, 0x02,       /* settle ms */
        0x06,             /* name length */
        'P', 'C', 'B', '-', '0', '5',
    };
    CHECK_EQ(n, sizeof(expect));
    CHECK(memcmp(buf, expect, sizeof(expect)) == 0);

    /* settled */
    info.settle_ms = 0;
    n = vtarget_cal_encode_info(buf, sizeof(buf), &info);
    CHECK_EQ(n, sizeof(expect));
    CHECK_EQ(buf[0], 0x01);
    CHECK_EQ(buf[7], 0);
    CHECK_EQ(buf[8], 0);
}

static void test_encode_info_edge_cases(void)
{
    uint8_t buf[VTARGET_INFO_MAX_LEN];
    vtarget_info_t info = { .min_mv = 1, .max_mv = 2, .requested_mv = 0,
                            .settle_ms = 100000, .name = "CLUSTER" };

    /* settle saturates at 0xFFFF but the flag stays "not settled" */
    size_t n = vtarget_cal_encode_info(buf, sizeof(buf), &info);
    CHECK_EQ(n, 10 + 7);
    CHECK_EQ(buf[0], 0x00);
    CHECK_EQ(buf[7], 0xFF);
    CHECK_EQ(buf[8], 0xFF);

    /* too small a buffer, NULL arguments */
    CHECK_EQ(vtarget_cal_encode_info(buf, 16, &info), 0);        /* needs 17 */
    CHECK_EQ(vtarget_cal_encode_info(buf, 17, &info), 17);
    CHECK_EQ(vtarget_cal_encode_info(NULL, 64, &info), 0);
    CHECK_EQ(vtarget_cal_encode_info(buf, sizeof(buf), NULL), 0);
    info.name = NULL;
    CHECK_EQ(vtarget_cal_encode_info(buf, sizeof(buf), &info), 0);

    /* over-long names are truncated to NAME_MAX - 1 */
    info.name = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    n = vtarget_cal_encode_info(buf, sizeof(buf), &info);
    CHECK_EQ(n, 10 + VTARGET_CAL_NAME_MAX - 1);
    CHECK_EQ(buf[9], VTARGET_CAL_NAME_MAX - 1);

    /* empty name */
    info.name = "";
    n = vtarget_cal_encode_info(buf, sizeof(buf), &info);
    CHECK_EQ(n, 10);
    CHECK_EQ(buf[9], 0);
}

static void test_encode_info_fits_max_len_for_every_table(void)
{
    uint8_t buf[VTARGET_INFO_MAX_LEN];
    for (size_t i = 0; i < vtarget_cal_table_count(); i++) {
        const vtarget_cal_table_t *t = vtarget_cal_table_at(i);
        vtarget_info_t info = { .min_mv = vtarget_cal_min_mv(t), .max_mv = vtarget_cal_max_mv(t),
                                .requested_mv = 0, .settle_ms = 0, .name = t->name };
        size_t n = vtarget_cal_encode_info(buf, sizeof(buf), &info);
        CHECK_EQ(n, 10 + strlen(t->name));
        CHECK_EQ(buf[9], strlen(t->name));
    }
}

/* ------------------------------ generated tables vs the DMM sweeps (CSV) */

static int check_board_against_csv(const vtarget_cal_table_t *t, double *worst_out)
{
    char path[512];
    snprintf(path, sizeof(path), "%s/vtarget_%s_measurements.csv", g_csv_dir, t->name);
    FILE *f = fopen(path, "r");
    if (f == NULL) {
        return -1;   /* no sweep for this table (e.g. CLUSTER) */
    }

    char line[512];
    int rows = 0;
    double worst = 0.0, min_dmm = 1e9, max_dmm = 0.0;
    if (fgets(line, sizeof(line), f) == NULL) {   /* header */
        fclose(f);
        return 0;
    }
    while (fgets(line, sizeof(line), f) != NULL) {
        int duty = 0;
        double dmm = 0.0;
        /* board_id,duty_percent,commanded_mv,duty_count,adc_mv,dmm_mv,... */
        if (sscanf(line, "%*[^,],%*[^,],%*[^,],%d,%*[^,],%lf", &duty, &dmm) != 2) {
            continue;
        }
        rows++;
        double err = fabs((double)vtarget_cal_duty_to_mv(t, (uint32_t)duty) - dmm);
        if (err > worst) worst = err;
        if (dmm < min_dmm) min_dmm = dmm;
        if (dmm > max_dmm) max_dmm = dmm;
    }
    fclose(f);

    *worst_out = worst;
    /* table range equals the measured range (rounded to whole mV) */
    CHECK(fabs((double)vtarget_cal_min_mv(t) - min_dmm) <= 1.0);
    CHECK(fabs((double)vtarget_cal_max_mv(t) - max_dmm) <= 1.0);
    return rows;
}

static void test_board_tables_match_dmm_sweeps(void)
{
    int boards_checked = 0;
    for (size_t i = 1; i < vtarget_cal_table_count(); i++) {   /* skip CLUSTER */
        const vtarget_cal_table_t *t = vtarget_cal_table_at(i);
        double worst = 0.0;
        int rows = check_board_against_csv(t, &worst);
        if (rows < 0) {
            printf("    %s: no sweep CSV in %s (skipped)\n", t->name, g_csv_dir);
            continue;
        }
        boards_checked++;
        CHECK(rows >= 100);
        /* generator tolerance is 6 mV; allow rounding and the rows it dropped as noise */
        if (worst > 10.0) printf("    %s: worst fit error %.1f mV\n", t->name, worst);
        CHECK(worst <= 10.0);
    }
    if (boards_checked == 0) {
        printf("    no sweep CSVs found - board tables not compared with measurements\n");
    }
}

int main(int argc, char **argv)
{
    if (argc > 1) {
        g_csv_dir = argv[1];
    }

    RUN(test_find_by_name);
    RUN(test_table_registry);
    RUN(test_all_tables_valid);
    RUN(test_table_valid_rejects_bad_tables);
    RUN(test_default_table_unchanged);
    RUN(test_range_checks);
    RUN(test_mv_to_duty_points_and_clamping);
    RUN(test_interpolation_between_points);
    RUN(test_monotonic_over_full_range);
    RUN(test_roundtrip_within_one_duty_step);
    RUN(test_settle_remaining);
    RUN(test_encode_info_layout);
    RUN(test_encode_info_edge_cases);
    RUN(test_encode_info_fits_max_len_for_every_table);
    RUN(test_board_tables_match_dmm_sweeps);

    printf("\n%d checks, %d failures\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
