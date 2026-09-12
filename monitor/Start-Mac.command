#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
./iPhone18Stockroom
result=$?
if [ "$result" -ne 0 ]; then
  printf '\nStockroom exited with an error. Press Return to close.\n'
  read -r reply
fi
exit "$result"
