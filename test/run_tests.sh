#!/usr/bin/env bash
# Offline tests: the engine under ASan/UBSan (test/engine_test.cc), then the framework's host test of the whole plugin.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/gen_params.py >/dev/null
mkdir -p build
SAN="-fsanitize=address,undefined -fno-omit-frame-pointer -g -O1"
g++ $SAN -std=gnu++11 -Wall -Wextra -Isrc -Ithird_party/mpc-vst-plugins/wrapper src/engine.cc test/engine_test.cc -lm -o build/engine_test
./build/engine_test
g++ -O2 -std=gnu++11 -Isrc -Ithird_party/mpc-vst-plugins/wrapper src/engine.cc test/engine_test.cc -lm -o build/engine_test_O2
./build/engine_test_O2 | grep "^info"
bash third_party/mpc-vst-plugins/tools/test_port.sh vst.json | tail -n 3
