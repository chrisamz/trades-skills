"""Regression checks for load_calc.py. Run with: python tests/test_load_calc.py (or pytest).

Each expected value was worked by hand from the method. If a change to the script moves one of
these numbers, either the change is wrong or the rule was wrong before; find out which before
updating the expectation, and record the source in references/method-notes.md.
"""

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "skills", "residential-load-calc", "scripts"))

import load_calc as L  # noqa: E402


def job(**changes):
    j = copy.deepcopy(L.TEMPLATE)
    j.update(changes)
    return j


def alt(result, evse, hvac=""):
    for a in result["alternates"]:
        if a["evse"] == L.EVSE_LABEL.get(evse, "") and a["hvac"] == L.HVAC_LABEL.get(hvac, ""):
            return a
    raise AssertionError(f"no alternate for {evse}/{hvac}")


def full(j):
    r = L.run(j)
    r["alternates"] = L.alternates(j, r)
    r["charger_limits"] = L.charger_limits(j, r)
    r["branch_circuits"] = L.branch_circuits(j, r)
    return r


def test_existing_dwelling_2023_83a():
    # pool 56,784 -> 8,000 + 48,784 x 0.4 = 27,513.6 VA
    r = full(job())
    assert r["method"] == "220.83(A)"
    assert r["total_va"] == 27514 and r["calculated_amps"] == 114.6 and r["fits"]
    assert alt(r, "full", "tiered")["calculated_amps"] == 143.4
    assert alt(r, "continuous_125", "tiered")["calculated_amps"] == 155.4
    assert alt(r, "general", "full")["calculated_amps"] == 139.6
    assert alt(r, "continuous_125", "full")["calculated_amps"] == 180.4
    assert r["alternates"][-1]["calculated_amps"] == 130.1  # 220.82 cross-check
    assert r["branch_circuits"][0]["min_circuit_amps"] == 60
    assert r["charger_limits"] == []


def test_existing_dwelling_83b_new_heat_pump():
    j = job()
    j["hvac"][0]["va"] = 0
    j["hvac"].append({"type": "heat_pump", "va": 7000, "new": True})
    r = L.run(j)
    # heating 17,000 at 100% + pool 46,784 -> 8,000 + 15,513.6
    assert r["method"] == "220.83(B)" and r["total_va"] == 40514 and r["calculated_amps"] == 168.8


def test_optional_method_2023():
    r = L.run(job(method="220.82"))
    # general 46,784 -> 10,000 + 14,713.6; furnace 10 kW at 65% = 6,500
    assert r["total_va"] == 31214 and r["calculated_amps"] == 130.1


def test_optional_method_2026():
    j = {"edition": "2026", "method": "120.82", "system": {"voltage": 240, "service_rating_a": 200},
         "dwelling": {"floor_area_sqft": 2400, "small_appliance_circuits": 3, "laundry_circuits": 1},
         "appliances": [{"va": 3500}, {"va": 4500}, {"va": 14000}, {"va": 5500}],
         "hvac": [{"type": "heat_pump", "va": 5000}, {"type": "supplemental_heat", "va": 10000}],
         "evse": [{"amps": 48}]}
    r = full(j)
    # general 38,300 -> 8,000 + 12,120; HP 5,000 + strips 6,500; EVSE 11,520 at 100%
    assert r["method"] == "120.82" and r["total_va"] == 43140 and r["calculated_amps"] == 179.8
    assert r["alternates"] == []
    assert any("provisional" in f for f in r["flags"])


def test_recorded_demand():
    j = {"edition": "2023", "method": "220.87", "system": {"voltage": 240, "service_rating_a": 100},
         "hvac": [{"type": "heat_pump", "va": 5500, "new": True},
                  {"type": "supplemental_heat", "va": 5000, "new": True}],
         "measured": {"peak_kw": 7.9, "basis": "utility_12mo"}}
    r = L.run(j)
    # 7,900 x 1.25 + 10,500
    assert r["total_va"] == 20375 and r["calculated_amps"] == 84.9 and r["fits"]


def test_recorded_demand_evse_125():
    j = {"edition": "2023", "method": "220.87", "system": {"voltage": 240, "service_rating_a": 200},
         "evse": [{"amps": 48, "new": True}], "options": {"evse_treatment": "continuous_125"},
         "measured": {"peak_kw": 14.8}}
    r = L.run(j)
    assert r["calculated_amps"] == 137.1 and r["headroom_a"] == 62.9


