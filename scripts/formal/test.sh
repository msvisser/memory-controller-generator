#!/usr/bin/env bash
BITS=32

function run_test {
  echo -n "[ .... ] $1"

  python ../../main.py -c $1 -b ${BITS} -p formal generate test.v 2> /dev/null
  sby -f test.sby > /dev/null

  if [ $? -eq 0 ]; then
    echo -e "\r[\e[0;32mPASSED\e[0m] $1"
  else
    echo -e "\r[\e[0;31mFAILED\e[0m] $1"
    exit 1
  fi

  rm test.v
}

if [ -z $1 ]; then
  run_test IdentityCode
  run_test ParityCode
  run_test HammingCode
  run_test ExtendedHammingCode
  run_test HsiaoCode
  run_test HsiaoConstructedCode
  run_test DuttaToubaCode
  run_test SheLiCode
else
  run_test $1
fi
