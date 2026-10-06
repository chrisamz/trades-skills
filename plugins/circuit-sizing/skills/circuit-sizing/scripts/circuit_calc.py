"""Branch-circuit and feeder sizing: conductor, breaker, voltage drop, conduit fill, box fill.

Four calculations, chosen by the "calc" field of the input JSON:

  wire          conductor size, overcurrent device, equipment ground and voltage drop
  nameplate     the same for air-conditioning and heat-pump equipment, from its nameplate
  voltage_drop  voltage drop for a given conductor
  conduit_fill  smallest raceway for a group of conductors, or a check of a given raceway
  box_fill      required box volume, or a check of a given box

Usage:
  python circuit_calc.py job.json              # markdown worksheet
  python circuit_calc.py job.json --format json
  python circuit_calc.py --template wire       # sample input (wire, nameplate, voltage_drop, conduit_fill, box_fill)

A wire or nameplate job may carry a "conduit" entry to size the raceway for the result in the same run,
and {"jobs": [...]} runs several calculations into one worksheet with a single notice.

Standard library only. Reads one JSON file, writes to stdout, touches nothing else.
Table values are the commonly published ones; see references/method-notes.md for how they were checked.
"""

import argparse
import json
import math
import sys

SIZES = ["14", "12", "10", "8", "6", "4", "3", "2", "1", "1/0", "2/0", "3/0", "4/0",
         "250", "300", "350", "400", "500", "600"]

# Ampacity, not more than three current-carrying conductors, 30 C ambient: (60 C, 75 C, 90 C)
AMPACITY = {
    "cu": {"14": (15, 20, 25), "12": (20, 25, 30), "10": (30, 35, 40), "8": (40, 50, 55),
           "6": (55, 65, 75), "4": (70, 85, 95), "3": (85, 100, 115), "2": (95, 115, 130),
           "1": (110, 130, 145), "1/0": (125, 150, 170), "2/0": (145, 175, 195),
           "3/0": (165, 200, 225), "4/0": (195, 230, 260), "250": (215, 255, 290),
           "300": (240, 285, 320), "350": (260, 310, 350), "400": (280, 335, 380),
           "500": (320, 380, 430), "600": (350, 420, 475)},
    "al": {"12": (15, 20, 25), "10": (25, 30, 35), "8": (35, 40, 45), "6": (40, 50, 55),
           "4": (55, 65, 75), "3": (65, 75, 85), "2": (75, 90, 100), "1": (85, 100, 115),
           "1/0": (100, 120, 135), "2/0": (115, 135, 150), "3/0": (130, 155, 175),
           "4/0": (150, 180, 205), "250": (170, 205, 230), "300": (195, 230, 260),
           "350": (210, 250, 280), "400": (225, 270, 305), "500": (260, 310, 350),
           "600": (285, 340, 385)},
}
TEMP_COLUMN = {60: 0, 75: 1, 90: 2}

# Ambient correction, 30 C base: (upper bound of band in C, factor at 60, 75, 90). None = not permitted.
AMBIENT = [(10, 1.29, 1.20, 1.15), (15, 1.22, 1.15, 1.12), (20, 1.15, 1.11, 1.08), (25, 1.08, 1.05, 1.04),
           (30, 1.00, 1.00, 1.00), (35, 0.91, 0.94, 0.96), (40, 0.82, 0.88, 0.91), (45, 0.71, 0.82, 0.87),
           (50, 0.58, 0.75, 0.82), (55, 0.41, 0.67, 0.76), (60, None, 0.58, 0.71), (65, None, 0.47, 0.65),
           (70, None, 0.33, 0.58), (75, None, None, 0.50), (80, None, None, 0.41), (85, None, None, 0.29)]

# More than three current-carrying conductors: (maximum count, factor)
BUNDLING = [(3, 1.00), (6, 0.80), (9, 0.70), (20, 0.50), (30, 0.45), (40, 0.40), (10 ** 6, 0.35)]

STANDARD_OCPD = [15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200,
                 225, 250, 300, 350, 400, 450, 500, 600]
SMALL_CONDUCTOR_MAX = {"cu": {"14": 15, "12": 20, "10": 30}, "al": {"12": 15, "10": 25}}

# Minimum equipment grounding conductor by overcurrent device rating: (rating up to, cu, al)
EGC = [(15, "14", "12"), (20, "12", "10"), (60, "10", "8"), (100, "8", "6"), (200, "6", "4"),
       (300, "4", "2"), (400, "3", "1"), (500, "2", "1/0"), (600, "1", "2/0")]

CIRCULAR_MILS = {"14": 4110, "12": 6530, "10": 10380, "8": 16510, "6": 26240, "4": 41740, "3": 52620,
                 "2": 66360, "1": 83690, "1/0": 105600, "2/0": 133100, "3/0": 167800, "4/0": 211600,
                 "250": 250000, "300": 300000, "350": 350000, "400": 400000, "500": 500000, "600": 600000}

# Direct-current resistance, ohms per 1,000 ft at 75 C, stranded: uncoated copper, aluminum
RESISTANCE = {
    "cu": {"14": 3.14, "12": 1.98, "10": 1.24, "8": 0.778, "6": 0.491, "4": 0.308, "3": 0.245, "2": 0.194,
           "1": 0.154, "1/0": 0.122, "2/0": 0.0967, "3/0": 0.0766, "4/0": 0.0608, "250": 0.0515,
           "300": 0.0429, "350": 0.0367, "400": 0.0321, "500": 0.0258, "600": 0.0214},
    "al": {"12": 3.25, "10": 2.04, "8": 1.28, "6": 0.808, "4": 0.508, "3": 0.403, "2": 0.319, "1": 0.253,
           "1/0": 0.201, "2/0": 0.159, "3/0": 0.126, "4/0": 0.100, "250": 0.0847, "300": 0.0707,
           "350": 0.0605, "400": 0.0529, "500": 0.0424, "600": 0.0353},
}

# Effective impedance at 0.85 power factor, ohms to neutral per 1,000 ft, three single conductors in
# conduit, by conduit material (Chapter 9, Table 9). 500 and 600 kcmil computed from R and X.
_Z_SIZES_CU = SIZES
_Z_SIZES_AL = SIZES[1:]
EFFECTIVE_Z = {
    "cu": {
        "pvc": dict(zip(_Z_SIZES_CU, [2.7, 1.7, 1.1, 0.69, 0.44, 0.29, 0.23, 0.19, 0.16, 0.13, 0.11, 0.088,
                                      0.074, 0.066, 0.059, 0.053, 0.049, 0.043, 0.040])),
        "aluminum": dict(zip(_Z_SIZES_CU, [2.7, 1.7, 1.1, 0.69, 0.45, 0.29, 0.24, 0.19, 0.16, 0.13, 0.11, 0.092,
                                           0.078, 0.070, 0.063, 0.058, 0.053, 0.048, 0.044])),
        "steel": dict(zip(_Z_SIZES_CU, [2.7, 1.7, 1.1, 0.70, 0.45, 0.30, 0.24, 0.20, 0.16, 0.13, 0.11, 0.094,
                                        0.080, 0.073, 0.065, 0.060, 0.056, 0.050, 0.047])),
    },
    "al": {
        "pvc": dict(zip(_Z_SIZES_AL, [2.8, 1.8, 1.1, 0.71, 0.46, 0.37, 0.30, 0.24, 0.19, 0.16, 0.13, 0.11,
                                      0.094, 0.082, 0.073, 0.066, 0.057, 0.051])),
        "aluminum": dict(zip(_Z_SIZES_AL, [2.8, 1.8, 1.1, 0.72, 0.46, 0.37, 0.30, 0.24, 0.20, 0.16, 0.13, 0.11,
                                           0.098, 0.086, 0.077, 0.071, 0.061, 0.055])),
        "steel": dict(zip(_Z_SIZES_AL, [2.8, 1.8, 1.1, 0.72, 0.46, 0.37, 0.30, 0.25, 0.20, 0.16, 0.14, 0.11,
                                        0.10, 0.088, 0.080, 0.073, 0.064, 0.058])),
    },
}
CONDUIT_MATERIAL = {"steel": "steel", "emt": "steel", "rmc": "steel", "imc": "steel", "pvc": "pvc",
                    "pvc40": "pvc", "pvc80": "pvc", "nonmetallic": "pvc", "cable": "pvc", "nm": "pvc",
                    "aluminum": "aluminum"}

