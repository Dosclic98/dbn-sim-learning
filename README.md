# Attack Graph driven Discrete Event Simulation for security assessment in Power Systems — Artifacts - SIGSIM-PADS 2026

Repository for running Control Finite State Machine-based simulations in OMNeT++ and learning Dynamic Bayesian Network (DBN) parameters from generated data traces.

## Replicating the results (recommended: Docker)

Using the provided Dockerfile, you can build a container that includes all necessary dependencies to run the full pipeline (simulation, parameterization, validation, and analysis). Setting up the simulation environment manually can be complex, since the OMNeT++ installation is OS-dependent, so using Docker is the recommended approach.

### Reference host specs (used to obtain the reported results)

Host Specifications:
- **OS**: Ubuntu 22.04.5 LTS (Jammy)
- **Linux** kernel: 5.15.0-164-generic

- **CPU**: Intel(R) Xeon(R) Gold 6418H (32 logical cores @2.10GHz)
- **RAM**: 64 GB (swap: 8 GB)

Docker:
- **Docker** Engine: 28.2.2
- **buildx**: 0.21.3

### Expected run time
The full pipeline (simulation, parameterization, validation, and analysis) takes approximately **2 hours and 15 minutes** on the reference host, with 1000 traces and using 30 cores for parallelization. The exact time may vary based on the host specifications. The most time-consuming step is the validation since the DBN must be retrained and tested multiple times for every fold and for every evidence frequency.

### 1) Clone the repository locally

```bash
git clone https://github.com/Dosclic98/dbn-sim-learning.git
cd dbn-sim-learning
```

This repository includes a git submodule under `MQTT_MMS_Medium/`, which contains the OMNeT++ simulation model executed by the experiments.

If you did not clone with submodules, initialize them with:

```bash
git submodule update --init --recursive
```

### 2) Add your `pysmile_license.py`

You need a BayesFusion SMILE/pysmile Academic license.

