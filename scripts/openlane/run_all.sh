#!/usr/bin/env bash
set -e
BITS=32

OPENLANE_DIR=/home/michiel/tue/Thesis/OpenLane
DESIGNS_DIR=$(pwd)/designs
PDK_ROOT=${OPENLANE_DIR}/pdks
DOCKER_OPTIONS=$(cd ${OPENLANE_DIR} && python3 ./env.py docker-config)
OPENLANE_TAG=$(cd ${OPENLANE_DIR} && python3 ./dependencies/get_tag.py)
OPENLANE_IMAGE_NAME=efabless/openlane:${OPENLANE_TAG}

function docker_run {
  docker run --rm \
  -v ${OPENLANE_DIR}:/openlane \
  -v ${PDK_ROOT}:${PDK_ROOT} -e PDK_ROOT=${PDK_ROOT} \
  -v ${DESIGNS_DIR}:/openlane/designs \
  ${DOCKER_OPTIONS} ${OPENLANE_IMAGE_NAME} \
  python3 run_designs.py --threads 16 --tag test_adj $@
}

function build_test {
  echo "[$1 $2] Building"
  mkdir -p designs/$1-$2/src
  python -m memory_controller_generator.testbench.example -x $1 -c $2 -b ${BITS} generate designs/$1-$2/src/top.v
  cp config.tcl designs/$1-$2/config.tcl
  echo "[$1 $2] Done"
}

CODE_LIST=(IdentityCode ParityCode HammingCode ExtendedHammingCode HsiaoCode HsiaoConstructedCode DuttaToubaCode SheLiCode)
CONTROLLER_LIST=(BasicController WriteBackController RefreshController ForceRefreshController TopRefreshController TopBottomRefreshController ContinuousRefreshController)

DESIGN_LIST=()

for code in "${CODE_LIST[@]}"; do
  for controller in "${CONTROLLER_LIST[@]}"; do
    build_test ${controller} ${code}
    DESIGN_LIST+=(${controller}-${code})
  done
done

docker_run "${DESIGN_LIST[@]}"
