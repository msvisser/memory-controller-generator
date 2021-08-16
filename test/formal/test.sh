#!/usr/bin/env bash
BITS=32

function run_test {
  python ../../main.py -c $1 -b ${BITS} -p formal generate > test.v 2> /dev/null
  sby -f test.sby > /dev/null

  if [ $? -eq 0 ]; then
    echo -e "[\e[0;32mPASSED\e[0m] $1"
  else
    echo -e "[\e[0;31mFAILED\e[0m] $1"
  fi
}

run_test IdentityCode
run_test ParityCode
run_test HammingCode
run_test ExtendedHammingCode
run_test HsiaoCode
run_test HsiaoConstructedCode
