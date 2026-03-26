#!/usr/bin/env bash
$numProcsToUse = $(( $(nproc) - 2 ))
$numProcsToUse = $(( $numProcsToUse > 0 ? $numProcsToUse : 1 ))
$numRuns = 1000
echo "Executing $numRuns runs using at most $numProcsToUse parallel processes..."
python3 replicate_results.py -r $numRuns -p $numProcsToUse