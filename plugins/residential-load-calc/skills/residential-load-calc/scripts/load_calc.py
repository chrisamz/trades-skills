"""Residential service / feeder load calculation and panel capacity check.

Methods (NEC section numbers shown for 2017-2023; the 2026 NEC moves Article 220
to Article 120, so 220.82 becomes 120.82 and so on):

  220.82  optional method, whole dwelling
  220.83  existing dwelling, adding load
  220.87  existing load from recorded maximum demand

Usage:
  python load_calc.py job.json              # markdown worksheet
  python load_calc.py job.json --format json
  python load_calc.py --template            # print a sample input file

Standard library only. Reads one JSON file, writes to stdout, touches nothing else.
The arithmetic is deterministic; every interpretation choice is an explicit input
and is echoed in the worksheet so an inspector can see what was assumed.
"""

import argparse
import json
import sys

STANDARD_SIZES_A = [100, 110, 125, 150, 175, 200, 225, 250, 300, 350, 400, 500, 600]

EDITIONS = {
    "2017": {"article": "220", "lighting_va_sqft": 3, "optional_first_tier_va": 10000,
             "evse_rule": "nameplate", "evse_default": "general", "provisional": False},
    "2020": {"article": "220", "lighting_va_sqft": 3, "optional_first_tier_va": 10000,
             "evse_rule": "nameplate", "evse_default": "general", "provisional": False},
    "2023": {"article": "220", "lighting_va_sqft": 3, "optional_first_tier_va": 10000,
             "evse_rule": "larger_of_7200", "evse_default": "general", "provisional": False},
    "2026": {"article": "120", "lighting_va_sqft": 2, "optional_first_tier_va": 8000,
             "evse_rule": "nameplate_else_7200", "evse_default": "full", "provisional": True},
}
EXISTING_FIRST_TIER_VA = 8000
REMAINDER_FACTOR = 0.40
EVSE_FLOOR_VA = 7200
HVAC_TYPES = ["ac", "heat_pump", "supplemental_heat", "space_heat", "thermal_storage"]
EVSE_TREATMENTS = ["general", "full", "continuous_125"]

TEMPLATE = {
    "job": "Smith residence - add 48 A EV charger",
    "edition": "2023",
    "method": "220.83",
    "system": {"voltage": 240, "service_rating_a": 200},
    "dwelling": {"floor_area_sqft": 2400, "small_appliance_circuits": 2, "laundry_circuits": 1},
    "appliances": [
        {"name": "Range", "va": 12000},
        {"name": "Dryer", "va": 5000},
        {"name": "Water heater", "va": 4500},
        {"name": "Dishwasher", "va": 1200},
        {"name": "Disposal", "amps": 7.2, "volts": 120},
    ],
    "hvac": [
        {"type": "ac", "name": "3.5 ton condenser + air handler", "va": 6000},
        {"type": "space_heat", "name": "Electric furnace", "va": 10000, "units": 1},
    ],
    "evse": [{"name": "Wall connector", "amps": 48, "new": True}],
    "options": {},
    "measured": {"peak_kw": None, "peak_amps": None, "basis": "utility_12mo",
                 "power_factor": 1.0, "has_pv_or_storage": False, "removed_va": 0},
}


NOTICE = (
    "Calculation aid only. This worksheet is not engineering, legal or code-compliance advice and is not a "
    "substitute for the adopted code book, a licensed electrician or the permit process. The adopted code "
    "edition, local amendments and the authority having jurisdiction govern. The rules were implemented from "
    "public summaries and were not verified against the code text; confirm every cited section and verify "
    "nameplate values on site before relying on the result. Provided as is, without warranty. Not affiliated "
    "with or endorsed by NFPA. NEC and National Electrical Code are registered trademarks of the National "
    "Fire Protection Association."
)


class InputError(Exception):
    pass


