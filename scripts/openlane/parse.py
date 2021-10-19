import csv

design_name_prefix = "/openLANE_flow/designs/"

with open('all.csv') as infile:
    reader = csv.DictReader(infile, delimiter=',', quotechar='"')

    per_design = {}

    for row in reader:
        design = row['design'][len(design_name_prefix):]
        if row['flow_status'] == 'flow_failed':
            continue
        if float(row['spef_tns']) < 0.0:
            continue

        if design in per_design:
            per_design[design].append(row)
        else:
            per_design[design] = [row]

    for design in per_design.keys():
        print(design)

        a_smallest = min(per_design[design], key=lambda d: float(d['DIEAREA_mm^2']))
        smallest = filter(lambda x: x['DIEAREA_mm^2'] == a_smallest['DIEAREA_mm^2'], per_design[design])
        fastest = max(smallest, key=lambda d: float(d['suggested_clock_frequency']))

        print(fastest['DIEAREA_mm^2'], fastest['suggested_clock_frequency'])
