#!/usr/bin/env bash
BITS=32

function run_test {
  python ../../main.py -c $1 -b ${BITS} generate |
  yosys -c test.tcl -f verilog - |
  grep "Chip area for\|Delay ="

  echo "--------------------------------------------------"
}

run_test IdentityCode
run_test ParityCode
run_test HammingCode
run_test ExtendedHammingCode
run_test HsiaoCode
run_test HsiaoConstructedCode
