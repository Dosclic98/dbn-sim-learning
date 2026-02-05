#!/usr/bin/env bash
mkdir -p dbn-sim-learning-container/{plots,results,traces}

# Place the pysmile_license.py file in the current directory before running this command.
sudo docker run --rm -it \
  -v "$PWD/pysmile_license.py":/home/simulation/dbn-sim-learning/pysmile_license.py:ro \
  -v "$PWD/dbn-sim-learning-container/plots":/home/simulation/dbn-sim-learning/plots \
  -v "$PWD/dbn-sim-learning-container/results":/home/simulation/dbn-sim-learning/results \
  -v "$PWD/dbn-sim-learning-container/traces":/home/simulation/dbn-sim-learning/traces \
  omnet