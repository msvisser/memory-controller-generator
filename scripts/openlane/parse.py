import csv
from matplotlib import widgets
import matplotlib.pyplot as plt
import numpy as np

design_name_prefix = "/openlane/designs/"

design_dict = {}
with open('all.csv') as infile:
    reader = csv.DictReader(infile, delimiter=',', quotechar='"')

    for row in reader:
        design = row['design'][len(design_name_prefix):]
        design_dict[design] = row

CONTROLLERS = ["BasicController", "WriteBackController", "RefreshController"]
CONTROLLERS_REFRESH = ["RefreshController", "ForceRefreshController", "ContinuousRefreshController", "TopRefreshController", "TopBottomRefreshController"]
CODES = ["IdentityCode", "ParityCode", "HammingCode", "ExtendedHammingCode", "HsiaoCode", "HsiaoConstructedCode", "DuttaToubaCode", "SheLiCode"]

for name, controllers in [("controller", CONTROLLERS), ("refresh", CONTROLLERS_REFRESH)]:
    fig_freq, ax_freq = plt.subplots()
    fig_area, ax_area = plt.subplots()
    fig_die_area, ax_die_area = plt.subplots()
    fig_power, ax_power = plt.subplots()

    for ci, controller in enumerate(controllers):
        freqs = []
        areas = []
        levels = []
        die_areas = []
        powers = []

        for code in CODES:
            design = f"{controller}-{code}"
            if design not in design_dict:
                print(design, "missing results")
                continue
            row = design_dict[design]
            clk_freq = float(row['suggested_clock_frequency'])
            clk_period = float(row['suggested_clock_period'])
            synth_area = float(row['synthesis_area_um^2'])
            area = int(row['resizer_area_um^2'])
            level = int(row['level'])
            die_area = float(row['DIEAREA_mm^2']) * 1_000_000
            power = float(row['power_W']) * 1_000

            if name == "controller":
                print(f"{design:50} {clk_freq:.2f} MHz  {clk_period:.2f} ns  {synth_area:9.3f} um^2  {area:5d} um^2  {die_area:.3f} um^2  {power:5.2f} mW")

            freqs.append(clk_freq)
            areas.append(area)
            levels.append(level)
            die_areas.append(die_area)
            powers.append(power)

        w = 0.9 / len(controllers)
        xs = np.arange(len(CODES)) - (((len(controllers)-1)/2) * w) + w*ci
        ax_freq.bar(xs, freqs, width=w)
        ax_area.bar(xs, areas, width=w)
        ax_die_area.bar(xs, die_areas, width=w)
        ax_power.bar(xs, powers, width=w)

        if name == "controller":
            print()

    xs = np.arange(len(CODES))

    ax_freq.set_xticks(xs, labels=CODES, rotation=30, ha="right", rotation_mode="anchor")
    ax_freq.yaxis.grid(True)
    ax_freq.set_ylabel("Frequency (MHz)")
    ax_freq.legend(controllers)
    fig_freq.tight_layout()
    fig_freq.savefig(f"tapeout-{name}-freqency.pdf")

    ax_area.set_xticks(xs, labels=CODES, rotation=30, ha="right", rotation_mode="anchor")
    ax_area.yaxis.grid(True)
    ax_area.set_ylabel("Area ($\\mu m^2$)")
    ax_area.legend(controllers)
    fig_area.tight_layout()
    fig_area.savefig(f"tapeout-{name}-area.pdf")

    ax_die_area.set_xticks(xs, labels=CODES, rotation=30, ha="right", rotation_mode="anchor")
    ax_die_area.yaxis.grid(True)
    ax_die_area.set_ylabel("Area ($\\mu m^2$)")
    ax_die_area.legend(controllers)
    fig_die_area.tight_layout()
    fig_die_area.savefig(f"tapeout-{name}-die_area.pdf")

    ax_power.set_xticks(xs, labels=CODES, rotation=30, ha="right", rotation_mode="anchor")
    ax_power.yaxis.grid(True)
    ax_power.set_ylabel("Power ($mW$)")
    ax_power.legend(controllers)
    fig_power.tight_layout()
    fig_power.savefig(f"tapeout-{name}-power.pdf")
