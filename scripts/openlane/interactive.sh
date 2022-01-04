#!/usr/bin/env bash
set -e
BITS=32

OPENLANE_DIR=/home/michiel/tue/Thesis/OpenLane
DESIGNS_DIR=$(pwd)/designs
PDK_ROOT=${OPENLANE_DIR}/pdks
DOCKER_OPTIONS=$(cd ${OPENLANE_DIR} && python3 ./env.py docker-config)
OPENLANE_TAG=$(cd ${OPENLANE_DIR} && python3 ./dependencies/get_tag.py)
OPENLANE_IMAGE_NAME=efabless/openlane:${OPENLANE_TAG}

docker run --rm \
-v ${OPENLANE_DIR}:/openlane \
-v ${PDK_ROOT}:${PDK_ROOT} -e PDK_ROOT=${PDK_ROOT} \
-v ${DESIGNS_DIR}:/openlane/designs \
${DOCKER_OPTIONS} -it ${OPENLANE_IMAGE_NAME} \
bash
