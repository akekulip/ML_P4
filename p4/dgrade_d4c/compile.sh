#!/bin/bash
# usage: compile.sh <srcdir> <name>   -> build_<name>/, build_<name>.log
S=/tmp/claude-1002/-home-philip-Projects-ML-P4/b7fee721-94ad-4cff-b5cf-ab01c11eab20/scratchpad/d4c_compile
export SDE=/home/philip/bf-sde-9.13.1
export SDE_INSTALL=$SDE/install
rm -rf $S/build_$2
$SDE_INSTALL/bin/bf-p4c --target tofino --arch tna -g --verbose 2 -o $S/build_$2 $1/switch.p4 > $S/build_$2.log 2>&1
echo "rc=$?"
grep -v "No size defined\|^ *table \|^ *\^" $S/build_$2.log | tail -25
