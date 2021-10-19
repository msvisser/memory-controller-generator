#!/usr/bin/env bash
set -e
BITS=32

OPENLANE_DIR=/home/michiel/tue/Thesis/OpenLane
DESIGNS_DIR=$(pwd)/designs
PDK_ROOT=${OPENLANE_DIR}/pdks
DOCKER_OPTIONS=$(cd ${OPENLANE_DIR} && python3 ./scripts/get_docker_config.py)
OPENLANE_TAG=$(cd ${OPENLANE_DIR} && python3 ./dependencies/get_tag.py)
OPENLANE_IMAGE_NAME=efabless/openlane:${OPENLANE_TAG}

function docker_run {
  docker run --rm \
  -v ${OPENLANE_DIR}:/openLANE_flow \
  -v ${PDK_ROOT}:${PDK_ROOT} -e PDK_ROOT=${PDK_ROOT} \
  -v ${DESIGNS_DIR}:/openLANE_flow/designs \
  ${DOCKER_OPTIONS} ${OPENLANE_IMAGE_NAME} \
  python3 run_designs.py --designs "$@" --regression ./designs/$1/regression.config --threads 32 > /dev/null
}

function build_test {
  echo "[$1 $2] Building"
  mkdir -p designs/$1-$2/src
  python ../../main.py -c $1 -x $2 -b ${BITS} generate > designs/$1-$2/src/top.v
  cp config.tcl designs/$1-$2/config.tcl
  cp regression.config designs/$1-$2/regression.config
  echo "[$1 $2] Done"
}

CODE_LIST=(IdentityCode ParityCode HammingCode ExtendedHammingCode HsiaoCode HsiaoConstructedCode DuttaToubaCode)
CONTROLLER_LIST=(BasicController WriteBackController)

DESIGN_LIST=()

if [ -z $1 ]; then
  for design in "${CODE_LIST[@]}"; do
    for controller in "${CONTROLLER_LIST[@]}"; do
      build_test ${design} ${controller}
      DESIGN_LIST+=(${design}-${controller})
    done
  done

  docker_run "${DESIGN_LIST[@]}"
else
  run_test $1
fi
