# dbn-sim-learning
GeNIe-based framework for learning Dynamic Bayesian Network (DBN) parameters from simulated data traces.

## Dependency Installation

1. It is highly advised to create and activate a [Python virtual environment](https://www.w3schools.com/python/python_virtualenv.asp) in which you can install all the necessary dependencies.

2. Install pysmile from the custom index (change `pysmile-A` to `pysmile-B` if you are not using the Academic license):

```bash
python -m pip install --no-cache-dir --index-url https://support.bayesfusion.com/pysmile-A/ pysmile
```

3. Install other dependencies:

```bash
pip install -r requirements.txt
```

## Add your pysmile license

To run the scripts using pysmile, a license file must be provided. Every script expects a `pysmile_license.py` file (in the project root) containing your pysmile license.

## Replicating the results (recommended: Docker)

### Reference host specs (used to obtain the reported results)

Host OS:
- Ubuntu 22.04.5 LTS (Jammy)
- Linux kernel: 5.15.0-164-generic

Host CPU:
- Intel(R) Xeon(R) Gold 6418H
- 2 sockets × 16 cores (32 CPUs visible)

Host RAM:
- 62 GiB (swap: 8 GiB)

Docker:
- Docker Engine: 28.2.2
- buildx: 0.21.3

### 1) Clone the repository locally

```bash
git clone https://github.com/Dosclic98/dbn-sim-learning.git
cd dbn-sim-learning
```

### 2) Add your `pysmile_license.py`

You need a BayesFusion SMILE/pysmile Academic license.

- Retrieve your license from [BayesFusion support pages](https://download.bayesfusion.com/files.html?category=Academia) (Academic program) and create `pysmile_license.py` in the repository root.

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

## How to parameterize the DBN

Run `parameterizer.ipynb` (or the exported `parameterizer.py`) to learn the CPTs of the base DBN model.
The main parameters are:

- `fileName`: The file containing the base DBN model (default: `DBNfromAG.xdsl`).
- `outFileName`: The output file where the parameterized DBN is saved (default: `DBNfromAG_learned.xdsl`).
- `tracesFileName`: The file containing the traces used for parameterization (default: `dbnLogs.csv`; `dbnLogs100.csv` contains only 100 traces).
- `numSlices`: The number of slices to consider (currently up to 100 due to a pysmile limitation).

## How to perform inference on the trained model

After training, use `experimentanalyzer.ipynb` to answer probabilistic queries.

The following parameters can be modified:

- `fileName`: Path to the trained DBN (.xdsl) to load for inference (e.g., `DBNfromAG_learned.xdsl`).
- `numSlices`: Number of time slices to consider in the DBN and to plot on the x‑axis.
- `algoTypeExact`: If `True`, use the exact Lauritzen algorithm; if `False`, use EPIS sampling (EPIS parameters can be tuned via `net.get_epis_params()`).
- `targetNodes`: List of node IDs highlighted in the final “Completed” summary plot.
- `remapOutcomes`: List of node IDs whose outcome labels are remapped for readability.
- `outcomesRemap`: Dict mapping raw outcome IDs to display labels (e.g., `{"N": "Not completed", "C": "Completed"}`).

Currently the provided example experiment does not set any evidence.
The output is a plot showing the posterior probability of the target nodes over time.

## How to validate the model

After learning the CPTs, you can assess the DBN’s performance through k‑fold Cross‑Validation (CV). The dataset is split across `k` equally sized folds; `k−1` folds are used for training and 1 for testing. This is repeated `k` times, rotating the test fold. The performance metrics (Accuracy, F1‑score, and Matthews Correlation Coefficient, MCC) are averaged to obtain the final results.

During testing, nodes chosen as “target nodes” are used to evaluate classification performance, while evidence is set on the remaining nodes. For each test trace, values for non‑target nodes are provided as evidence; values for target nodes are compared with the model prediction (outcome with the highest likelihood) to compute the confusion matrix.

By default, the pysmile validator provides evidence on non‑target nodes at every time slice. In our validator, we study how providing less frequent evidence impacts performance by using a vector parameter with the values of `n` to test. The k‑fold CV is repeated for each `n`.

`validator_playground.ipynb` (or the exported `validator_playground.py`) performs this procedure. Main parameters:

- `fileName`: The file containing the trained DBN.
- `dataFileName`: The file containing the traces used for validation.
- `numSlices`: The number of slices to consider.
- `ext_ev_every_n_slices`: A list of evidence‑frequency values to test (e.g., `[1, 2, 5, 10]` means provide evidence every N slices, with N ranging from 1 to 10).
- `algoTypeExact`: If `True`, use the exact algorithm; otherwise, use EPIS sampling. (Currently, EPIS may struggle to converge when `ext_ev_every_n_slices` includes `10`; results shown use the exact algorithm.)
- `numFolds`: The number of folds in the k‑fold CV.

The output is a plot showing the metrics (mean and standard deviation over folds) versus the evidence frequency.

## How to analyze the data traces distribution

Because the traces are generated by a simulator, one might argue the trained DBN could learn to mimic the simulator rather than generalize the underlying process, especially if traces are very similar. Use `data_evaluator.ipynb` (or `data_evaluator.py`) to analyze the trace distributions.

Main parameters:
- `dataFileName`: The file containing the traces to analyze.
- `targetNodes`: List of node IDs whose completion‑time distribution will be analyzed.
- `numSlices`: The number of slices to consider.

The output is a histogram showing the distribution of completion slices (time slice index) for the specified target nodes. This may differ from completion duration, since it uses the absolute slice where the target node completes.