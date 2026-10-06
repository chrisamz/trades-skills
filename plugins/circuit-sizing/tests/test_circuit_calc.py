"""Regression checks for circuit_calc.py. Run with: python tests/test_circuit_calc.py (or pytest).

Expected values were worked by hand from the method, or are widely published results (for example the
number of 12 AWG THHN conductors allowed in common EMT sizes). If a change moves one of these numbers,
find out whether the change or the old value is wrong before updating the expectation.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "skills", "circuit-sizing", "scripts"))

import circuit_calc as C  # noqa: E402


def test_ev_charger_48a_continuous():
    both = C.run(dict(C.TEMPLATES["wire"]))
    # the template asks for the raceway too, so the result has two parts under one notice
    assert both["calc"] == "multi" and [p["calc"] for p in both["parts"]] == ["wire", "conduit_fill"]
    # two 6 AWG and one 10 AWG THHN are 0.1225 sq in; 1/2 EMT allows 0.1216, so 3/4
    assert both["parts"][1]["total_area"] == 0.1225 and both["parts"][1]["smallest"]["trade_size"] == "3/4"
    r = both["parts"][0]
    s = r["steps"]
    # 48 A x 125% = 60 A device; 6 AWG copper is 65 A at 75 C
    assert s["ocpd"] == 60 and s["size"] == "6" and r["final_size"] == "6" and r["egc"] == "10"
    # 2 x 50 ft x 0.491 x 48 / 1000 = 2.36 V = 0.98%
    assert r["voltage_drop"]["tried"][0]["volts"] == 2.36 and r["voltage_drop"]["tried"][0]["pct"] == 0.98
    # with 60 C terminations 6 AWG is only 55 A, so 4 AWG
    assert r["if_60c_terminals"] == "4"


def test_long_nm_run_upsizes_for_voltage_drop():
    r = C.run({"calc": "wire", "load_amps": 16, "continuous": True, "voltage": 120, "wiring": "nm",
               "length_ft": 150})
    assert r["steps"]["ocpd"] == 20 and r["steps"]["size"] == "12"
    pcts = [d["pct"] for d in r["voltage_drop"]["tried"]]
    # 12: 7.92%, 10: 4.96%, 8: 3.11%, 6: 1.96%
    assert pcts == [7.92, 4.96, 3.11, 1.96] and r["final_size"] == "6"
    assert r["egc"] == "12" and r["egc_upsized"] == "6"


def test_ambient_and_bundling_derating():
    r = C.run({"calc": "wire", "load_amps": 40, "continuous": False, "ambient_c": 45,
               "current_carrying_conductors": 6, "terminal_temp": 75})
    s = r["steps"]
    # 8 AWG: 55 x 0.87 x 0.80 = 38.3 A, short of 40; 6 AWG: 75 x 0.696 = 52.2 A
    assert s["size"] == "6" and round(s["corrected"], 1) == 52.2 and s["ocpd"] == 40


def test_small_conductor_limits():
    r = C.run({"calc": "wire", "load_amps": 24, "continuous": False})
    # 12 AWG is 25 A at 75 C but capped at a 20 A device, and the device here is 25 A, so 10 AWG
    assert r["steps"]["ocpd"] == 25 and r["steps"]["size"] == "10"


def test_aluminum_feeder_next_size_up():
    r = C.run({"calc": "wire", "load_amps": 100, "continuous": False, "material": "al"})
    # 100 A device; 1 AWG aluminum is 100 A at 75 C
    assert r["steps"]["size"] == "1" and r["steps"]["ocpd"] == 100 and r["egc"] == "6"


def test_voltage_drop_standalone():
    r = C.run(dict(C.TEMPLATES["voltage_drop"]))
    # 2 x 180 x 0.778 x 30 / 1000 = 8.40 V = 3.50% of 240
    assert r["volts"] == 8.4 and r["pct"] == 3.5 and not r["ok"] and r["size_that_meets"] == "6"
    # 3% of 240 = 7.2 V -> 7.2 x 1000 / (2 x 0.778 x 30) = 154 ft
    assert r["max_length_ft"] == 154


def test_voltage_drop_three_phase():
    r = C.run({"calc": "voltage_drop", "load_amps": 40, "voltage": 208, "phase": 3, "size": "8",
               "length_ft": 100})
    # 1.732 x 100 x 0.778 x 40 / 1000 = 5.39 V
    assert r["volts"] == 5.39


def test_conduit_fill_minimum_size():
    r = C.run(dict(C.TEMPLATES["conduit_fill"]))
    # 3 x 0.0507 + 0.0211 = 0.1732 sq in; 1/2 EMT allows 0.1216, 3/4 EMT allows 0.2132
    assert r["total_area"] == 0.1732 and r["smallest"]["trade_size"] == "3/4"
    assert r["smallest"]["fill_pct"] == 32.5


def published_count(raceway, trade, size):
    r = C.run({"calc": "conduit_fill", "raceway": raceway, "trade_size": trade,
               "conductors": [{"size": size, "count": 1}]})
    return r["check"]["max_alike"]


def test_table_values_reproduce_published_conductor_counts():
    # Widely published maximum counts of THHN conductors (Annex C style tables).
    assert published_count("emt", "1/2", "12") == 9
    assert published_count("emt", "3/4", "12") == 16
    assert published_count("emt", "1/2", "14") == 12
    assert published_count("emt", "1", "10") == 16
    assert published_count("pvc40", "1/2", "12") == 8
    assert published_count("emt", "1", "12") == 26


def test_conduit_check_given_size_and_two_conductor_rule():
    r = C.run({"calc": "conduit_fill", "raceway": "pvc40", "trade_size": "1/2",
               "conductors": [{"size": "6", "count": 2}]})
    # two conductors: 31% of 0.285 = 0.0884; 2 x 0.0507 = 0.1014 does not pass
    assert r["limit"] == 0.31 and not r["check"]["ok"] and r["smallest"]["trade_size"] == "3/4"


def test_box_fill_receptacle():
    r = C.run(dict(C.TEMPLATES["box_fill"]))
    # 4 conductors + 1 clamp + 2 device + 1 ground = 8 x 2.25 = 18.0 cu in
    assert r["required_volume"] == 18.0
    assert r["smallest_standard"][0]["box"].startswith("3 x 2 x 3-1/2")


def test_box_fill_ground_rule_by_edition():
    job = {"calc": "box_fill", "conductors": [{"size": "12", "count": 8}],
           "grounds": {"size": "12", "count": 6}, "edition": "2023"}
    # 8 + (1 + 2 x 0.25) = 9.5 allowances x 2.25 = 21.375
    assert C.run(job)["required_volume"] == 21.375
    job["edition"] = "2017"
    # all grounds count as one: 9 x 2.25 = 20.25
    assert C.run(job)["required_volume"] == 20.25


def test_box_check_and_bad_input():
    r = C.run({"calc": "box_fill", "conductors": [{"size": "14", "count": 6}], "box_volume_in3": 10})
    assert r["required_volume"] == 12.0 and not r["check"]["ok"]
    for bad in ({"calc": "nope"}, {"calc": "wire"}, {"calc": "conduit_fill", "conductors": []},
                {"calc": "box_fill", "conductors": [{"size": "4", "count": 2}]},
                {"calc": "wire", "load_amps": 900}):
        try:
            C.run(bad)
        except C.InputError:
            continue
        raise AssertionError(f"accepted bad input {bad}")


def test_every_worksheet_carries_the_notice():
    for name, job in C.TEMPLATES.items():
        md = C.to_markdown(C.run(dict(job)))
        assert "## Notice" in md and "NFPA" in md, name


# Maximum THHN/THWN conductor counts from an independent published copy of the Annex C tables
# (Elliott Electric Supply reference tables, 2017 and 2020 editions), trade sizes 1/2 to 2.
# Columns: 14, 12, 10, 8, 6, 4, 2, 1/0, 4/0, 250 kcmil. Only counts of three or more are compared,
# because those tables apply the 40% limit to every count while this script applies the one- and
# two-conductor limits to counts of one and two.
PUBLISHED_SIZES = ["14", "12", "10", "8", "6", "4", "2", "1/0", "4/0", "250"]
PUBLISHED_TRADE = ["1/2", "3/4", "1", "1-1/4", "1-1/2", "2"]
PUBLISHED = {
    "emt": [[12, 9, 5, 3, 2, 1, 1, 1, 1, 1], [22, 16, 10, 6, 4, 2, 1, 1, 1, 1], [35, 26, 16, 9, 7, 4, 3, 1, 1, 1],
            [61, 45, 28, 16, 12, 7, 5, 3, 1, 1], [84, 61, 38, 22, 16, 10, 7, 4, 2, 1],
            [138, 101, 63, 36, 26, 16, 11, 7, 4, 3]],
    "imc": [[14, 10, 6, 3, 2, 1, 1, 1, 1, 1], [24, 17, 11, 6, 4, 3, 1, 1, 1, 1], [39, 29, 18, 10, 7, 4, 3, 2, 1, 1],
            [68, 49, 31, 18, 13, 8, 5, 3, 2, 1], [91, 67, 42, 24, 17, 11, 7, 4, 2, 1],
            [149, 109, 69, 39, 28, 17, 12, 8, 4, 3]],
    "rmc": [[13, 9, 6, 3, 2, 1, 1, 1, 1, 1], [22, 16, 10, 6, 4, 2, 1, 1, 1, 1], [36, 26, 17, 9, 7, 4, 3, 1, 1, 1],
            [63, 46, 29, 16, 12, 7, 5, 3, 1, 1], [85, 62, 39, 22, 16, 10, 7, 4, 2, 1],
            [140, 102, 64, 37, 27, 16, 11, 7, 4, 3]],
    "pvc40": [[11, 8, 5, 3, 1, 1, 1, 1, 0, 0], [21, 15, 9, 5, 4, 2, 1, 1, 0, 1], [34, 25, 15, 9, 6, 4, 3, 1, 0, 1],
              [60, 43, 27, 16, 11, 7, 5, 3, 1, 1], [82, 59, 37, 21, 15, 9, 7, 4, 2, 1],
              [135, 99, 62, 36, 26, 16, 11, 7, 4, 3]],
    "pvc80": [[9, 6, 4, 2, 1, 1, 1, 0, 0, 0], [17, 12, 7, 4, 3, 1, 1, 1, 0, 0], [28, 20, 13, 7, 5, 3, 2, 1, 0, 1],
              [51, 37, 23, 13, 9, 6, 4, 2, 1, 1], [70, 51, 32, 18, 13, 8, 6, 3, 1, 1],
              [118, 86, 54, 31, 22, 14, 10, 6, 3, 3]],
}


def test_tables_reproduce_published_counts_for_every_raceway():
    compared = 0
    for raceway, table in PUBLISHED.items():
        for trade, row in zip(PUBLISHED_TRADE, table):
            for size, want in zip(PUBLISHED_SIZES, row):
                if want < 3:
                    continue
                got = published_count(raceway, trade, size)
                assert got == want, (raceway, trade, size, got, want)
                compared += 1
    assert compared > 150


def test_most_alike_honors_the_two_conductor_limit():
    # two 6 AWG THHN are 0.1014 sq in; 31% of 1/2 EMT is 0.0942, so only one is allowed
    assert published_count("emt", "1/2", "6") == 1


def test_large_conductor_voltage_drop_uses_effective_impedance():
    r = C.run({"calc": "voltage_drop", "load_amps": 200, "voltage": 240, "phase": 1, "size": "4/0",
               "length_ft": 200})
    # steel conduit: 0.080 ohm per 1,000 ft effective against 0.0608 dc -> 2 x 200 x 0.080 x 200 / 1000 = 6.4 V
    assert r["resistance"] == 0.080 and r["volts"] == 6.4 and r["resistance_source"] == "Chapter 9, Table 9"
    r = C.run({"calc": "voltage_drop", "load_amps": 200, "voltage": 240, "size": "4/0", "length_ft": 200,
               "raceway_material": "pvc"})
    assert r["resistance"] == 0.074
    # small conductors keep the dc value, which is the larger one
    r = C.run({"calc": "voltage_drop", "load_amps": 16, "voltage": 120, "size": "12", "length_ft": 100})
    assert r["resistance"] == 1.98 and r["resistance_source"] == "Chapter 9, Table 8"


def test_resistance_tables_agree_with_each_other():
    # Alternating-current resistance in Table 9 is within a few percent of the dc value in Table 8 for
    # every size, so a gross typing error in either table would show up as a large ratio here.
    for material in ("cu", "al"):
        for size, dc in C.RESISTANCE[material].items():
            z = C.EFFECTIVE_Z[material]["pvc"][size]
            assert 0.75 < z / dc < 1.9, (material, size, z, dc)
        values = [C.RESISTANCE[material][s] for s in C.SIZES if s in C.RESISTANCE[material]]
        assert values == sorted(values, reverse=True)


def test_ampacity_tables_are_monotonic():
    for material in ("cu", "al"):
        prev = (0, 0, 0)
        for size in C.SIZES:
            if size not in C.AMPACITY[material]:
                continue
            row = C.AMPACITY[material][size]
            assert row[0] <= row[1] <= row[2] and all(a >= b for a, b in zip(row, prev)), (material, size)
            prev = row


def test_air_conditioner_from_nameplate():
    r = C.run(dict(C.TEMPLATES["nameplate"]))
    s = r["steps"]
    # 24.3 A minimum circuit ampacity: 12 AWG copper is 25 A at 75 C; device is the 40 A nameplate maximum.
    # The ground for a 40 A device would be 10 AWG, but it need not be larger than the circuit conductors.
    assert s["size"] == "12" and s["ocpd"] == 40 and r["egc"] == "12"
    assert any("240.4(G)" in f for f in r["flags"])
    # 2 x 40 ft x 1.98 x 24.3 / 1000 = 3.85 V
    assert r["voltage_drop"]["tried"][0]["volts"] == 3.85
    # in NM cable the 60 C column governs: 12 AWG is 20 A, so 10 AWG (30 A)
    nm = C.run(dict(C.TEMPLATES["nameplate"], wiring="nm"))
    assert nm["steps"]["size"] == "10" and nm["egc"] == "10"


def test_nameplate_odd_maximum_rounds_down():
    r = C.run({"calc": "nameplate", "mca": 18.5, "mocp": 28})
    # largest standard rating not over 28 A is 25 A; 14 AWG copper is 20 A at 75 C, enough for 18.5 A
    assert r["steps"]["ocpd"] == 25 and r["steps"]["size"] == "14" and r["egc"] == "14"
    try:
        C.run({"calc": "nameplate", "mca": 30, "mocp": 20})
    except C.InputError:
        return
    raise AssertionError("accepted a maximum device below the minimum circuit ampacity")


def test_several_jobs_share_one_notice():
    r = C.run({"job": "Kitchen circuit", "jobs": [dict(C.TEMPLATES["conduit_fill"]), dict(C.TEMPLATES["box_fill"])]})
    md = C.to_markdown(r)
    assert r["calc"] == "multi" and len(r["parts"]) == 2
    assert md.count("## Notice") == 1 and md.count("Calculation aid only") == 1
    assert md.startswith("# Kitchen circuit")


def test_how_many_conductors_a_breaker_allows():
    r = C.run({"calc": "conduit_fill", "raceway": "emt", "trade_size": "3/4", "breaker_a": 20,
               "conductors": [{"size": "12", "count": 16}]})
    row = r["derating"]["rows"][0]
    # 12 AWG is 30 A at 90 C: 4 to 6 -> 24 A, 7 to 9 -> 21 A, 10 to 20 -> 15 A
    assert [b["ampacity"] for b in row["bands"][:4]] == [30.0, 24.0, 21.0, 15.0]
    assert row["most"] == 9
    # 10 AWG on 30 A circuits: 40 A x 0.8 = 32 A holds, x 0.7 = 28 A does not
    r = C.run({"calc": "conduit_fill", "breaker_a": 30, "conductors": [{"size": "10", "count": 6}]})
    assert r["derating"]["rows"][0]["most"] == 6
    # a 25 A breaker is over the small-conductor limit for 12 AWG whatever the count
    r = C.run({"calc": "conduit_fill", "breaker_a": 25, "conductors": [{"size": "12", "count": 3}]})
    assert r["derating"]["rows"][0]["most"] == 0


def test_motor_warning_only_where_it_could_apply():
    plain = C.run({"calc": "wire", "job": "Range circuit", "load_amps": 40})
    assert not any("Articles 430" in f for f in plain["flags"])
    saw = C.run({"calc": "wire", "job": "Shed, lights and table saw", "load_amps": 16})
    assert any("Articles 430" in f for f in saw["flags"])


def test_rooftop_stacked_derating_with_raceway():
    r = C.run({"calc": "wire", "load_amps": 24, "continuous": True, "ambient_c": 50,
               "current_carrying_conductors": 9, "conduit": {"raceway": "emt", "extra": [
                   {"size": "8", "insulation": "thhn", "count": 7}]}})
    s = r["parts"][0]["steps"]
    # 10 AWG: 40 x 0.82 x 0.70 = 23.0 A, short of 24; 8 AWG: 55 x 0.574 = 31.6 A
    assert s["ocpd"] == 30 and s["size"] == "8" and round(s["corrected"], 1) == 31.6
    # nine 8 AWG and one 10 AWG: 0.3505 sq in; 1 in. EMT allows 0.3456, so 1-1/4
    assert r["parts"][1]["total_area"] == 0.3505 and r["parts"][1]["smallest"]["trade_size"] == "1-1/4"


def test_aluminum_feeder_to_a_detached_building():
    r = C.run({"calc": "wire", "load_amps": 80, "breaker_a": 100, "material": "al", "voltage": 240,
               "length_ft": 180, "raceway_material": "pvc",
               "conduit": {"raceway": "pvc40", "insulation": "xhhw", "neutral": True}})
    w = r["parts"][0]
    # 1 AWG aluminum is 100 A at 75 C; at 180 ft and 80 A it drops 3.04%, so 1/0 (2.41%)
    assert w["steps"]["size"] == "1" and w["final_size"] == "1/0"
    assert [d["pct"] for d in w["voltage_drop"]["tried"]] == [3.04, 2.41]
    # ground for 100 A is 6 AWG aluminum, raised in proportion (x 1.262) to 4 AWG
    assert w["egc"] == "6" and w["egc_upsized"] == "4"
    # three 1/0 and one 4 AWG XHHW: 0.6289 sq in; 1-1/4 PVC allows 0.5812, so 1-1/2
    assert r["parts"][1]["total_area"] == 0.6289 and r["parts"][1]["smallest"]["trade_size"] == "1-1/2"


def test_long_large_conductor_run():
    r = C.run({"calc": "voltage_drop", "load_amps": 160, "voltage": 240, "size": "3/0", "length_ft": 400})
    # steel conduit 0.094: 2 x 400 x 0.094 x 160 / 1000 = 12.03 V = 5.01%; 400 kcmil (0.056) gives 2.99%
    assert r["volts"] == 12.03 and r["pct"] == 5.01 and r["size_that_meets"] == "400"


def test_worksheet_says_why_the_next_size_down_fails():
    r = C.run({"calc": "wire", "load_amps": 24, "continuous": True, "ambient_c": 50,
               "current_carrying_conductors": 9})
    rej = r["steps"]["rejected"]
    # 10 AWG: 40 x 0.82 x 0.70 = 23.0 A, under the 24 A load
    assert rej["size"] == "10" and "23.0 A" in rej["why"]
    assert "next size down, 10 AWG" in C.to_markdown(r)


def test_condenser_changeout_with_existing_wire_and_breaker():
    job = dict(C.TEMPLATES["nameplate"], existing_size="12", breaker_a=30)
    r = C.run(job)
    md = C.to_markdown(r)
    assert r["existing"]["verdict"].startswith("adequate")
    assert "can stay" in r["existing_breaker"]["note"]
    # the answer depends on 75 C terminations: at 60 C, 12 AWG is 20 A and 10 AWG (30 A) is needed
    assert r["if_60c_terminals"] == "10" and any("60 C only" in f for f in r["flags"])
    # 25 A against 24.3 A is under a 5% margin
    assert any(f.startswith("Thin margin") for f in r["flags"])
    assert "Existing 12 AWG" in md and "The existing 30 A breaker is within" in md
    assert not any("Article 430" in f for f in r["flags"])
    over = C.run(dict(job, breaker_a=50))
    assert "must be replaced" in over["existing_breaker"]["note"]


def test_existing_conductor_too_small():
    r = C.run({"calc": "wire", "load_amps": 40, "existing_size": "10"})
    assert r["existing"]["verdict"].startswith("too small")


def test_raised_voltage_drop_target_is_flagged():
    r = C.run({"calc": "wire", "load_amps": 80, "breaker_a": 100, "material": "al", "length_ft": 180,
               "max_voltage_drop_pct": 5})
    assert r["final_size"] == "1" and any("target entered is 5%" in f for f in r["flags"])
    r = C.run({"calc": "wire", "load_amps": 80, "breaker_a": 100, "material": "al", "length_ft": 180})
    assert not any("target entered" in f for f in r["flags"])


def test_over_target_run_lists_other_options():
    r = C.run({"calc": "voltage_drop", "load_amps": 160, "voltage": 240, "size": "3/0", "length_ft": 400})
    text = " ".join(r["options"])
    # parallel run: half of 5.01%; PVC: 2 x 400 x 0.088 x 160 / 1000 = 11.26 V = 4.7%; 3% at 96 A
    assert "about 2.5%" in text and "about 4.7%" in text and "about 96 A" in text
    ok = C.run({"calc": "voltage_drop", "load_amps": 20, "voltage": 240, "size": "10", "length_ft": 50})
    assert ok["options"] == []


def test_lug_rating_entered_as_wire_rating_is_flagged():
    job = {"calc": "wire", "load_amps": 24, "continuous": True, "ambient_c": 50,
           "current_carrying_conductors": 9, "insulation_temp": 75}
    r = C.run(job)
    # 75 C column: 50 x 0.75 x 0.70 = 26.2 A, and the worksheet says the entry looks wrong
    assert round(r["steps"]["corrected"], 1) == 26.2
    assert any("belongs in terminal_temp" in f for f in r["flags"])
    # entered by type, THHN is 90 C: 55 x 0.82 x 0.70 = 31.6 A, with no warning
    job.pop("insulation_temp")
    r = C.run(dict(job, insulation="THHN"))
    assert round(r["steps"]["corrected"], 1) == 31.6
    assert not any("belongs in terminal_temp" in f for f in r["flags"])
    # wet-rated 75 C types are taken at 75 C without complaint
    r = C.run(dict(job, insulation="thwn"))
    assert r["steps"]["insulation"] == 75 and not any("belongs in terminal_temp" in f for f in r["flags"])


def test_conduit_type_carries_into_voltage_drop():
    job = {"calc": "wire", "load_amps": 80, "breaker_a": 100, "material": "al", "length_ft": 180,
           "conduit": {"raceway": "pvc40", "insulation": "xhhw", "neutral": True}}
    r = C.run(job)
    assert any("in pvc conduit" in f for f in r["parts"][0]["flags"])


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"{len(tests)} passed")