def test_verdict_flips_and_charger_limit():
    j = {"edition": "2020", "method": "220.83", "system": {"voltage": 240, "service_rating_a": 125},
         "dwelling": {"floor_area_sqft": 1800},
         "appliances": [{"va": 10000}, {"va": 5000}, {"va": 4500}, {"va": 1200}, {"va": 1500}],
         "hvac": [{"type": "ac", "va": 4300}], "evse": [{"va": 9600, "new": True}]}
    r = full(j)
    assert r["calculated_amps"] == 96.7 and r["fits"]
    assert alt(r, "full", "tiered")["fits"] and alt(r, "full", "tiered")["calculated_amps"] == 120.7
    assert not alt(r, "continuous_125", "tiered")["fits"]
    assert alt(r, "continuous_125", "full")["calculated_amps"] == 141.4
    assert [c["max_amps"] for c in r["charger_limits"]] == [33, 35, 26]
    assert r["branch_circuits"][0]["min_circuit_amps"] == 50


def test_evse_minimum_2023_and_load_management():
    j = job()
    j["evse"] = [{"amps": 16, "new": True}]
    assert any("7,200 VA minimum" in ln["label"] for ln in L.run(j)["lines"])
    j["evse"] = [{"amps": 48, "ems_limit_amps": 24, "new": True}]
    r = L.run(j)
    assert any("load management" in ln["label"] for ln in r["lines"])
    # 24 A x 240 V = 5,760 VA in the pool instead of 11,520
    assert r["total_va"] == round(8000 + (56784 - 11520 + 5760 - 8000) * 0.4)


def test_30_day_recording_with_solar_is_refused():
    j = {"edition": "2023", "method": "220.87", "system": {"service_rating_a": 100},
         "evse": [{"amps": 32, "new": True}],
         "measured": {"peak_amps": 40, "basis": "recording_30d", "has_pv_or_storage": True}}
    r = full(j)
    assert any("NOT PERMITTED" in f for f in r["flags"])
    # 40 A x 1.25 + 32 A = 82 A is under the 100 A rating, but the method cannot be used here,
    # so the worksheet must not report a fits verdict or anything derived from one.
    assert r["calculated_amps"] == 82.0 and r["fits"] is None and len(r["not_permitted"]) == 1
    assert r["charger_limits"] == []
    md = L.to_markdown(r)
    assert "NOT A VALID RESULT" in md and "FITS" not in md and "Smallest standard rating" not in md
    assert "| yes |" not in md and md.count("| not valid |") == 2
    # same job on 12 months of utility data is permitted and gets a normal verdict
    j["measured"]["basis"] = "utility_12mo"
    r = full(j)
    assert r["fits"] is True and r["not_permitted"] == [] and "**FITS**" in L.to_markdown(r)


def test_optional_method_under_100a_gives_no_verdict():
    j = job(method="220.82", evse=[])
    j["system"]["service_rating_a"] = 60
    r = full(j)
    assert r["fits"] is None and "100 A or larger" in r["not_permitted"][0]
    md = L.to_markdown(r)
    assert "NOT A VALID RESULT" in md and "DOES NOT FIT" not in md
    # under 220.83 the same service gets a verdict; only its 220.82 cross-check row is marked
    j["method"] = "220.83"
    j["appliances"].append({"name": "Hot tub", "va": 6000, "new": True})
    r = full(j)
    assert r["fits"] is False and r["not_permitted"] == []
    md = L.to_markdown(r)
    assert "**DOES NOT FIT**" in md and md.count("| not valid |") == 1


def test_bad_input_is_rejected():
    for bad in ({"edition": "2014"}, {"edition": "2023", "method": "x"},
                {"edition": "2023", "method": "220.87", "system": {"service_rating_a": 100}}):
        try:
            L.run(bad)
        except L.InputError:
            continue
        raise AssertionError(f"accepted bad input {bad}")


def test_worksheet_carries_the_notice():
    r = full(job())
    md = L.to_markdown(r)
    assert "## Notice" in md and "not verified against the code text" in md and "NFPA" in md


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"{len(tests)} passed")