TRADE_SIZES = ["1/2", "3/4", "1", "1-1/4", "1-1/2", "2", "2-1/2", "3", "3-1/2", "4"]
# Raceway total internal area, square inches, by trade size
RACEWAY_AREA = {
    "emt": [0.304, 0.533, 0.864, 1.496, 2.036, 3.356, 5.858, 8.846, 11.545, 14.753],
    "imc": [0.342, 0.586, 0.959, 1.647, 2.225, 3.630, 5.135, 7.922, 10.584, 13.631],
    "rmc": [0.314, 0.549, 0.887, 1.526, 2.071, 3.408, 4.866, 7.499, 10.010, 12.882],
    "pvc40": [0.285, 0.508, 0.832, 1.453, 1.986, 3.291, 4.695, 7.268, 9.737, 12.554],
    "pvc80": [0.217, 0.409, 0.688, 1.237, 1.711, 2.874, 4.119, 6.442, 8.688, 11.258],
}
RACEWAY_NAME = {"emt": "EMT", "imc": "IMC", "rmc": "RMC", "pvc40": "PVC Schedule 40", "pvc80": "PVC Schedule 80"}
# Insulated conductor area, square inches
CONDUCTOR_AREA = {
    "thhn": {"14": 0.0097, "12": 0.0133, "10": 0.0211, "8": 0.0366, "6": 0.0507, "4": 0.0824, "3": 0.0973,
             "2": 0.1158, "1": 0.1562, "1/0": 0.1855, "2/0": 0.2223, "3/0": 0.2679, "4/0": 0.3237,
             "250": 0.3970, "300": 0.4608, "350": 0.5242, "400": 0.5863, "500": 0.7073},
    "xhhw": {"14": 0.0139, "12": 0.0181, "10": 0.0243, "8": 0.0437, "6": 0.0590, "4": 0.0814, "3": 0.0962,
             "2": 0.1146, "1": 0.1534, "1/0": 0.1825, "2/0": 0.2190, "3/0": 0.2642, "4/0": 0.3197,
             "250": 0.3904, "300": 0.4536, "350": 0.5166, "400": 0.5782, "500": 0.6984},
}
INSULATION_ALIAS = {"thhn": "thhn", "thwn": "thhn", "thwn-2": "thhn", "thhn/thwn-2": "thhn",
                    "xhhw": "xhhw", "xhhw-2": "xhhw"}

# Box fill: volume allowance per conductor, cubic inches
BOX_ALLOWANCE = {"18": 1.50, "16": 1.75, "14": 2.00, "12": 2.25, "10": 2.50, "8": 3.00, "6": 5.00}
STANDARD_BOXES = [
    ("3 x 2 x 1-1/2 device box", 7.5), ("3 x 2 x 2 device box", 10.0), ("3 x 2 x 2-1/4 device box", 10.5),
    ("3 x 2 x 2-1/2 device box", 12.5), ("3 x 2 x 2-3/4 device box", 14.0), ("3 x 2 x 3-1/2 device box", 18.0),
    ("4 x 1-1/4 round or octagonal", 12.5), ("4 x 1-1/2 round or octagonal", 15.5),
    ("4 x 2-1/8 round or octagonal", 21.5), ("4 x 1-1/4 square", 18.0), ("4 x 1-1/2 square", 21.0),
    ("4 x 2-1/8 square", 30.3), ("4-11/16 x 1-1/4 square", 25.5), ("4-11/16 x 1-1/2 square", 29.5),
    ("4-11/16 x 2-1/8 square", 42.0),
]

NOTICE = (
    "Calculation aid only. This worksheet is not engineering, legal or code-compliance advice and is not a "
    "substitute for the adopted code book, a licensed electrician or the permit process. The adopted code "
    "edition, local amendments and the authority having jurisdiction govern. Table values and rules were "
    "entered from public sources and cross-checked against independent published copies, not against the "
    "code book itself; confirm every cited section "
    "and verify equipment markings on site before relying on the result. Provided as is, without warranty. "
    "Not affiliated with or endorsed by NFPA. NEC and National Electrical Code are registered trademarks of "
    "the National Fire Protection Association."
)

TEMPLATES = {
    "wire": {"calc": "wire", "job": "48 A EV charger, 50 ft run", "load_amps": 48, "continuous": True,
             "voltage": 240, "phase": 1, "material": "cu", "wiring": "raceway", "insulation": "thhn",
             "terminal_temp": 75, "ambient_c": 30, "current_carrying_conductors": 2,
             "length_ft": 50, "max_voltage_drop_pct": 3,
             "conduit": {"raceway": "emt", "insulation": "thhn", "neutral": False}},
    "nameplate": {"calc": "nameplate", "job": "3 ton condenser", "mca": 24.3, "mocp": 40, "voltage": 240,
                  "phase": 1, "material": "cu", "wiring": "raceway", "terminal_temp": 75, "ambient_c": 30,
                  "current_carrying_conductors": 2, "length_ft": 40, "max_voltage_drop_pct": 3,
                  "existing_size": None, "breaker_a": None},
    "voltage_drop": {"calc": "voltage_drop", "job": "Shed feeder", "load_amps": 30, "voltage": 240, "phase": 1,
                     "material": "cu", "size": "8", "length_ft": 180, "max_voltage_drop_pct": 3},
    "conduit_fill": {"calc": "conduit_fill", "job": "Range feed", "raceway": "emt", "trade_size": None,
                     "nipple": False, "breaker_a": None,
                     "conductors": [{"size": "6", "insulation": "thhn", "count": 3},
                                    {"size": "10", "insulation": "thhn", "count": 1}]},
    "box_fill": {"calc": "box_fill", "job": "Receptacle, two 12-2 cables", "edition": "2023",
                 "conductors": [{"size": "12", "count": 4}], "grounds": {"size": "12", "count": 2},
                 "internal_clamps": True, "support_fittings": 0,
                 "devices": [{"largest_size": "12", "count": 1}], "box_volume_in3": None},
}


class InputError(Exception):
    pass


