#!/usr/bin/bash
set -e

REPORTS=(designs/**/runs/**/reports/final_summary_report.csv)
OUTPUT=all.csv

head -n 1 ${REPORTS[0]} > ${OUTPUT}
for report in "${REPORTS[@]}"; do
    tail -n 1 ${report} >> ${OUTPUT}
done

# cat ${OUTPUT} | sort --field-separator=, --key=4.19n,4 | sort --field-separator=, --key=2,2 --stable > ${OUTPUT}
csview ${OUTPUT} > ${OUTPUT}.txt
