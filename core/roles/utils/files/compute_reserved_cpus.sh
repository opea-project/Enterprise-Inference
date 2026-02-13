#!/bin/bash
set -euo pipefail

TOTAL_RESERVED=$1
if [ -z "$TOTAL_RESERVED" ] || [ "$TOTAL_RESERVED" -le 0 ]; then
  echo "Error: missing or invalid TOTAL_RESERVED argument (must be > 0)" >&2
  exit 1
fi

total_numa=$(lscpu | awk -F: '/NUMA node\(s\):/{print $2}' | tr -d ' ')
if [ -z "$total_numa" ]; then
  echo "Error: failed to detect NUMA nodes from lscpu" >&2
  exit 1
fi

threads_per_core=$(lscpu | awk '/Thread.*per core:/{print $4}')
[ -n "$threads_per_core" ] || threads_per_core=1

ht_enabled=false
[ "$threads_per_core" -eq 2 ] && ht_enabled=true

cpus_per_numa=$(( (TOTAL_RESERVED + total_numa - 1) / total_numa ))
out=""

for i in $(seq 0 $((total_numa - 1))); do
  line=$(lscpu | grep "NUMA node$i CPU" | cut -d: -f2 | xargs)
  if [ -z "$line" ]; then
    echo "Error: failed to read NUMA node$i CPU list from lscpu" >&2
    exit 1
  fi
  IFS=',' read -ra segments <<< "$line"
  declare -a all_cpus=()
  for seg in "${segments[@]}"; do
    seg=$(echo "$seg" | xargs)
    if [[ "$seg" == *"-"* ]]; then
      IFS='-' read -r start end <<< "$seg"
      for ((c=start; c<=end; c++)); do all_cpus+=("$c"); done
    else
      all_cpus+=("$seg")
    fi
  done
  IFS=$'\n' sorted=($(printf '%s\n' "${all_cpus[@]}" | sort -n))
  unset IFS
  total_cpus_in_numa=${#sorted[@]}
  if [ "$ht_enabled" = true ] && [ "$total_cpus_in_numa" -ge "$((cpus_per_numa * 2))" ]; then
    half=$((total_cpus_in_numa / 2))
    physical_half=("${sorted[@]:0:$half}")
    ht_half=("${sorted[@]:$half:$half}")
    reserve_from_physical=$(( (cpus_per_numa + 1) / 2 ))
    reserve_from_ht=$(( cpus_per_numa - reserve_from_physical ))
    selected=()
    for ((j=0; j<reserve_from_physical && j<${#physical_half[@]}; j++)); do
      selected+=("${physical_half[$j]}")
    done
    for ((j=0; j<reserve_from_ht && j<${#ht_half[@]}; j++)); do
      selected+=("${ht_half[$j]}")
    done
  else
    selected=("${sorted[@]:0:$cpus_per_numa}")
  fi
  IFS=$'\n' selected_sorted=($(printf '%s\n' "${selected[@]}" | sort -n))
  unset IFS
  for cpu in "${selected_sorted[@]}"; do out="${out}${cpu},"; done
done

out="${out%,}"
if [ -z "$out" ]; then
  echo "Error: failed to compute reserved CPU list (empty result)" >&2
  exit 1
fi
echo "NRI_RESERVED_CPU_LIST=$out"
