"""Shared VTarget calibration constants for the test scripts.

Mirror of VTARGET_CAL_TABLE in main/vtarget_pwm.c (25-point DMM table, median of
the PCB-04/08/09/10 cluster). Keep it in sync with the firmware. Vendor2 (0x82)
accepts only VTARGET_MIN_MV..VTARGET_MAX_MV and maps the request to a PWM duty
through this table, so only duty counts DUTY_MIN..DUTY_MAX are reachable.

VTarget settles slowly (gate filter tau ~ 145 ms with R4=22k, R5=43k, C2=10uF),
so wait >= 1 s after a change for a settled voltage.
"""

MAX_DUTY = 1023

# (duty_count, voltage_mV): duty ascending, voltage descending
FW_CAL_TABLE = [
    (358, 4200), (559, 4072), (612, 3943), (647, 3811), (678, 3650),
    (699, 3514), (716, 3385), (732, 3250), (747, 3110), (763, 2945),
    (775, 2813), (787, 2674), (797, 2552), (808, 2418), (819, 2281),
    (831, 2132), (841, 2010), (851, 1892), (862, 1772), (872, 1673),
    (883, 1575), (898, 1465), (912, 1397), (929, 1361), (982, 1326),
]

VTARGET_MAX_MV = FW_CAL_TABLE[0][1]    # 4200
VTARGET_MIN_MV = FW_CAL_TABLE[-1][1]   # 1326
DUTY_MIN = FW_CAL_TABLE[0][0]          # 358  (max voltage)
DUTY_MAX = FW_CAL_TABLE[-1][0]         # 982  (min voltage)
DUTY_MIN_PCT = 100.0 * DUTY_MIN / MAX_DUTY
DUTY_MAX_PCT = 100.0 * DUTY_MAX / MAX_DUTY


def mv_to_duty(voltage_mv):
    """Firmware mapping (vtarget_set_voltage): requested mV -> PWM duty count."""
    if voltage_mv >= VTARGET_MAX_MV:
        return DUTY_MIN
    if voltage_mv <= VTARGET_MIN_MV:
        return DUTY_MAX
    for (duty_lo, v_hi), (duty_hi, v_lo) in zip(FW_CAL_TABLE, FW_CAL_TABLE[1:]):
        if v_lo <= voltage_mv <= v_hi:
            return duty_lo + (duty_hi - duty_lo) * (v_hi - voltage_mv) // (v_hi - v_lo)
    return DUTY_MAX


def duty_to_mv(duty_count):
    """Inverse mapping: PWM duty count -> mV request that makes the firmware
    drive (approximately) that duty. Clamped to the reachable duty window."""
    duty_count = max(DUTY_MIN, min(DUTY_MAX, round(duty_count)))
    for (duty_lo, v_hi), (duty_hi, v_lo) in zip(FW_CAL_TABLE, FW_CAL_TABLE[1:]):
        if duty_lo <= duty_count <= duty_hi:
            return round(v_hi - (v_hi - v_lo) * (duty_count - duty_lo) / (duty_hi - duty_lo))
    return VTARGET_MIN_MV


def duty_pct_to_mv(duty_pct):
    """Duty percent -> mV request (clamped to the reachable duty window)."""
    return duty_to_mv(MAX_DUTY * duty_pct / 100.0)


def reachable_duty_pct(duty_pct):
    """True if the duty percent lies inside the window reachable via Vendor2."""
    return DUTY_MIN_PCT <= duty_pct <= DUTY_MAX_PCT