- Retrieve your license from [BayesFusion support pages](https://download.bayesfusion.com/files.html?category=Academia) (Academic program) and insert the `pysmile_license.py` file in the repository root.

Note: `pysmile_license.py` is intentionally ignored by git via `.gitignore`.

### 3) Build the container

Using the helper script:

```bash
./buildContainer.sh
```

Or manually:

```bash
sudo docker buildx build --progress=plain -t omnet ./docker/
```

> [!WARNING]  
> A stable internet connection is required during the build process to download the OMNeT++ source and all other dependencies. The build process may take around 5-10 minutes depending on your connection speed and host performance.

### 4) Run the container (with shared output folders)

Using the helper script:

```bash
./runContainer.sh
```

Or manually (shares `plots/`, `results/`, `traces/` on the host):

```bash
mkdir -p dbn-sim-learning-container/{plots,results,traces}

sudo docker run --rm -it \
	-v "$PWD/pysmile_license.py":/home/simulation/dbn-sim-learning/pysmile_license.py:ro \
	-v "$PWD/dbn-sim-learning-container/plots":/home/simulation/dbn-sim-learning/plots \
	-v "$PWD/dbn-sim-learning-container/results":/home/simulation/dbn-sim-learning/results \
	-v "$PWD/dbn-sim-learning-container/traces":/home/simulation/dbn-sim-learning/traces \
	omnet
```

### 5) Replicate the full pipeline inside the container

From `/home/simulation/dbn-sim-learning` (container workdir), run:

```bash
python3 replicate_results.py -r 1000 -p "$(nproc)"
```

This will:
- run the simulator batch (with resource monitoring)
- run `parameterizer.py` in normal and benchmark mode
- run `data_evaluator.py`
- run `experiment_analyzer.py` in normal and benchmark mode
- run `validator_playground.py`
- print the total wall-clock time at the end

## Additional information on the scripts

This repository is currently organized around a small set of Python entrypoints in the repository root.
When running via Docker, outputs inside the container are written to `plots/`, `results/`, and `traces/` and are bind-mounted to the host under `dbn-sim-learning-container/{plots,results,traces}` (see the `docker/` folder and `runContainer.sh`).

### Full pipeline orchestrator

Run:

```bash
python3 replicate_results.py -r 1000 -p "$(nproc)"
```

`replicate_results.py` runs the whole pipeline in sequence:

1. `runSimulation.py` (simulation batch + resource monitoring)
2. `parameterizer.py` (single learning run)
3. `parameterizer.py --bench` (parameter-learning benchmark)
4. `data_evaluator.py` (trace distribution + entropy)
5. `experiment_analyzer.py` (inference plots)
6. `experiment_analyzer.py --bench` (inference benchmark)
7. `validator_playground.py` (k-fold validation vs evidence frequency)

It also ensures `plots/`, `results/`, and `traces/` exist before starting.

### Simulation + trace aggregation (`runSimulation.py`)

Run:

```bash
python3 runSimulation.py -r 1000 -p 30
```

It is designed to run inside the container where OMNeT++ is installed.
It launches multiple OMNeT++ runs in parallel and monitors per-run wall-clock time and peak RSS (requires `psutil`).
After all runs complete, it calls the simulator's `aggregator.sh` to produce the aggregated trace CSV.

Main outputs:
- `results/logger.log`: simulator + aggregation logs
- `results/simulation_resources.csv`: per-run wall-clock and peak RSS
- `results/simulation_resources_summary.csv`: mean/std of wall-clock and peak RSS
- `results/dbnLogs.csv` and `traces/dbnLogs.csv`: aggregated traces used by the learning/analysis scripts

### Parameter learning (`parameterizer.py`)

Defaults (edit at the top of the script if you need to change them):
- Input model: `models/DBNfromAG.xdsl`
- Output model: `models/DBNfromAG_learned.xdsl`
- Traces: `traces/dbnLogs.csv`
- Slices: `numSlices = 100`

Run a single learning pass:

```bash
python3 parameterizer.py
```

Run the benchmark (repeats learning multiple times and records time/RAM via `tracemalloc`):

```bash
python3 parameterizer.py --bench
```

Benchmark outputs:
- `results/parameter_learning_benchmark.csv`
- `results/parameter_learning_benchmark_aggregated.csv`

### Inference experiments + benchmark (`experiment_analyzer.py`)

This script loads `models/DBNfromAG_learned.xdsl` and runs the experiments defined in-code (currently an example with the single experiment named `No evidence`).
By default it uses EPIS sampling (`algoTypeExact = False`); set `algoTypeExact = True` for the exact Lauritzen algorithm.

Run inference + generate the posterior plot:

```bash
python3 experiment_analyzer.py
```

Output:
- `plots/No evidence_targetNodes_Completed.pdf`

Run the inference benchmark (repeat runs + aggregate avg/std time and peak RAM):

```bash
python3 experiment_analyzer.py --bench
```

Benchmark output:
- `results/benchmark_inference_times.csv`

### Validation vs evidence frequency (`validator_playground.py`, `validator.py`)

`validator.py` contains the `Validator` class implementing 5-fold CV over the trace dataset.
`validator_playground.py` wires it together for the experiment used in this project:
- uses `models/DBNfromAG_learned.xdsl`
- performs 5-folds CV on `traces/dbnLogs.csv` varying the  evidence frequency via `ext_ev_every_n_slices = [1, 2, 5, 10]`

Run validation (computes and stores CSVs):

```bash
python3 validator_playground.py
```

Load already-computed CSVs and only re-generate the plot:

```bash
python3 validator_playground.py --stored
```

Outputs:
- `results/5_folds-evEveryNSlices_*.csv`
- `results/5_folds-full_results.csv`
- `plots/validation_metrics_vs_evEveryNSlices.pdf`

### Trace distribution analysis (`data_evaluator.py`)

This script analyzes `traces/dbnLogs.csv` to:
- plot completion-slice histograms for selected target nodes
- compute per-node entropy of completion-slice distributions and export them to CSV

Run:

```bash
python3 data_evaluator.py
```

Outputs:
- `plots/completion_slice_distribution.pdf`
- `results/node_entropy_values.csv`