def num(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{what} must be a number, got {value!r}")
    if value < 0:
        raise InputError(f"{what} cannot be negative")
    return float(value)


def item_va(item, default_volts, what):
    """Nameplate VA from `va`, `kw`, or `amps` (x `volts`)."""
    if item.get("va") is not None:
        return num(item["va"], f"{what} va")
    if item.get("kw") is not None:
        return num(item["kw"], f"{what} kw") * 1000.0
    if item.get("amps") is not None:
        volts = num(item.get("volts", default_volts), f"{what} volts")
        return num(item["amps"], f"{what} amps") * volts
    return None


def sec(ed, suffix):
    return f"{ed['article']}.{suffix}"


def tiered(pool_va, first_tier_va):
    first = min(pool_va, first_tier_va)
    rest = max(pool_va - first_tier_va, 0.0)
    return first, rest, first + rest * REMAINDER_FACTOR


def evse_loads(job, ed, flags):
    """Each EVSE as (name, va, is_new, note)."""
    volts = job["system"]["voltage"]
    out = []
    for i, e in enumerate(job.get("evse", [])):
        name = e.get("name", f"EVSE {i + 1}")
        is_new = bool(e.get("new", False))
        if e.get("ems_limit_amps") is not None:
            v = num(e.get("volts", volts), f"{name} volts")
            va = num(e["ems_limit_amps"], f"{name} ems_limit_amps") * v
            cite = "120.7 / 625.42" if ed["article"] == "120" else "625.42 / 750.30"
            out.append((name, va, is_new, f"limited to {e['ems_limit_amps']:g} A by load management ({cite})"))
            flags.append(f"{name}: load taken at the load-management setpoint. The control system must be "
                         f"listed and the setpoint must not be field-adjustable past this value ({cite}).")
            continue
        va = item_va(e, volts, name)
        note = "nameplate"
        if ed["evse_rule"] == "larger_of_7200":
            if va is None or va < EVSE_FLOOR_VA:
                va, note = float(EVSE_FLOOR_VA), "7,200 VA minimum (220.57)"
        elif ed["evse_rule"] == "nameplate_else_7200":
            if va is None:
                va, note = float(EVSE_FLOOR_VA), "nameplate unknown, 7,200 VA used (120.57)"
        elif va is None:
            raise InputError(f"{name}: give va, kw or amps (no default EVSE load before the 2023 NEC)")
        out.append((name, va, is_new, note))
    return out


def hvac_totals(job, only=None):
    """Sum HVAC nameplate VA by type. `only` = True (new), False (existing), None (all)."""
    volts = job["system"]["voltage"]
    t = {k: 0.0 for k in HVAC_TYPES}
    units = 0
    interlocked = False
    for i, h in enumerate(job.get("hvac", [])):
        kind = h.get("type")
        if kind not in HVAC_TYPES:
            raise InputError(f"hvac[{i}] type must be one of {HVAC_TYPES}, got {kind!r}")
        if only is not None and bool(h.get("new", False)) != only:
            continue
        va = item_va(h, volts, f"hvac[{i}]")
        if va is None:
            raise InputError(f"hvac[{i}] needs va, kw or amps")
        t[kind] += va
        if kind == "space_heat":
            units += int(h.get("units", 1))
        if kind == "supplemental_heat" and h.get("interlocked"):
            interlocked = True
    t["space_heat_units"] = units
    t["interlocked"] = interlocked
    return t


def noncoincident(t):
    """Larger of total cooling vs total heating at nameplate (220.60 / 120.60)."""
    cooling = t["ac"] + t["heat_pump"]
    if t["interlocked"]:
        hp_heat = max(t["heat_pump"], t["supplemental_heat"])
    else:
        hp_heat = t["heat_pump"] + t["supplemental_heat"]
    heating = hp_heat + t["space_heat"] + t["thermal_storage"]
    if heating >= cooling:
        return heating, "heating"
    return cooling, "cooling"


def optional_hvac(t, ed):
    """220.82(C): largest of the six candidates."""
    cands = [("A/C at 100%", "82(C)(1)", t["ac"])]
    cands.append(("Heat pump at 100%", "82(C)(2)", t["heat_pump"]))
    if t["supplemental_heat"] > 0:
        if t["interlocked"]:
            cands.append(("Supplemental heat at 65% (compressor interlocked out)", "82(C)(3)",
                          0.65 * t["supplemental_heat"]))
        else:
            cands.append(("Heat pump at 100% + supplemental heat at 65%", "82(C)(3)",
                          t["heat_pump"] + 0.65 * t["supplemental_heat"]))
    if t["space_heat"] > 0:
        if t["space_heat_units"] >= 4:
            cands.append(("Space heat, 4 or more separately controlled units, at 40%", "82(C)(5)",
                          0.40 * t["space_heat"]))
        else:
            cands.append(("Space heat, fewer than 4 separately controlled units, at 65%", "82(C)(4)",
                          0.65 * t["space_heat"]))
    cands.append(("Thermal storage / continuous heating at 100%", "82(C)(6)", t["thermal_storage"]))
    label, suffix, va = max(cands, key=lambda c: c[2])
    return label, sec(ed, suffix), va


def general_pool(job, ed, lines, which=None, part=None):
    """Lighting, small-appliance/laundry circuits and appliances. `which` filters appliances by new flag."""
    d = job.get("dwelling", {})
    volts = job["system"]["voltage"]
    pool = 0.0
    cite = [sec(ed, part)] * 3 if part else [sec(ed, "82(B)(1)"), sec(ed, "82(B)(2)"), sec(ed, "82(B)(3)")]
    if which is not True:
        area = num(d.get("floor_area_sqft", 0), "floor_area_sqft")
        lighting = area * ed["lighting_va_sqft"]
        circuits = int(d.get("small_appliance_circuits", 2)) + int(d.get("laundry_circuits", 1))
        lines.append({"label": f"General lighting and receptacles, {area:,.0f} sq ft x {ed['lighting_va_sqft']} VA",
                      "section": cite[0], "va": lighting})
        lines.append({"label": f"Small-appliance and laundry circuits, {circuits} x 1,500 VA",
                      "section": cite[1], "va": circuits * 1500.0})
        pool += lighting + circuits * 1500.0
    for i, a in enumerate(job.get("appliances", [])):
        is_new = bool(a.get("new", False))
        if which is not None and is_new != which:
            continue
        name = a.get("name", f"Appliance {i + 1}")
        va = item_va(a, volts, name)
        if va is None:
            raise InputError(f"{name}: give va, kw or amps")
        lines.append({"label": name + (" (new)" if is_new else ""), "section": cite[2], "va": va})
        pool += va
    return pool


def calc_optional(job, ed, evse_treatment, flags):
    lines = []
    pool = general_pool(job, ed, lines)
    evse = evse_loads(job, ed, flags)
    outside = 0.0
    outside_lines = []
    for name, va, is_new, note in evse:
        tag = f"EVSE: {name} ({note})"
        if evse_treatment == "general":
            lines.append({"label": tag, "section": sec(ed, "82(B)(3)"), "va": va})
            pool += va
        else:
            f = 1.25 if evse_treatment == "continuous_125" else 1.0
            where = sec(ed, "82(D)") if ed["article"] == "120" else sec(ed, "57")
            outside_lines.append({"label": f"{tag} at {f:.0%}", "section": where, "va": va * f})
            outside += va * f
    first, rest, demand = tiered(pool, ed["optional_first_tier_va"])
    steps = [
        {"label": "General loads, connected", "va": pool},
        {"label": f"First {ed['optional_first_tier_va'] / 1000:g} kVA at 100%", "section": sec(ed, "82(B)"), "va": first},
        {"label": f"Remainder {rest:,.0f} VA at 40%", "section": sec(ed, "82(B)"), "va": rest * REMAINDER_FACTOR},
    ]
    label, where, hvac_va = optional_hvac(hvac_totals(job), ed)
    steps.append({"label": f"Heating / cooling, largest candidate: {label}", "section": where, "va": hvac_va})
    steps.extend(outside_lines)
    return lines, steps, demand + hvac_va + outside


def calc_existing(job, ed, evse_treatment, hvac_83a, flags):
    """220.83, 2017-2023 editions."""
    lines = []
    part = "83(B)" if any(h.get("new") for h in job.get("hvac", [])) else "83(A)"
    pool = general_pool(job, ed, lines, part=part)
    evse = evse_loads(job, ed, flags)
    outside = 0.0
    steps_tail = []
    for name, va, is_new, note in evse:
        tag = f"EVSE: {name}{' (new)' if is_new else ''} ({note})"
        if evse_treatment == "general":
            lines.append({"label": tag, "section": sec(ed, part), "va": va})
            pool += va
        else:
            f = 1.25 if evse_treatment == "continuous_125" else 1.0
            steps_tail.append({"label": f"{tag} at {f:.0%}", "section": "AHJ interpretation", "va": va * f})
            outside += va * f
    t = hvac_totals(job)
    adding_hvac = any(h.get("new") for h in job.get("hvac", []))
    if adding_hvac:
        many = t["space_heat_units"] >= 4
        if many and t["space_heat"] > 0:
            lines.append({"label": "Space heat, 4 or more separately controlled units", "section": sec(ed, part),
                          "va": t["space_heat"]})
            pool += t["space_heat"]
            t = dict(t)
            t["space_heat"] = 0.0
        hvac_va, side = noncoincident(t)
        steps_tail.insert(0, {"label": f"Heating / cooling at 100%, larger is {side}",
                              "section": sec(ed, part) + ", " + sec(ed, "60"), "va": hvac_va})
        outside += hvac_va
    else:
        hvac_va, side = noncoincident(t)
        if hvac_va > 0:
            if hvac_83a == "tiered":
                lines.append({"label": f"Existing heating / cooling, larger is {side}", "section": sec(ed, part),
                              "va": hvac_va})
                pool += hvac_va
            else:
                steps_tail.insert(0, {"label": f"Existing heating / cooling at 100%, larger is {side}",
                                      "section": "AHJ interpretation", "va": hvac_va})
                outside += hvac_va
    first, rest, demand = tiered(pool, EXISTING_FIRST_TIER_VA)
    steps = [
        {"label": "Loads in the tiered pool, connected", "va": pool},
        {"label": "First 8 kVA at 100%", "section": sec(ed, part), "va": first},
        {"label": f"Remainder {rest:,.0f} VA at 40%", "section": sec(ed, part), "va": rest * REMAINDER_FACTOR},
    ] + steps_tail
    return lines, steps, demand + outside, part


def calc_existing_2026(job, ed, flags):
    """120.83 (2026): existing loads tiered, new loads at their own factors. Provisional."""
    lines = []
    pool = general_pool(job, ed, lines, which=False, part="83")
    evse = evse_loads(job, ed, flags)
    new_steps = []
    new_total = 0.0
    for name, va, is_new, note in evse:
        if is_new:
            new_steps.append({"label": f"New EVSE: {name} ({note}) at 80%", "section": "Table 120.83", "va": va * 0.80})
            new_total += va * 0.80
        else:
            lines.append({"label": f"Existing EVSE: {name} ({note})", "section": "120.83", "va": va})
            pool += va
    old = hvac_totals(job, only=False)
    old_va, side = noncoincident(old)
    if old_va > 0:
        lines.append({"label": f"Existing heating / cooling, larger is {side}", "section": "120.83", "va": old_va})
        pool += old_va
    new = hvac_totals(job, only=True)
    resistance = new["supplemental_heat"] + new["space_heat"]
    if resistance > 0:
        new_steps.append({"label": "New central electric resistance heat at 80%", "section": "Table 120.83",
                          "va": resistance * 0.80})
        new_total += resistance * 0.80
    other_new = new["ac"] + new["heat_pump"] + new["thermal_storage"]
    scratch = []
    other_new += general_pool(job, ed, scratch, which=True)
    for ln in scratch:
        ln["section"] = "Table 120.83"
    if other_new > 0:
        new_steps.append({"label": f"Other new loads, {other_new:,.0f} VA at 50%", "section": "Table 120.83",
                          "va": other_new * 0.50})
        new_total += other_new * 0.50
    first, rest, demand = tiered(pool, EXISTING_FIRST_TIER_VA)
    steps = [
        {"label": "Existing loads, connected", "va": pool},
        {"label": "First 8 kVA at 100%", "section": "120.83", "va": first},
        {"label": f"Remainder {rest:,.0f} VA at 40%", "section": "120.83", "va": rest * REMAINDER_FACTOR},
    ] + new_steps
    return lines + scratch, steps, demand + new_total, "83"


def calc_measured(job, ed, evse_treatment, flags):
    m = job.get("measured") or {}
    volts = job["system"]["voltage"]
    pf = num(m.get("power_factor") or 1.0, "power_factor")
    if not 0 < pf <= 1:
        raise InputError("power_factor must be between 0 and 1")
    if m.get("peak_amps") is not None:
        peak_va = num(m["peak_amps"], "peak_amps") * volts
        src = f"{m['peak_amps']:g} A recorded x {volts:g} V"
    elif m.get("peak_kw") is not None:
        peak_va = num(m["peak_kw"], "peak_kw") * 1000.0 / pf
        src = f"{m['peak_kw']:g} kW recorded" + (f" / {pf:g} PF" if pf != 1 else " (kW taken as kVA)")
    else:
        raise InputError("method 220.87 needs measured.peak_kw or measured.peak_amps")
    basis = m.get("basis", "utility_12mo")
    if basis not in ("utility_12mo", "recording_30d"):
        raise InputError("measured.basis must be utility_12mo or recording_30d")
    if basis == "recording_30d":
        flags.append("30-day recording: must be continuous, 15-minute averaged demand on the highest loaded "
                     "phase, taken while occupied, and adjusted to include the larger of heating or cooling "
                     f"and other seasonal loads ({sec(ed, '87')} Exception).")
        if m.get("has_pv_or_storage"):
            flags.append("NOT PERMITTED AS ENTERED: the 30-day exception cannot be used where the service has "
                         "solar, wind or peak-shaving equipment. Use 12 months of utility data or a calculated method.")
    elif m.get("has_pv_or_storage"):
        flags.append("Solar or storage on site: utility interval data can show net import, which hides the true "
                     "house peak. Confirm the peak is gross consumption before relying on this result.")
    if m.get("peak_kw") is not None and m.get("peak_amps") is None:
        flags.append("Peak given in kW: confirm it is a demand value (15-minute or hourly interval peak), not "
                     "monthly energy divided by hours. Hourly data understates the 15-minute peak.")
    lines = [{"label": f"Maximum demand, {src}", "section": sec(ed, "87"), "va": peak_va}]
    steps = [{"label": "Existing maximum demand at 125%", "section": sec(ed, "87"), "va": peak_va * 1.25}]
    total = peak_va * 1.25
    for i, a in enumerate(job.get("appliances", [])):
        if a.get("new"):
            name = a.get("name", f"Appliance {i + 1}")
            va = item_va(a, volts, name)
            if va is None:
                raise InputError(f"{name}: give va, kw or amps")
            steps.append({"label": f"New load: {name} at 100%", "section": sec(ed, "87"), "va": va})
            total += va
    new_hvac = hvac_totals(job, only=True)
    hv = sum(new_hvac[k] for k in HVAC_TYPES)
    if hv > 0:
        steps.append({"label": "New heating / cooling equipment at 100%", "section": sec(ed, "87"), "va": hv})
        total += hv
        flags.append("New HVAC is added on top of a recorded peak that may already include the equipment it "
                     "replaces. If it replaces existing equipment, say so to the AHJ; the result here is conservative.")
    f = 1.25 if evse_treatment == "continuous_125" else 1.0
    for name, va, is_new, note in evse_loads(job, ed, flags):
        if is_new:
            steps.append({"label": f"New EVSE: {name} ({note}) at {f:.0%}", "section": sec(ed, "87"), "va": va * f})
            total += va * f
    removed = float(m.get("removed_va") or 0)
    if removed > 0:
        if ed["article"] == "120":
            steps.append({"label": "Removed load subtracted", "section": "120.87", "va": -removed})
            total -= removed
            flags.append("Removed load subtracted under 2026 120.87. This reading comes from a single published "
                         "summary; confirm against the code book.")
        else:
            flags.append(f"removed_va ignored: {sec(ed, '87')} in the {job['edition']} NEC has no provision "
                         "for subtracting removed loads.")
    return lines, steps, total


def run(job, evse_treatment=None, hvac_83a=None):
    edition = str(job.get("edition", ""))
    if edition not in EDITIONS:
        raise InputError(f"edition must be one of {list(EDITIONS)}; ask which NEC edition the AHJ has adopted")
    ed = EDITIONS[edition]
    method = str(job.get("method", "")).replace("120.", "220.")
    if method not in ("220.82", "220.83", "220.87"):
        raise InputError("method must be 220.82, 220.83 or 220.87 (120.82 / 120.83 / 120.87 also accepted)")
    system = job.get("system") or {}
    volts = num(system.get("voltage", 240), "system.voltage")
    if volts not in (240.0, 208.0):
        raise InputError("system.voltage must be 240 (120/240 V) or 208 (208Y/120 V, 3-wire)")
    job = dict(job, system=dict(system, voltage=volts))
    rating = num(system.get("service_rating_a", 0), "system.service_rating_a")
    opts = job.get("options") or {}
    evse_treatment = evse_treatment or opts.get("evse_treatment") or ed["evse_default"]
    if evse_treatment not in EVSE_TREATMENTS:
        raise InputError(f"options.evse_treatment must be one of {EVSE_TREATMENTS}")
    hvac_83a = hvac_83a or opts.get("hvac_83a", "tiered")
    if hvac_83a not in ("tiered", "full"):
        raise InputError("options.hvac_83a must be tiered or full")

    flags = []
    readings = {"evse": None, "hvac_83a": None}
    has_evse = bool(job.get("evse"))
    if method == "220.82":
        lines, steps, total = calc_optional(job, ed, evse_treatment, flags)
        cite = sec(ed, "82")
        if has_evse:
            readings["evse"] = evse_treatment
        if 0 < rating < 100:
            flags.append(f"{cite} applies only where the service or feeder is 100 A or larger. Use the standard method.")
    elif method == "220.83":
        if ed["article"] == "120":
            lines, steps, total, part = calc_existing_2026(job, ed, flags)
        else:
            lines, steps, total, part = calc_existing(job, ed, evse_treatment, hvac_83a, flags)
            if has_evse:
                readings["evse"] = evse_treatment
            if part == "83(A)" and job.get("hvac"):
                readings["hvac_83a"] = hvac_83a
        cite = sec(ed, part)
    else:
        if evse_treatment == "general":
            evse_treatment = "full"
        lines, steps, total = calc_measured(job, ed, evse_treatment, flags)
        cite = sec(ed, "87")
        if any(e.get("new") for e in job.get("evse", [])):
            readings["evse"] = evse_treatment

    if ed["provisional"]:
        flags.append("2026 NEC rules here are built from published change summaries, not checked line by line "
                     "against the code book. Treat as provisional and verify the factors before submitting.")
    if not any(a.get("new") for a in job.get("appliances", []) + job.get("evse", []) + job.get("hvac", [])) \
            and method != "220.82":
        flags.append("No load is marked \"new\": true. This method is for adding load; mark what is being added.")

    amps = total / volts
    result = {
        "job": job.get("job", ""),
        "edition": edition,
        "method": cite,
        "voltage": volts,
        "lines": lines,
        "steps": steps,
        "total_va": round(total),
        "calculated_amps": round(amps, 1),
        "service_rating_a": rating or None,
        "readings": readings,
        "flags": flags,
        "minimum_standard_size_a": next((s for s in STANDARD_SIZES_A if s >= amps), None),
        "notice": NOTICE,
    }
    if rating:
        result["fits"] = amps <= rating
        result["headroom_a"] = round(rating - amps, 1)
        result["utilization_pct"] = round(100 * amps / rating, 1)
    return result


EVSE_LABEL = {
    "general": "in the demand tiers, as an appliance",
    "full": "at 100%, after the tiers",
    "continuous_125": "at 125% (continuous load), after the tiers",
}
HVAC_LABEL = {
    "tiered": "in the demand tiers",
    "full": "at 100%",
}
BRANCH_SIZES_A = [15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125]


def reading_label(readings):
    parts = []
    if readings.get("evse"):
        parts.append("EV charger " + EVSE_LABEL[readings["evse"]])
    if readings.get("hvac_83a"):
        parts.append("existing heating / cooling " + HVAC_LABEL[readings["hvac_83a"]])
    return "; ".join(parts)


def row(label, r, used=False, evse=None, hvac=None):
    return {"reading": label, "evse": EVSE_LABEL.get(evse, ""), "hvac": HVAC_LABEL.get(hvac, ""),
            "total_va": r["total_va"], "calculated_amps": r["calculated_amps"],
            "fits": r.get("fits"), "used": used}


def reading_combos(job, base):
    """Every defensible combination of readings for this job; one entry when nothing varies."""
    ed = EDITIONS[base["edition"]]
    used = base["readings"]
    if ed["article"] == "120" or not (used["evse"] or used["hvac_83a"]):
        return [(used["evse"], used["hvac_83a"])]
    method = str(job.get("method", "")).replace("120.", "220.")
    evse_opts = [None]
    if used["evse"]:
        evse_opts = ["full", "continuous_125"] if method == "220.87" else EVSE_TREATMENTS
    hvac_opts = ["tiered", "full"] if used["hvac_83a"] else [None]
    return [(e, h) for e in evse_opts for h in hvac_opts]


def alternates(job, base):
    """The same job under every defensible reading, so the user sees how far the answer moves.

    Pre-2026 code leaves the EV charger's place in these methods open, and inspectors differ on
    existing heating under 220.83(A). The 2026 NEC fixes the factors, so there is nothing to vary.
    """
    ed = EDITIONS[base["edition"]]
    method = str(job.get("method", "")).replace("120.", "220.")
    used = base["readings"]
    rows = []
    combos = reading_combos(job, base)
    if len(combos) > 1:
        for e, h in combos:
            r = run(job, evse_treatment=e, hvac_83a=h)
            rows.append(row(reading_label({"evse": e, "hvac_83a": h}), r, evse=e, hvac=h,
                            used=(e == used["evse"] and h == used["hvac_83a"])))
    if method == "220.83":
        whole = run(dict(job, method="220.82"))
        label = f"Cross-check: whole-house optional method ({sec(ed, '82')})"
        if whole["readings"]["evse"] and ed["article"] != "120":
            label += ", " + reading_label(whole["readings"])
        rows.append(row(label, whole))
    return rows


def charger_limits(job, base):
    """Largest load-management setpoint that fits, for each reading where the nameplate does not."""
    rating = base.get("service_rating_a")
    new = [e for e in job.get("evse", []) if e.get("new") and e.get("ems_limit_amps") is None]
    if not rating or len(new) != 1:
        return []
    volts = base["voltage"]
    nameplate_va = item_va(new[0], volts, "EVSE")
    if nameplate_va is None:
        return []
    top = int(nameplate_va / float(new[0].get("volts", volts)))
    out = []
    for e, h in reading_combos(job, base):
        if run(job, evse_treatment=e, hvac_83a=h).get("fits"):
            continue
        best = None
        for amps in range(top - 1, 5, -1):
            trial = dict(job, evse=[dict(x, ems_limit_amps=amps) if x is new[0] else x for x in job["evse"]])
            if run(trial, evse_treatment=e, hvac_83a=h).get("fits"):
                best = amps
                break
        out.append({"reading": reading_label({"evse": e, "hvac_83a": h}) or "as calculated",
                    "evse": EVSE_LABEL.get(e, ""), "hvac": HVAC_LABEL.get(h, ""), "max_amps": best})
    return out


def branch_circuits(job, base):
    """Minimum branch-circuit rating for each new EV charger (continuous load, 125%)."""
    volts = base["voltage"]
    out = []
    for i, e in enumerate(job.get("evse", [])):
        if not e.get("new"):
            continue
        va = item_va(e, volts, "EVSE")
        if va is None:
            continue
        amps = va / float(e.get("volts", volts))
        size = next((b for b in BRANCH_SIZES_A if b >= amps * 1.25 - 1e-9), None)
        out.append({"name": e.get("name", f"EVSE {i + 1}"), "load_amps": round(amps, 1),
                    "min_circuit_amps": size})
    return out


def to_markdown(r):
    out = []
    title = r["job"] or "Load calculation"
    out.append(f"# {title}")
    out.append("")
    out.append(f"Method: NEC {r['edition']} {r['method']}  |  System: {r['voltage']:g} V single-phase, 3-wire")
    out.append("")
    out.append("## Connected loads")
    out.append("")
    out.append("| Load | Section | VA |")
    out.append("|---|---|---:|")
    for ln in r["lines"]:
        out.append(f"| {ln['label']} | {ln.get('section', '')} | {ln['va']:,.0f} |")
    out.append("")
    out.append("## Demand calculation")
    out.append("")
    out.append("| Step | Section | VA |")
    out.append("|---|---|---:|")
    for st in r["steps"]:
        out.append(f"| {st['label']} | {st.get('section', '')} | {st['va']:,.0f} |")
    out.append(f"| **Calculated load** | | **{r['total_va']:,.0f}** |")
    out.append("")
    out.append(f"**{r['total_va']:,.0f} VA / {r['voltage']:g} V = {r['calculated_amps']:.1f} A**")
    out.append("")
    if r.get("service_rating_a"):
        verdict = "FITS" if r["fits"] else "DOES NOT FIT"
        out.append(f"Service or feeder rating: {r['service_rating_a']:g} A. **{verdict}** "
                   f"({r['utilization_pct']:.1f}% of rating, headroom {r['headroom_a']:+.1f} A).")
    if r.get("minimum_standard_size_a"):
        out.append(f"Smallest standard rating that carries this load: {r['minimum_standard_size_a']} A.")
    out.append("")
    alts = r.get("alternates") or []
    if any(a["used"] for a in alts):
        out.append("## Same job under other readings of the code")
        out.append("")
        out.append("Editions before 2026 do not say how an EV charger enters this calculation, and inspectors "
                   "differ. The row marked \"used above\" is the worksheet result.")
        out.append("")
    elif alts:
        out.append("## Cross-check")
        out.append("")
    two = any(a["hvac"] for a in alts)

    def cells(a):
        if a["reading"].startswith("Cross-check"):
            return [a["reading"]] + ([""] if two else [])
        if not a["evse"] and not a["hvac"]:
            return [a["reading"]] + ([""] if two else [])
        first = a["evse"] or a["hvac"]
        return [first, a["hvac"]] if two else [first]

    if two:
        head = ["EV charger taken", "Existing heating / cooling taken"]
    else:
        head = ["EV charger taken"] if any(a["evse"] for a in alts) else ["Reading"]
    if alts:
        out.append("| " + " | ".join(head) + " | VA | Amps | Fits |")
        out.append("|" + "---|" * len(head) + "---:|---:|---|")
        for a in alts:
            fits = "" if a["fits"] is None else ("yes" if a["fits"] else "**no**")
            c = cells(a)
            if a["used"]:
                c[-1] = (c[-1] + " (used above)").strip()
            out.append("| " + " | ".join(c) + f" | {a['total_va']:,.0f} | {a['calculated_amps']:.1f} | {fits} |")
        out.append("")
    if r.get("charger_limits"):
        out.append("## Largest charger setting that fits")
        out.append("")
        out.append("With a listed load-management system limiting the charger (625.42), for each reading that "
                   "fails at full nameplate:")
        out.append("")
        out.append("| " + " | ".join(head) + " | Maximum setting |")
        out.append("|" + "---|" * len(head) + "---:|")
        for c in r["charger_limits"]:
            amps = "none fits" if c["max_amps"] is None else f"{c['max_amps']} A"
            lead = [c["evse"] or c["reading"]] + ([c["hvac"]] if two else [])
            out.append("| " + " | ".join(lead) + f" | {amps} |")
        out.append("")
    if r.get("branch_circuits"):
        out.append("## Branch circuit for the new charger")
        out.append("")
        for c in r["branch_circuits"]:
            size = f"{c['min_circuit_amps']} A" if c["min_circuit_amps"] else "over 125 A, size separately"
            out.append(f"- {c['name']}: {c['load_amps']:g} A continuous x 125% = minimum {size} circuit "
                       "(625.41). Conductor size depends on wiring method and terminal ratings; not covered here.")
        out.append("")
    if r["flags"]:
        out.append("## Check before relying on this")
        out.append("")
        for f in r["flags"]:
            out.append(f"- {f}")
        out.append("")
    out.append("## Notice")
    out.append("")
    out.append(NOTICE)
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Residential load calculation and panel capacity check")
    p.add_argument("input", nargs="?", help="job JSON file, or - for stdin")
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument("--template", action="store_true", help="print a sample input and exit")
    args = p.parse_args(argv)
    if args.template:
        print(json.dumps(TEMPLATE, indent=2))
        return 0
    if not args.input:
        p.error("give a job JSON file, or --template")
    try:
        if args.input == "-":
            job = json.load(sys.stdin)
        else:
            with open(args.input, encoding="utf-8") as fh:
                job = json.load(fh)
        result = run(job)
        result["alternates"] = alternates(job, result)
        result["charger_limits"] = charger_limits(job, result)
        result["branch_circuits"] = branch_circuits(job, result)
    except (InputError, json.JSONDecodeError, OSError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(to_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
