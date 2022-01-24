#!/usr/bin/bash
set -e

DESIGNS=(designs/**/runs/config_test_batch)
OUTPUT=all.csv

head -n 1 ${DESIGNS[0]}/reports/final_summary_report.csv | tr -d '\n' > ${OUTPUT}
echo ",synthesis_area_um^2,resizer_area_um^2,power_W" >> ${OUTPUT}
for design in "${DESIGNS[@]}"; do
    tail -n 1 ${design}/reports/final_summary_report.csv | tr -d '\n' >> ${OUTPUT}
    echo -n "," >> ${OUTPUT}
    sed -n "s/^   Chip area for module '\\\\top': \(.*\)$/\1/p" ${design}/reports/synthesis/1-synthesis.stat.rpt.strategy0 | tr -d '\n' >> ${OUTPUT}
    echo -n "," >> ${OUTPUT}
    sed -n "5s/Design area \([0-9]*\) u^2 [0-9]*% utilization./\1/p" ${design}/reports/placement/8-resizer_sta.area.rpt | tr -d '\n' >> ${OUTPUT}
    echo -n "," >> ${OUTPUT}
    sed -n "s/Total *[^ ]* *[^ ]* *[^ ]* *\([^ ]*\) 100.0%/\1/p" ${design}/reports/routing/26-parasitics_sta.power.rpt >> ${OUTPUT}
done

csview ${OUTPUT} > ${OUTPUT}.txt
