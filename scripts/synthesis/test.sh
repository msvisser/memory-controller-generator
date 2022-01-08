#!/usr/bin/env bash
BITS=32

function run_test {
  python -m memory_controller_generator.testbench.example -c $1 -b ${BITS} generate -t il |
  yosys -c test.tcl -f ilang - |
  grep "Chip area for\|Delay ="

  echo "--------------------------------------------------"
}

if [ -z $1 ]; then
  run_test IdentityCode
  run_test ParityCode
  run_test HammingCode
  run_test ExtendedHammingCode
  run_test HsiaoCode
  run_test HsiaoConstructedCode
  run_test DuttaToubaCode
else
  run_test $1
fi