def num(value, what, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{what} must be a number, got {value!r}")
    if value < 0 or (positive and value == 0):
        raise InputError(f"{what} must be {'greater than zero' if positive else 'zero or more'}")
    return float(value)


def norm_size(value, what="size"):
    s = str(value).strip().lower().replace("awg", "").replace("kcmil", "").replace("mcm", "").replace("#", "")
    s = s.strip()
    s = {"0": "1/0", "00": "2/0", "000": "3/0", "0000": "4/0"}.get(s, s)
    if s not in SIZES and s not in BOX_ALLOWANCE:
        raise InputError(f"{what}: unknown conductor size {value!r}")
    return s


def label(size):
    return f"{size} kcmil" if size.isdigit() and int(size) >= 250 else f"{size} AWG"


def material_of(job):
    m = str(job.get("material", "cu")).lower()
    m = {"copper": "cu", "aluminum": "al", "aluminium": "al"}.get(m, m)
    if m not in ("cu", "al"):
        raise InputError("material must be cu or al")
    return m


def ambient_factor(ambient_c, temp):
    for upper, f60, f75, f90 in AMBIENT:
        if ambient_c <= upper:
            return {60: f60, 75: f75, 90: f90}[temp]
    return None


def bundling_factor(count):
    for upper, f in BUNDLING:
        if count <= upper:
            return f
    return 0.35


def next_standard(amps):
    return next((s for s in STANDARD_OCPD if s >= amps - 1e-9), None)


def conduit_material_of(job):
    spec = job.get("conduit")
    named = (spec.get("raceway") if isinstance(spec, dict) else spec) or job.get("raceway")
    raw = str(job.get("raceway_material") or named
              or ("nm" if str(job.get("wiring", "")).lower() == "nm" else "steel"))
    key = raw.lower().replace(" ", "")
    if key not in CONDUIT_MATERIAL:
        raise InputError(f"raceway_material must be one of {sorted(CONDUIT_MATERIAL)}")
    return CONDUIT_MATERIAL[key]


def ohms_per_kft(material, size, conduit="steel"):
    """Larger of dc resistance and effective impedance at 0.85 power factor.

    Direct-current resistance governs for small conductors; for 1/0 AWG and larger, reactance makes
    the effective impedance the larger number. Taking the larger of the two is conservative for both.
    """
    return max(RESISTANCE[material][size], EFFECTIVE_Z[material][conduit][size])


def vd_volts(material, size, amps, length_ft, phase, conduit="steel"):
    k = 2.0 if phase == 1 else math.sqrt(3)
    return k * length_ft * ohms_per_kft(material, size, conduit) * amps / 1000.0


def egc_size(ocpd, material, circuit_size=None):
    """Minimum equipment ground for the device rating, never larger than the circuit conductors (250.122(A))."""
    for upper, cu, al in EGC:
        if ocpd <= upper:
            size = cu if material == "cu" else al
            if circuit_size is not None and SIZES.index(size) > SIZES.index(circuit_size):
                return circuit_size
            return size
    return None


def system_of(job):
    voltage = num(job.get("voltage", 240), "voltage", positive=True)
    phase = int(job.get("phase", 1))
    if phase not in (1, 3):
        raise InputError("phase must be 1 or 3")
    return voltage, phase


def size_for(job, terminal_temp, flags):
    """Smallest conductor and the overcurrent device for the load. Returns a dict of the steps."""
    material = material_of(job)
    wiring = str(job.get("wiring", "raceway")).lower()
    if wiring not in ("raceway", "nm"):
        raise InputError("wiring must be raceway or nm")
    if job.get("continuous_amps") is not None or job.get("noncontinuous_amps") is not None:
        cont = num(job.get("continuous_amps", 0), "continuous_amps")
        noncont = num(job.get("noncontinuous_amps", 0), "noncontinuous_amps")
    else:
        load = num(job.get("load_amps"), "load_amps", positive=True)
        cont, noncont = (load, 0.0) if job.get("continuous", False) else (0.0, load)
    load = cont + noncont
    if load <= 0:
        raise InputError("load must be greater than zero")
    sizing_amps = 1.25 * cont + noncont
    insulation = insulation_temp_of(job, flags)
    if wiring == "nm":
        insulation, terminal_temp = 90, 60
    ambient = num(job.get("ambient_c", 30), "ambient_c")
    ccc = int(job.get("current_carrying_conductors", 3))
    f_amb = ambient_factor(ambient, insulation)
    if f_amb is None:
        raise InputError(f"{insulation} C insulation cannot be used at {ambient:g} C ambient")
    f_bun = bundling_factor(ccc)
    column = TEMP_COLUMN[min(terminal_temp, insulation)]

    if job.get("breaker_a") is not None:
        ocpd = num(job["breaker_a"], "breaker_a", positive=True)
        if ocpd < sizing_amps - 1e-9:
            flags.append(f"The {ocpd:g} A device given is smaller than the {sizing_amps:.1f} A the load requires "
                         "(125% of continuous plus noncontinuous load, 210.20(A)).")
    else:
        ocpd = next_standard(sizing_amps)
        if ocpd is None:
            raise InputError("load is beyond the 600 A range of this calculator")

    table = AMPACITY[material]
    rejected = None
    for size in SIZES:
        if size not in table:
            continue
        terminal_ampacity = table[size][column]
        corrected = table[size][TEMP_COLUMN[insulation]] * f_amb * f_bun
        usable = min(corrected, terminal_ampacity)
        if terminal_ampacity < sizing_amps - 1e-9:
            rejected = {"size": size, "why": f"{terminal_ampacity:g} A at the {min(terminal_temp, insulation)} C "
                                             f"termination column, under the {sizing_amps:.1f} A sizing current"}
            continue
        if corrected < load - 1e-9:
            rejected = {"size": size, "why": f"{corrected:.1f} A after temperature and bundling corrections, "
                                             f"under the {load:g} A load"}
            continue
        cap = SMALL_CONDUCTOR_MAX[material].get(size)
        if cap is not None and ocpd > cap:
            rejected = {"size": size, "why": f"limited to a {cap} A device (240.4(D)), and this circuit "
                                             f"needs {ocpd:g} A"}
            continue
        allowed = usable if usable in STANDARD_OCPD else (next_standard(usable) or usable)
        if ocpd > 800 or ocpd > allowed + 1e-9:
            rejected = {"size": size, "why": f"its {usable:.1f} A ampacity cannot be protected by a "
                                             f"{ocpd:g} A device (240.4)"}
            continue
        return {"rejected": rejected, "material": material, "wiring": wiring, "size": size, "ocpd": ocpd, "load": load,
                "continuous": cont, "noncontinuous": noncont, "sizing_amps": sizing_amps,
                "terminal_temp": min(terminal_temp, insulation), "insulation": insulation,
                "terminal_ampacity": terminal_ampacity, "table_ampacity": table[size][TEMP_COLUMN[insulation]],
                "ambient": ambient, "ambient_factor": f_amb, "ccc": ccc, "bundling_factor": f_bun,
                "corrected": corrected, "usable": usable, "small_cap": cap}
    raise InputError("no single conductor up to 600 kcmil carries this load under these conditions; "
                     "parallel conductors are outside this calculator")


MOTOR_WORDS = ("motor", "compressor", "condenser", "heat pump", "air condition", "a/c", "mini split",
               "minisplit", "pump", "welder", "saw", "hvac", "furnace blower", "air handler")


# Conductor temperature rating by insulation type. Dry and wet ratings differ for some types; the wet
# rating is used for the ones commonly pulled in outdoor or underground raceways.
INSULATION_TEMP = {"thhn": 90, "thwn-2": 90, "thhn/thwn-2": 90, "xhhw-2": 90, "rhw-2": 90, "use-2": 90,
                   "thwn": 75, "thw": 75, "xhhw": 75, "rhw": 75, "tw": 60, "uf": 60}


def insulation_temp_of(job, flags):
    """Temperature rating of the wire itself. The rating of the lugs belongs in terminal_temp."""
    name = job.get("insulation")
    if name is not None:
        key = str(name).lower().replace(" ", "")
        if key not in INSULATION_TEMP:
            raise InputError(f"insulation must be one of {sorted(INSULATION_TEMP)}, or give insulation_temp")
        return INSULATION_TEMP[key]
    temp = int(job.get("insulation_temp", 90))
    if temp not in TEMP_COLUMN:
        raise InputError("insulation_temp must be 60, 75 or 90")
    if temp < 90 and str(job.get("wiring", "raceway")).lower() != "nm":
        flags.append(f"The wire was entered as {temp} C insulation. THHN, THWN-2 and XHHW-2 are 90 C, and their "
                     "corrections start from the 90 C column. If the 75 C figure is the rating of the lugs, it "
                     "belongs in terminal_temp and the wire should be entered by its insulation type.")
    return temp


def looks_like_motor_load(job):
    text = (str(job.get("job", "")) + " " + str(job.get("load_description", ""))).lower()
    return any(w in text for w in MOTOR_WORDS)


def attach_conduit(job, result, size, ground, voltage, phase):
    """Size the raceway for the conductors this job produced, when the job asks for it."""
    spec = job.get("conduit")
    if not spec:
        return
    if not isinstance(spec, dict):
        spec = {"raceway": str(spec)}
    insulation = spec.get("insulation", "thhn")
    count = 3 if phase == 3 else 2
    if spec.get("neutral") and (phase == 3 or voltage > 150):
        count += 1
    conductors = [{"size": size, "insulation": insulation, "count": count}]
    if ground and not spec.get("no_ground"):
        conductors.append({"size": ground, "insulation": insulation, "count": 1})
    conductors.extend(spec.get("extra") or [])
    result["conduit"] = calc_conduit({"calc": "conduit_fill", "job": "", "raceway": spec.get("raceway", "emt"),
                                      "trade_size": spec.get("trade_size"), "conductors": conductors})
    # The script chose and counted these conductors itself, so only the checks that still apply are kept.
    many = result["conduit"]["conductor_count"] > 4
    result["conduit"]["flags"] = [f for f in result["conduit"]["flags"]
                                  if f.startswith("Fill limits assume") or f.startswith("These conductors do not fit")
                                  or (many and f.startswith("Fill is separate"))]
    result["conduit"]["described"] = (f"{count} x {label(size)} circuit conductors"
                                      + (f" and 1 x {label(ground)} ground" if ground and not spec.get("no_ground") else ""))


def existing_verdict(job, material, minimum, final):
    """Compare a conductor already installed with the code minimum and the voltage-drop size."""
    if job.get("existing_size") is None:
        return None
    size = norm_size(job["existing_size"], "existing_size")
    if size not in AMPACITY[material]:
        raise InputError(f"existing_size: no ampacity value for {label(size)}")
    if SIZES.index(size) < SIZES.index(minimum):
        verdict = f"too small. The minimum is {label(minimum)}."
    elif SIZES.index(size) < SIZES.index(final):
        verdict = (f"meets the code minimum, but {label(final)} is needed to stay within the voltage-drop target.")
    else:
        verdict = "adequate under the conditions entered."
    return {"size": size, "verdict": verdict}


def target_warning(max_pct, flags):
    if max_pct > 3 + 1e-9:
        flags.append(f"The voltage-drop target entered is {max_pct:g}%. The usual recommendation is 3% for a feeder "
                     "or a branch circuit taken by itself, and 5% only for the two together. If this run is the "
                     "whole path from the service to the load, 5% is the figure; if it is one part, use 3%.")


def calc_wire(job):
    flags = []
    voltage, phase = system_of(job)
    terminal = int(job.get("terminal_temp", 75))
    if terminal not in (60, 75, 90):
        raise InputError("terminal_temp must be 60, 75 or 90")
    if terminal == 90:
        flags.append("90 C terminations are rare; most breakers, panels and devices are marked 60/75 C. "
                     "Confirm the marking on both ends.")
    s = size_for(job, terminal, flags)
    material = s["material"]
    result = {"calc": "wire", "job": job.get("job", ""), "voltage": voltage, "phase": phase, "steps": s,
              "flags": flags}
    egc = egc_size(s["ocpd"], material, s["size"])
    result["egc"] = egc

    length = job.get("length_ft")
    max_pct = num(job.get("max_voltage_drop_pct", 3), "max_voltage_drop_pct", positive=True)
    conduit = conduit_material_of(job)
    final = s["size"]
    if length is not None:
        length = num(length, "length_ft", positive=True)
        drops = []
        start = SIZES.index(s["size"])
        for size in SIZES[start:]:
            if size not in RESISTANCE[material]:
                continue
            v = vd_volts(material, size, s["load"], length, phase, conduit)
            pct = 100.0 * v / voltage
            drops.append({"size": size, "volts": round(v, 2), "pct": round(pct, 2), "ok": pct <= max_pct})
            if pct <= max_pct:
                final = size
                break
        else:
            flags.append(f"No conductor up to 600 kcmil keeps voltage drop within {max_pct:g}% at this length.")
        result["voltage_drop"] = {"length_ft": length, "max_pct": max_pct, "tried": drops}
        if final != s["size"] and egc:
            ratio = CIRCULAR_MILS[final] / CIRCULAR_MILS[s["size"]]
            need = CIRCULAR_MILS[egc] * ratio
            bigger = next((z for z in SIZES if CIRCULAR_MILS[z] >= need - 1e-6), None)
            if bigger and SIZES.index(bigger) > SIZES.index(final):
                bigger = final
            result["egc_upsized"] = bigger
        if SIZES.index(final) >= SIZES.index("1/0"):
            flags.append(f"Voltage drop for 1/0 AWG and larger uses the effective impedance at 0.85 power factor "
                         f"for conductors in {conduit} conduit (Chapter 9, Table 9). A load with a much lower "
                         "power factor will drop more.")
    else:
        flags.append("No length given, so voltage drop was not checked.")
    result["final_size"] = final
    result["existing"] = existing_verdict(job, material, s["size"], final)
    if length is not None:
        target_warning(max_pct, flags)

    if s["wiring"] == "nm":
        flags.append("NM cable: ampacity is limited to the 60 C column, with corrections taken from the 90 C "
                     "value (334.80).")
    elif s["terminal_temp"] == 75 and (s["ocpd"] <= 100):
        alt_flags = []
        try:
            alt = size_for(job, 60, alt_flags)
            if alt["size"] != s["size"]:
                result["if_60c_terminals"] = alt["size"]
                flags.append(f"Sized for 75 C terminations. If either end is marked 60 C only, or is unmarked on "
                             f"a circuit of 100 A or less, the minimum is {label(alt['size'])} (110.14(C)).")
        except InputError:
            pass
    if s["ccc"] > 3:
        flags.append("Count only current-carrying conductors for the bundling factor: a neutral that carries "
                     "only unbalanced current and equipment grounds do not count (310.15(E), 310.15(F)).")
    if looks_like_motor_load(job):
        flags.append("This worksheet is for general loads. Air conditioners, heat pumps and other equipment marked "
                     "with a minimum circuit ampacity are sized from the nameplate (the nameplate calculation). "
                     "Motors without that marking and welders follow Articles 430 and 630 and are not covered.")
    attach_conduit(job, result, final, result.get("egc_upsized") or egc, voltage, phase)
    return result


def calc_nameplate(job):
    """Air-conditioning, heat-pump and similar equipment marked with a minimum circuit ampacity (MCA)
    and a maximum overcurrent device (MOCP). The nameplate already includes the 125% allowance for the
    largest motor, so the conductor is sized to the MCA as marked and the device may be as large as the
    MOCP even when that exceeds the conductor's ampacity (440.4(B), 440.22, 440.35, 240.4(G))."""
    flags = []
    voltage, phase = system_of(job)
    material = material_of(job)
    mca = num(job.get("mca"), "mca (minimum circuit ampacity from the nameplate)", positive=True)
    mocp = num(job.get("mocp"), "mocp (maximum overcurrent device from the nameplate)", positive=True)
    if mocp < mca:
        raise InputError("mocp is smaller than mca; check the nameplate values")
    wiring = str(job.get("wiring", "raceway")).lower()
    if wiring not in ("raceway", "nm"):
        raise InputError("wiring must be raceway or nm")
    terminal = int(job.get("terminal_temp", 75))
    if terminal not in TEMP_COLUMN:
        raise InputError("terminal_temp must be 60, 75 or 90")
    insulation = insulation_temp_of(job, flags)
    if wiring == "nm":
        insulation, terminal = 90, 60
    ambient = num(job.get("ambient_c", 30), "ambient_c")
    ccc = int(job.get("current_carrying_conductors", 3))
    f_amb = ambient_factor(ambient, insulation)
    if f_amb is None:
        raise InputError(f"{insulation} C insulation cannot be used at {ambient:g} C ambient")
    f_bun = bundling_factor(ccc)
    column = TEMP_COLUMN[min(terminal, insulation)]
    table = AMPACITY[material]
    chosen = None
    rejected = None
    for size in SIZES:
        if size not in table:
            continue
        corrected = table[size][TEMP_COLUMN[insulation]] * f_amb * f_bun
        if table[size][column] >= mca - 1e-9 and corrected >= mca - 1e-9:
            chosen = {"size": size, "terminal_ampacity": table[size][column], "rejected": rejected,
                      "table_ampacity": table[size][TEMP_COLUMN[insulation]], "corrected": corrected}
            break
        if table[size][column] < mca - 1e-9:
            rejected = {"size": size, "why": f"{table[size][column]:g} A at the {min(terminal, insulation)} C "
                                             f"termination column, under the {mca:g} A minimum circuit ampacity"}
        else:
            rejected = {"size": size, "why": f"{corrected:.1f} A after temperature and bundling corrections, "
                                             f"under the {mca:g} A minimum circuit ampacity"}
    if chosen is None:
        raise InputError("no single conductor up to 600 kcmil carries this minimum circuit ampacity")
    ocpd = max((x for x in STANDARD_OCPD if x <= mocp + 1e-9), default=None)
    if ocpd is None or ocpd < mca:
        ocpd = mocp
        flags.append("No standard device rating falls between the minimum circuit ampacity and the maximum "
                     "overcurrent device; use the rating marked on the nameplate.")
    egc = egc_size(ocpd, material, chosen["size"])
    steps = dict(chosen, material=material, wiring=wiring, mca=mca, mocp=mocp, ocpd=ocpd,
                 terminal_temp=min(terminal, insulation), insulation=insulation, ambient=ambient,
                 ambient_factor=f_amb, ccc=ccc, bundling_factor=f_bun)
    result = {"calc": "nameplate", "job": job.get("job", ""), "voltage": voltage, "phase": phase,
              "steps": steps, "egc": egc, "final_size": chosen["size"], "flags": flags}
    length = job.get("length_ft")
    if length is not None:
        length = num(length, "length_ft", positive=True)
        max_pct = num(job.get("max_voltage_drop_pct", 3), "max_voltage_drop_pct", positive=True)
        conduit = conduit_material_of(job)
        drops = []
        for size in SIZES[SIZES.index(chosen["size"]):]:
            if size not in RESISTANCE[material]:
                continue
            v = vd_volts(material, size, mca, length, phase, conduit)
            pct = 100.0 * v / voltage
            drops.append({"size": size, "volts": round(v, 2), "pct": round(pct, 2), "ok": pct <= max_pct})
            if pct <= max_pct:
                result["final_size"] = size
                break
        result["voltage_drop"] = {"length_ft": length, "max_pct": max_pct, "tried": drops}
        target_warning(max_pct, flags)
        flags.append("Voltage drop is figured at the minimum circuit ampacity, which is above the running "
                     "current, so the real drop while running is lower. Starting current is far higher and "
                     "is the usual cause of lights dimming on a long run.")
    else:
        flags.append("No length given, so voltage drop was not checked.")
    result["existing"] = existing_verdict(job, material, chosen["size"], result["final_size"])
    if job.get("breaker_a") is not None:
        have = num(job["breaker_a"], "breaker_a", positive=True)
        if have > mocp + 1e-9:
            note = f"is over the {mocp:g} A nameplate maximum and must be replaced with a smaller one."
        elif have < mca - 1e-9:
            note = (f"is under the {mca:g} A minimum circuit ampacity and can be expected to trip; "
                    f"use a rating up to {ocpd:g} A.")
        else:
            note = (f"is within the nameplate range and can stay if the unit starts on it. "
                    f"A rating up to {ocpd:g} A is allowed on the same conductors if it trips on starting.")
        result["existing_breaker"] = {"rating": have, "note": note}
    usable = min(chosen["terminal_ampacity"], chosen["corrected"])
    if usable - mca < 0.05 * mca:
        flags.append(f"Thin margin: {label(chosen['size'])} is good for {usable:.1f} A against a {mca:g} A minimum "
                     "circuit ampacity. Any correction not entered here (a hot attic or roof, more conductors in "
                     "the raceway) would push it to the next size.")
    if wiring != "nm" and min(terminal, insulation) == 75:
        low = next((z for z in SIZES if z in table and table[z][0] >= mca - 1e-9), None)
        if low and low != chosen["size"]:
            flags.append(f"Sized for 75 C terminations. If the breaker, the disconnect or the unit's lugs are marked "
                         f"60 C only, or are unmarked, the minimum is {label(low)} (110.14(C)).")
            result["if_60c_terminals"] = low
    if SMALL_CONDUCTOR_MAX[material].get(chosen["size"]) and ocpd > SMALL_CONDUCTOR_MAX[material][chosen["size"]]:
        flags.append(f"The {ocpd:g} A device is larger than the usual limit for {label(chosen['size'])}. That is "
                     "permitted for this equipment because its internal overload protection protects the "
                     "conductors (240.4(G), 440.22). Expect to show the inspector the nameplate.")
    if wiring == "nm":
        flags.append("NM cable: ampacity is limited to the 60 C column (334.80). The whip to an outdoor unit "
                     "cannot be NM cable; it is a wet location.")
    flags.append("Use the values on the unit's own nameplate, not a catalog sheet for a similar model. If the "
                 "nameplate says fuses only or HACR breaker, the device type must match (110.3(B)).")
    flags.append("A disconnect within sight of the unit is required and is not sized here (440.14).")
    attach_conduit(job, result, result["final_size"], egc, voltage, phase)
    return result


def calc_voltage_drop(job):
    voltage, phase = system_of(job)
    material = material_of(job)
    size = norm_size(job.get("size"))
    if size not in RESISTANCE[material]:
        raise InputError(f"no resistance value for {label(size)} {material}")
    amps = num(job.get("load_amps"), "load_amps", positive=True)
    length = num(job.get("length_ft"), "length_ft", positive=True)
    max_pct = num(job.get("max_voltage_drop_pct", 3), "max_voltage_drop_pct", positive=True)
    conduit = conduit_material_of(job)
    ohms = ohms_per_kft(material, size, conduit)
    v = vd_volts(material, size, amps, length, phase, conduit)
    pct = 100.0 * v / voltage
    k = 2.0 if phase == 1 else math.sqrt(3)
    max_len = max_pct / 100.0 * voltage * 1000.0 / (k * ohms * amps)
    fix = None
    if pct > max_pct:
        for z in SIZES[SIZES.index(size):]:
            if z in RESISTANCE[material] and \
                    100.0 * vd_volts(material, z, amps, length, phase, conduit) / voltage <= max_pct:
                fix = z
                break
    flags = []
    source = "Chapter 9, Table 8"
    if ohms > RESISTANCE[material][size]:
        source = "Chapter 9, Table 9"
        flags.append(f"Uses the effective impedance at 0.85 power factor for conductors in {conduit} conduit, "
                     "because reactance matters at this size. A load with a much lower power factor will drop more.")
    flags.append("The 3% branch / 5% total figures are recommendations in informational notes, not requirements, "
                 "except where a specific rule or local amendment makes them mandatory.")
    target_warning(max_pct, flags)
    options = []
    if pct > max_pct:
        half = 100.0 * (v / 2.0) / voltage
        options.append(f"A second identical run in parallel halves the drop, to about {half:.1f}%. Parallel runs "
                       "must be 1/0 AWG or larger and identical in length, material and size (310.10(G)).")
        if conduit == "steel" and ohms > RESISTANCE[material][size]:
            pvc = 100.0 * vd_volts(material, size, amps, length, phase, "pvc") / voltage
            options.append(f"The same conductor in nonmetallic conduit would drop about {pvc:.1f}%, because steel "
                           "conduit adds reactance.")
        fit = max_pct / 100.0 * voltage * 1000.0 / (k * ohms * length)
        options.append(f"On the existing conductor, {max_pct:g}% is reached at about {fit:.0f} A; moving load off "
                       "this run or supplying it at a higher voltage are the other ways to get there.")
    return {"calc": "voltage_drop", "options": options, "job": job.get("job", ""), "voltage": voltage, "phase": phase,
            "material": material, "size": size, "load_amps": amps, "length_ft": length,
            "resistance": ohms, "resistance_source": source, "volts": round(v, 2), "pct": round(pct, 2),
            "max_pct": max_pct, "ok": pct <= max_pct, "max_length_ft": round(max_len),
            "size_that_meets": fix, "flags": flags}


def calc_conduit(job):
    raceway = str(job.get("raceway", "emt")).lower().replace(" ", "").replace("schedule", "").replace("sch", "")
    if raceway not in RACEWAY_AREA:
        raise InputError(f"raceway must be one of {list(RACEWAY_AREA)}")
    rows = []
    total = 0.0
    count = 0
    for i, c in enumerate(job.get("conductors") or []):
        ins = INSULATION_ALIAS.get(str(c.get("insulation", "thhn")).lower())
        if ins is None:
            raise InputError(f"conductors[{i}]: insulation must be one of {sorted(INSULATION_ALIAS)}")
        size = norm_size(c.get("size"), f"conductors[{i}]")
        if size not in CONDUCTOR_AREA[ins]:
            raise InputError(f"conductors[{i}]: no area value for {label(size)} {ins.upper()}")
        n = int(c.get("count", 1))
        if n < 1:
            raise InputError(f"conductors[{i}]: count must be at least 1")
        area = CONDUCTOR_AREA[ins][size]
        rows.append({"size": size, "insulation": ins.upper(), "count": n, "each": area, "area": area * n})
        total += area * n
        count += n
    if count == 0:
        raise InputError("give at least one conductor")
    nipple = bool(job.get("nipple", False))
    if nipple:
        limit, why = 0.60, "nipple of 24 in. or less, 60% (Chapter 9, Table 1, Note 4)"
    elif count == 1:
        limit, why = 0.53, "one conductor, 53% (Chapter 9, Table 1)"
    elif count == 2:
        limit, why = 0.31, "two conductors, 31% (Chapter 9, Table 1)"
    else:
        limit, why = 0.40, "more than two conductors, 40% (Chapter 9, Table 1)"
    areas = RACEWAY_AREA[raceway]
    options = [{"trade_size": t, "total_area": a, "allowed": round(a * limit, 4),
                "fill_pct": round(100 * total / a, 1), "ok": total <= a * limit + 1e-9}
               for t, a in zip(TRADE_SIZES, areas)]
    smallest = next((o for o in options if o["ok"]), None)
    if len(rows) == 1:
        # All conductors alike: the most that fit at 40%, rounding up at 0.8 or more (Chapter 9, Note 7).
        each = rows[0]["each"]
        for o in options:
            exact = o["total_area"] * 0.40 / each
            most = int(exact) + (1 if exact - int(exact) >= 0.8 else 0)
            if most == 2 and 2 * each > o["total_area"] * 0.31 + 1e-9:
                most = 1
            if most <= 1:
                most = 1 if each <= o["total_area"] * 0.53 + 1e-9 else 0
            o["max_alike"] = most
    flags = []
    given = job.get("trade_size")
    check = None
    if given:
        g = str(given).replace('"', "").strip()
        if g not in TRADE_SIZES:
            raise InputError(f"trade_size must be one of {TRADE_SIZES}")
        check = options[TRADE_SIZES.index(g)]
    if smallest is None:
        flags.append("These conductors do not fit in any size up to trade size 4 of this raceway.")
    flags.append("Count every conductor in the raceway, including equipment grounds. A bare ground takes less "
                 "area than an insulated one; entering it as insulated is conservative.")
    flags.append("Fill is separate from ampacity: more than three current-carrying conductors in one raceway "
                 "also reduces ampacity (310.15(C)(1)).")
    if not nipple and count > 2:
        flags.append("Fill limits assume pulls of ordinary length and bends. Long runs or many bends may call "
                     "for a larger raceway even when the fill passes.")
    derating = None
    if job.get("breaker_a") is not None:
        breaker = num(job["breaker_a"], "breaker_a", positive=True)
        material = material_of(job)
        ambient = num(job.get("ambient_c", 30), "ambient_c")
        f_amb = ambient_factor(ambient, 90)
        derating = {"breaker": breaker, "ambient": ambient, "rows": []}
        seen = []
        for row in rows:
            if row["size"] in seen or row["size"] not in AMPACITY[material]:
                continue
            seen.append(row["size"])
            base_amps = AMPACITY[material][row["size"]][2]
            cap = SMALL_CONDUCTOR_MAX[material].get(row["size"])
            bands = []
            most = 0
            lower = 1
            for upper, factor in BUNDLING[:6]:
                amps = base_amps * (f_amb or 0) * factor
                ok = amps >= breaker - 1e-9 and (cap is None or breaker <= cap)
                bands.append({"range": f"{lower} to {upper}", "ampacity": round(amps, 1), "ok": ok})
                if ok:
                    most = upper
                lower = upper + 1
            derating["rows"].append({"size": row["size"], "base": base_amps, "bands": bands, "most": most})
        flags.append("The current-carrying count leaves out equipment grounds and a neutral that carries only "
                     "the unbalanced current of a multiwire circuit (310.15(E), 310.15(F)). The ampacity here is "
                     "from the 90 C column; terminations may limit the circuit further.")
    return {"calc": "conduit_fill", "job": job.get("job", ""), "raceway": raceway, "rows": rows, "derating": derating,
            "conductor_count": count, "total_area": round(total, 4), "limit": limit, "limit_reason": why,
            "smallest": smallest, "check": check, "options": options, "flags": flags}


def calc_box(job):
    edition = str(job.get("edition", "2023"))
    if edition not in ("2014", "2017", "2020", "2023", "2026"):
        raise InputError("edition must be 2014, 2017, 2020, 2023 or 2026")
    items = []
    total = 0.0
    largest = None

    def allowance(size, what):
        s = norm_size(size, what)
        if s not in BOX_ALLOWANCE:
            raise InputError(f"{what}: box fill covers 18 through 6 AWG; larger conductors are sized by "
                             "314.28, not by volume allowance")
        return s, BOX_ALLOWANCE[s]

    def bigger(a, b):
        order = list(BOX_ALLOWANCE)
        if a is None:
            return b
        return a if order.index(a) >= order.index(b) else b

    for i, c in enumerate(job.get("conductors") or []):
        s, v = allowance(c.get("size"), f"conductors[{i}]")
        n = int(c.get("count", 1))
        items.append({"item": f"{n} x {label(s)} conductor", "section": "314.16(B)(1)", "allowances": n,
                      "each": v, "volume": n * v})
        total += n * v
        largest = bigger(largest, s)
    if largest is None:
        raise InputError("give at least one conductor")
    if job.get("internal_clamps"):
        v = BOX_ALLOWANCE[largest]
        items.append({"item": "Internal cable clamps (one allowance, largest conductor)", "section": "314.16(B)(2)",
                      "allowances": 1, "each": v, "volume": v})
        total += v
    fittings = int(job.get("support_fittings", 0) or 0)
    if fittings:
        v = BOX_ALLOWANCE[largest]
        items.append({"item": f"{fittings} x fixture stud or hickey type", "section": "314.16(B)(3)",
                      "allowances": fittings, "each": v, "volume": fittings * v})
        total += fittings * v
    for i, d in enumerate(job.get("devices") or []):
        s, v = allowance(d.get("largest_size", largest), f"devices[{i}]")
        n = int(d.get("count", 1))
        gangs = int(d.get("gangs_wide", 1))
        items.append({"item": f"{n} x device yoke, {label(s)} connected"
                              + (f", {gangs} gangs wide" if gangs > 1 else ""),
                      "section": "314.16(B)(4)", "allowances": 2 * n * gangs, "each": v,
                      "volume": 2 * n * gangs * v})
        total += 2 * n * gangs * v
    g = job.get("grounds") or {}
    gcount = int(g.get("count", 0) or 0)
    if gcount:
        s, v = allowance(g.get("size", largest), "grounds")
        if int(edition) >= 2020 and gcount > 4:
            a = 1 + 0.25 * (gcount - 4)
            note = f"{gcount} x {label(s)} equipment ground (first four count as one, each further one a quarter)"
        else:
            a = 1
            note = f"{gcount} x {label(s)} equipment ground (count as one)"
        items.append({"item": note, "section": "314.16(B)(5)", "allowances": a, "each": v, "volume": a * v})
        total += a * v
    total = round(total, 3)
    fits = [{"box": name, "volume": vol}
            for name, vol in sorted(STANDARD_BOXES, key=lambda b: b[1]) if vol >= total - 1e-9]
    check = None
    if job.get("box_volume_in3") is not None:
        vol = num(job["box_volume_in3"], "box_volume_in3", positive=True)
        check = {"volume": vol, "ok": vol >= total - 1e-9, "spare": round(vol - total, 2)}
    flags = [
        "Count each conductor that enters the box and is spliced or terminated as one, and each conductor that "
        "passes through unbroken as one. Pigtails and jumpers that start and end inside the box do not count.",
        "Plaster rings, extension rings and domed covers marked with a volume add to the box volume.",
        "Nonmetallic boxes are marked with their volume; use the marking, not the table of metal boxes.",
    ]
    return {"calc": "box_fill", "job": job.get("job", ""), "edition": edition, "items": items,
            "required_volume": total, "smallest_standard": fits[:3], "check": check, "flags": flags}


CALCS = {"wire": calc_wire, "nameplate": calc_nameplate, "voltage_drop": calc_voltage_drop, "conduit_fill": calc_conduit, "box_fill": calc_box}


def run_one(job):
    calc = str(job.get("calc", "")).lower()
    if calc not in CALCS:
        raise InputError(f"calc must be one of {list(CALCS)}")
    return CALCS[calc](job)


def run(job):
    """One calculation, or several under {"jobs": [...]}. A chained conduit result becomes its own part."""
    jobs = job.get("jobs") if isinstance(job, dict) else None
    if jobs is None:
        jobs = [job]
    elif not jobs:
        raise InputError("jobs is empty")
    parts = []
    for j in jobs:
        r = run_one(j)
        conduit = r.pop("conduit", None)
        parts.append(r)
        if conduit:
            conduit["job"] = "Raceway for " + conduit.pop("described")
            parts.append(conduit)
    if len(parts) == 1:
        parts[0]["notice"] = NOTICE
        return parts[0]
    return {"calc": "multi", "job": job.get("job", "") or parts[0].get("job", ""), "parts": parts, "notice": NOTICE}


def md_wire(r, out):
    s = r["steps"]
    metal = "copper" if s["material"] == "cu" else "aluminum"
    final = r["final_size"]
    out.append(f"**Result: {label(final)} {metal}, {s['ocpd']:g} A overcurrent device"
               + (f", {label(r.get('egc_upsized') or r['egc'])} {metal} equipment ground" if r["egc"] else "")
               + "**")
    out.append("")
    out.append(f"System: {r['voltage']:g} V, {'single' if r['phase'] == 1 else 'three'}-phase  |  "
               f"Wiring: {'NM cable' if s['wiring'] == 'nm' else 'conductors in raceway or cable'}")
    out.append("")
    out.append("| Step | Section | Value |")
    out.append("|---|---|---:|")
    out.append(f"| Load: {s['continuous']:g} A continuous + {s['noncontinuous']:g} A noncontinuous | | {s['load']:g} A |")
    out.append(f"| Sizing current: 125% of continuous + noncontinuous | 210.19(A), 210.20(A) | {s['sizing_amps']:.1f} A |")
    out.append(f"| Overcurrent device, next standard rating | 240.6(A) | {s['ocpd']:g} A |")
    out.append(f"| {label(s['size'])} at the {s['terminal_temp']} C termination column | 110.14(C), Table 310.16 | {s['terminal_ampacity']:g} A |")
    out.append(f"| {label(s['size'])} at {s['insulation']} C before corrections | Table 310.16 | {s['table_ampacity']:g} A |")
    out.append(f"| Ambient {s['ambient']:g} C correction | Table 310.15(B)(1) | x {s['ambient_factor']:.2f} |")
    out.append(f"| {s['ccc']} current-carrying conductors | Table 310.15(C)(1) | x {s['bundling_factor']:.2f} |")
    out.append(f"| Corrected ampacity (must cover the {s['load']:g} A load) | 310.15 | {s['corrected']:.1f} A |")
    out.append(f"| Ampacity the device must protect (lower of corrected and termination) | 240.4 | {s['usable']:.1f} A |")
    if s["small_cap"]:
        out.append(f"| Small-conductor limit for {label(s['size'])} | 240.4(D) | {s['small_cap']} A max |")
    if r["egc"]:
        out.append(f"| Equipment ground for a {s['ocpd']:g} A device | Table 250.122 | {label(r['egc'])} |")
    out.append("")
    out.append(f"Minimum by ampacity: **{label(s['size'])}**.")
    if s.get("rejected"):
        out.append(f"The next size down, {label(s['rejected']['size'])}, does not work: {s['rejected']['why']}.")
    if r.get("existing"):
        out.append("")
        out.append(f"**Existing {label(r['existing']['size'])}: {r['existing']['verdict']}**")
    vd = r.get("voltage_drop")
    if vd:
        out.append("")
        out.append(f"### Voltage drop at {vd['length_ft']:g} ft one way, {s['load']:g} A, target {vd['max_pct']:g}%")
        out.append("")
        out.append("| Conductor | Drop (V) | Drop (%) | Within target |")
        out.append("|---|---:|---:|---|")
        for d in vd["tried"]:
            out.append(f"| {label(d['size'])} | {d['volts']:.2f} | {d['pct']:.2f} | {'yes' if d['ok'] else '**no**'} |")
        out.append("")
        if final != s["size"]:
            out.append(f"Upsize to **{label(final)}** to stay within {vd['max_pct']:g}%. The {s['ocpd']:g} A device "
                       "does not change.")
            if r.get("egc_upsized"):
                out.append(f"Equipment ground increases in proportion to **{label(r['egc_upsized'])}** (250.122(B)).")
            out.append("Check that the larger conductor fits the device and equipment terminals.")
        else:
            out.append(f"{label(final)} is within the target; no upsizing needed.")
    out.append("")


def md_nameplate(r, out):
    s = r["steps"]
    metal = "copper" if s["material"] == "cu" else "aluminum"
    final = r["final_size"]
    out.append(f"**Result: {label(final)} {metal}, {s['ocpd']:g} A maximum overcurrent device"
               + (f", {label(r['egc'])} {metal} equipment ground" if r["egc"] else "") + "**")
    out.append("")
    out.append(f"System: {r['voltage']:g} V, {'single' if r['phase'] == 1 else 'three'}-phase  |  "
               f"Wiring: {'NM cable' if s['wiring'] == 'nm' else 'conductors in raceway or cable'}")
    out.append("")
    out.append("| Step | Section | Value |")
    out.append("|---|---|---:|")
    out.append(f"| Minimum circuit ampacity from the nameplate | 440.4(B), 440.35 | {s['mca']:g} A |")
    out.append(f"| Maximum overcurrent device from the nameplate | 440.4(B), 440.22 | {s['mocp']:g} A |")
    out.append(f"| {label(s['size'])} at the {s['terminal_temp']} C termination column | 110.14(C), Table 310.16 | {s['terminal_ampacity']:g} A |")
    out.append(f"| {label(s['size'])} at {s['insulation']} C before corrections | Table 310.16 | {s['table_ampacity']:g} A |")
    out.append(f"| Ambient {s['ambient']:g} C correction | Table 310.15(B)(1) | x {s['ambient_factor']:.2f} |")
    out.append(f"| {s['ccc']} current-carrying conductors | Table 310.15(C)(1) | x {s['bundling_factor']:.2f} |")
    out.append(f"| Corrected ampacity (must cover the {s['mca']:g} A minimum circuit ampacity) | 310.15 | {s['corrected']:.1f} A |")
    out.append(f"| Ampacity that governs (lower of termination and corrected) | 110.14(C) | "
               f"{min(s['corrected'], s['terminal_ampacity']):.1f} A |")
    out.append(f"| Overcurrent device, largest standard rating not over the nameplate maximum | 240.6(A), 240.4(G) | {s['ocpd']:g} A |")
    if r["egc"]:
        out.append(f"| Equipment ground for a {s['ocpd']:g} A device, not larger than the circuit conductors "
                   f"| 250.122(A) | {label(r['egc'])} |")
    out.append("")
    out.append(f"Minimum by ampacity: **{label(s['size'])}**. The nameplate value already includes the 125% "
               "allowance, so nothing more is added. A smaller device than the maximum is allowed if the unit "
               "starts on it.")
    if s.get("rejected"):
        out.append(f"The next size down, {label(s['rejected']['size'])}, does not work: {s['rejected']['why']}.")
    if r.get("existing") or r.get("existing_breaker"):
        out.append("")
    if r.get("existing"):
        out.append(f"**Existing {label(r['existing']['size'])}: {r['existing']['verdict']}**")
    if r.get("existing") and r.get("existing_breaker"):
        out.append("")
    if r.get("existing_breaker"):
        out.append(f"**The existing {r['existing_breaker']['rating']:g} A breaker {r['existing_breaker']['note']}**")
    vd = r.get("voltage_drop")
    if vd:
        out.append("")
        out.append(f"### Voltage drop at {vd['length_ft']:g} ft one way, {s['mca']:g} A, target {vd['max_pct']:g}%")
        out.append("")
        out.append("| Conductor | Drop (V) | Drop (%) | Within target |")
        out.append("|---|---:|---:|---|")
        for d in vd["tried"]:
            out.append(f"| {label(d['size'])} | {d['volts']:.2f} | {d['pct']:.2f} | {'yes' if d['ok'] else '**no**'} |")
        out.append("")
        if final != s["size"]:
            out.append(f"Upsize to **{label(final)}** to stay within {vd['max_pct']:g}%.")
        else:
            out.append(f"{label(final)} is within the target; no upsizing needed.")
    out.append("")


def md_voltage_drop(r, out):
    metal = "copper" if r["material"] == "cu" else "aluminum"
    out.append(f"**Result: {r['volts']:.2f} V drop, {r['pct']:.2f}% of {r['voltage']:g} V. "
               f"{'Within' if r['ok'] else 'Over'} the {r['max_pct']:g}% target.**")
    out.append("")
    k = "2" if r["phase"] == 1 else "1.732"
    out.append(f"{label(r['size'])} {metal}, {r['load_amps']:g} A, {r['length_ft']:g} ft one way, "
               f"{'single' if r['phase'] == 1 else 'three'}-phase.")
    out.append("")
    out.append(f"Drop = {k} x {r['length_ft']:g} ft x {r['resistance']:g} ohm per 1,000 ft x {r['load_amps']:g} A "
               f"/ 1,000 = {r['volts']:.2f} V ({r['resistance_source']})")
    out.append("")
    out.append(f"Longest one-way run at this load within {r['max_pct']:g}%: about {r['max_length_ft']:,} ft.")
    if r["size_that_meets"]:
        out.append(f"Smallest conductor that meets the target at this length: **{label(r['size_that_meets'])}**.")
    out.append("")
    if r.get("options"):
        out.append("Other ways to get within the target:")
        out.append("")
        for o in r["options"]:
            out.append(f"- {o}")
        out.append("")


def md_conduit(r, out):
    name = RACEWAY_NAME[r["raceway"]]
    if r["check"]:
        c = r["check"]
        out.append(f"**Result: trade size {c['trade_size']} {name} is {c['fill_pct']:.1f}% full. "
                   f"{'Passes' if c['ok'] else 'Does not pass'} the {r['limit']:.0%} limit.**")
    elif r["smallest"]:
        m = r["smallest"]
        out.append(f"**Result: trade size {m['trade_size']} {name} minimum ({m['fill_pct']:.1f}% full).**")
    else:
        out.append(f"**Result: does not fit in {name} up to trade size 4.**")
    out.append("")
    out.append("| Conductors | Area each (sq in) | Area (sq in) |")
    out.append("|---|---:|---:|")
    for row in r["rows"]:
        out.append(f"| {row['count']} x {label(row['size'])} {row['insulation']} | {row['each']:.4f} | {row['area']:.4f} |")
    out.append(f"| **Total, {r['conductor_count']} conductors** | Chapter 9, Table 5 | **{r['total_area']:.4f}** |")
    out.append("")
    out.append(f"Fill limit: {r['limit_reason']}.")
    out.append("")
    pick = r["check"] or r["smallest"]
    if pick and pick.get("max_alike") and pick["max_alike"] > 2:
        row = r["rows"][0]
        out.append(f"Most {label(row['size'])} {row['insulation']} conductors allowed in trade size "
                   f"{pick['trade_size']} {name}: **{pick['max_alike']}** (Chapter 9, Table 1 and Note 7).")
        out.append("")
    out.append(f"| {name} trade size | Internal area (sq in) | Allowed (sq in) | Fill | Passes |")
    out.append("|---|---:|---:|---:|---|")
    for o in r["options"]:
        near = r["smallest"] and abs(TRADE_SIZES.index(o["trade_size"]) - TRADE_SIZES.index(r["smallest"]["trade_size"])) <= 1
        picked = r["check"] and o["trade_size"] == r["check"]["trade_size"]
        if near or picked:
            out.append(f"| {o['trade_size']} | {o['total_area']:.3f} | {o['allowed']:.4f} | {o['fill_pct']:.1f}% | "
                       f"{'yes' if o['ok'] else '**no**'} |")
    out.append("")
    if r["check"] and r["smallest"] and not r["check"]["ok"]:
        out.append(f"Smallest size that passes: **trade size {r['smallest']['trade_size']}**.")
        out.append("")
    d = r.get("derating")
    if d:
        out.append(f"### Ampacity when conductors share the raceway, {d['breaker']:g} A circuits, "
                   f"{d['ambient']:g} C ambient")
        out.append("")
        out.append("| Conductor | Current-carrying conductors | Ampacity (A) | Holds the breaker |")
        out.append("|---|---|---:|---|")
        for row in d["rows"]:
            for b in row["bands"]:
                out.append(f"| {label(row['size'])} | {b['range']} | {b['ampacity']:.1f} | "
                           f"{'yes' if b['ok'] else '**no**'} |")
        out.append("")
        for row in d["rows"]:
            if row["most"]:
                out.append(f"{label(row['size'])} on {d['breaker']:g} A circuits: at most **{row['most']}** "
                           "current-carrying conductors in the raceway (Table 310.15(C)(1)).")
            else:
                out.append(f"{label(row['size'])} does not hold a {d['breaker']:g} A breaker under these conditions.")
        out.append("")


def md_box(r, out):
    if r["check"]:
        c = r["check"]
        out.append(f"**Result: {r['required_volume']:.2f} cu in required; the {c['volume']:g} cu in box "
                   f"{'is large enough' if c['ok'] else 'is too small'} ({c['spare']:+.2f} cu in).**")
    else:
        out.append(f"**Result: {r['required_volume']:.2f} cu in required.**")
    out.append("")
    out.append("| Item | Section | Allowances | Each (cu in) | Volume (cu in) |")
    out.append("|---|---|---:|---:|---:|")
    for i in r["items"]:
        out.append(f"| {i['item']} | {i['section']} | {i['allowances']:g} | {i['each']:.2f} | {i['volume']:.2f} |")
    out.append(f"| **Required volume** | Table 314.16(B)(1) | | | **{r['required_volume']:.2f}** |")
    out.append("")
    if r["smallest_standard"]:
        out.append("Smallest standard metal boxes that hold it (Table 314.16(A)):")
        out.append("")
        for b in r["smallest_standard"]:
            out.append(f"- {b['box']}: {b['volume']:g} cu in")
    else:
        out.append("No single standard metal box in the table holds this; use a larger or ganged box, or an "
                   "extension ring, and use its marked volume.")
    out.append("")


MD = {"wire": md_wire, "nameplate": md_nameplate, "voltage_drop": md_voltage_drop, "conduit_fill": md_conduit, "box_fill": md_box}
TITLES = {"wire": "Conductor and overcurrent sizing",
          "nameplate": "Air-conditioning or heat-pump circuit from the nameplate", "voltage_drop": "Voltage drop",
          "conduit_fill": "Conduit fill", "box_fill": "Box fill"}


def body(r, heading):
    out = [f"{heading} {r['job'] or TITLES[r['calc']]}", ""]
    if r["job"]:
        out.extend([f"Calculation: {TITLES[r['calc']]}", ""])
    MD[r["calc"]](r, out)
    if r["flags"]:
        out.append(("#" * (len(heading) + 1)) + " Check before relying on this")
        out.append("")
        for f in r["flags"]:
            out.append(f"- {f}")
        out.append("")
    return out


def to_markdown(r):
    if r["calc"] == "multi":
        title = r["job"] or "Circuit worksheet"
        out = [f"# {title}", ""]
        for part in r["parts"]:
            if part["job"] == title:
                part = dict(part, job="")
            out.extend(body(part, "##"))
    else:
        out = body(r, "#")
    out.append("## Notice")
    out.append("")
    out.append(NOTICE)
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Conductor, breaker, voltage drop, conduit fill and box fill")
    p.add_argument("input", nargs="?", help="job JSON file, or - for stdin")
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument("--template", choices=list(TEMPLATES), help="print a sample input and exit")
    args = p.parse_args(argv)
    if args.template:
        print(json.dumps(TEMPLATES[args.template], indent=2))
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
