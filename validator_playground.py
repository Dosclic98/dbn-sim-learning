import pysmile
import pysmile_license
from validator import Validator
from pathlib import Path
from pysmile.learning import DataSet, EM
import itertools
from expdef import Experiment, Analytic, Result
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import sys

# Enable layex backend for matplotlib
plt.rcParams['text.usetex'] = True
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 12

fileName = "models/DBNfromAG_learned.xdsl"
dataFileName = "traces/dbnLogs.csv"
targetNodes = ["tomcatWebServer_bruteForce", "DMZ_scanIP", "historian_scanVuln", "IED1_DERfailure"]
fixedNodes = ["historianServer_remoteShellAND", "MMSclient1_AND52", "MMSserver1_NodeAND23", "historianServer_NodeOR1"]
numSlices = 100
algoTypeExact = True
ext_ev_every_n_slices = [1,2,5,10]
numFolds = 5
# Read the --stored parameter from command line
stored = False
if '--stored' in sys.argv:
    stored = True

net = pysmile.Network()
net.read_file(fileName)
net.set_slice_count(numSlices)
if not algoTypeExact:
    # Set default inference algorithm and parameters
    net.set_bayesian_algorithm(pysmile.BayesianAlgorithmType.EPIS_SAMPLING)
else:
    net.set_bayesian_algorithm(pysmile.BayesianAlgorithmType.LAURITZEN)

validator: Validator = Validator(net, dataFileName, fixedNodes)
for targetNode in targetNodes:
    validator.addClassNode(targetNode)

if not stored:
    print("Running validation...")
    full_results_df = pd.DataFrame()
    for ev_every_n_slices in ext_ev_every_n_slices:
        print(f"Evaluating with evEveryNSlices = {ev_every_n_slices}")
        validator.set_ev_every_n_slices(ev_every_n_slices)
        results_df = validator.kFold(nFolds=numFolds)
        results_df.to_csv(f"results/{numFolds}_folds-evEveryNSlices_{ev_every_n_slices}.csv", index=False)
        full_results_df = pd.concat([full_results_df, results_df], ignore_index=True)
    full_results_df.to_csv(f"results/{numFolds}_folds-full_results.csv", index=False)
else:
    print("Loading stored results...")
    # Load full results from CSV if needed
    full_results_df = pd.read_csv(f"results/{numFolds}_folds-full_results.csv")

# Plot the full results using a line plot (one line per metric with error bars)
metrics = ['Accuracy', 'F1-score', 'MCC']
metricsStd = [f'Std-Accuracy', f'Std-F1-score', f'Std-MCC']
markers = ['o', 's', '^']  # circle, square, triangle

sns.set_context("notebook", font_scale=1.7)
for metric, metricStd, marker in zip(metrics, metricsStd, markers):
    ax = plt.gca()
    # Set a different marker for each metric
    sns.lineplot(data=full_results_df, x='evEveryN', y=metric, marker=marker, label=metric, markersize=8)
    color = ax.lines[-1].get_color()
    # Add error bars
    plt.errorbar(full_results_df['evEveryN'], full_results_df[metric], yerr=full_results_df[metricStd], fmt='none', capsize=5, ecolor=color, color=color)
plt.title(f'{numFolds}-fold Cross-Validation Metrics vs evidence frequency'.format(numFolds))
plt.xlabel('Evidence frequency (every N slices)')
plt.ylabel('Metric Value')
plt.legend(title='Metrics')
plt.grid(True)
plt.xticks(ext_ev_every_n_slices)
plt.savefig('plots/validation_metrics_vs_evEveryNSlices.pdf', bbox_inches='tight')


