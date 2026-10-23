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
# The UI through the wrapper, as MPC drives it: header buttons, pop-up lists, the data wheel on a pop-up value, a cable
MV=third_party/mpc-vst-plugins
python3 "$MV/tools/gen_vst.py" vst.json --params-h >/dev/null
SANW="-fsanitize=address,undefined -fno-omit-frame-pointer -g -O1"
g++ $SANW -std=gnu++11 -Isrc -Ibuild -I"$MV/wrapper" -c src/engine.cc -o build/ui_engine.o
gcc $SANW -std=gnu11 -Ibuild -c "$MV/wrapper/vst2_wrap.c" -o build/ui_wrap.o
gcc $SANW -std=gnu11 -Ibuild -c test/ui_test.c -o build/ui_test.o
g++ $SANW build/ui_engine.o build/ui_wrap.o build/ui_test.o -lm -ldl -lpthread -o build/ui_test
ASAN_OPTIONS=detect_leaks=0 ./build/ui_test
