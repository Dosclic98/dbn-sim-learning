# %%
import pysmile
import pysmile_license
import argparse
from pathlib import Path
from pysmile.learning import DataSet, EM
import itertools
from expdef import Experiment, Analytic, Result
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import time
import tracemalloc

from seeding import seed_pysmile_network, set_global_seed

# Enable layex backend for matplotlib
plt.rcParams['text.usetex'] = True
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 12  

set_global_seed()

# %%
fileName = "models/DBNfromAG_learned.xdsl"
numSlices = 100

algoTypeExact = False

parser = argparse.ArgumentParser(description="Run DBN inference experiments and optionally benchmark inference.")
parser.add_argument("--bench", action="store_true", help="Run in benchmark mode (repeat inference runs and write timing/memory CSV).")
args, _unknownArgs = parser.parse_known_args()

benchmarkInference = bool(args.bench)
numRunsInference = 10

targetNodes = ["DMZ_scanIP", "historian_scanVuln", "tomcatWebServer_bruteForce", "IED1_DERfailure"]
nodeRemap = {
    "DMZ_scanIP": "scanIP",
    "historian_scanVuln": "scanVuln",
    "tomcatWebServer_bruteForce": "bruteForce",
    "IED1_DERfailure": "DERfailure"
}
remappedTargetNodes = list(nodeRemap.values())
print(remappedTargetNodes)
remapOutcomes = ["workStation_compromise", "DMZ_scanIP", "historian_scanVuln", "tomcatWebServer_bruteForce", "IED1_DERfailure"]
outcomesRemap = {
    "N": "Not completed",
    "C": "Completed"
}

resultsVec = [   
        Result("DMZ_scanIP", 0),
        Result("historian_scanVuln", 0),
        Result("tomcatWebServer_bruteForce", 1),
        Result("IED1_DERfailure", 1)
    ]
experiments: list[Experiment] = [
    Experiment("No evidence", [],
        resultsVec
    )
]

# %%
net = pysmile.Network()
net.read_file(fileName)
seed_pysmile_network(net)
if not algoTypeExact:
    # Set default inference algorithm and parameters
    net.set_bayesian_algorithm(pysmile.BayesianAlgorithmType.EPIS_SAMPLING)
    # Print default EPIS algorithm parameters
    episParams = net.get_epis_params()
    print("Propagation length: ", episParams.propagation_length)
    print("Num state small:", episParams.num_state_small)
    print("Num state medium:", episParams.num_state_medium)
    print("Num state big:", episParams.num_state_big)
else:
    net.set_bayesian_algorithm(pysmile.BayesianAlgorithmType.LAURITZEN)

def runExperiments(net: pysmile.Network, experiments: list[Experiment], isBanchmarking: bool = False) -> list[list[pd.DataFrame], list[float], list[float]]:
    results = []
    inferenceTimes = []
    memoryUsages = []
    for exp in experiments:
        net.clear_all_evidence()
        print(f"Running experiment: {exp.name}")
        analytics = exp.analytics
        # Set evidence
        for analytic in analytics:
            print(f"  Setting evidence for node: {analytic.nodeId}")
            if analytic.slices is None:
                # Set static evidence: node_id, outcome_id
                net.set_evidence(analytic.nodeId, analytic.outcomeId)
            else:
                for slice_num in analytic.slices:
                    # Set temporal evidence: node_id, slice, outcome_id
                    net.set_temporal_evidence(analytic.nodeId, slice_num, analytic.outcomeId)
        # Run inference
        startTime = time.time()
        tracemalloc.start()
        net.update_beliefs()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        endTime = time.time()
        memoryUsages.append(peak * 1e-6)  # Convert to MBytes
        inferenceTimes.append(endTime - startTime)
        # Plot results
        resultRows: list[dict] = []
        for result in exp.results:
            print(f"  Result for {result.nodeId}")
            val = net.get_node_value(result.nodeId)
            # Build the results dataframe
            for i in range(numSlices):
                outcomeIds = net.get_outcome_ids(result.nodeId)
                numOutcomes = len(outcomeIds)
                for outcomeId, j in zip(outcomeIds, range(numOutcomes)):
                    if result.nodeId in remapOutcomes:
                        outcomeId = outcomesRemap[outcomeId]
                    resultRows.append({
                        "nodeId": result.nodeId,
                        "slice": i,
                        "outcomeId": outcomeId,
                        "value": val[(i * numOutcomes) + j]
                    })
        resDf = pd.DataFrame.from_records(resultRows, columns=["nodeId", "slice", "outcomeId", "value"])
        results.append(resDf)
    return [results, inferenceTimes, memoryUsages]

def runExperimentsMod(net: pysmile.Network, experiments: list[Experiment]) -> list[pd.DataFrame]:
    results = []
    for exp in experiments:
        net.clear_all_evidence()
        print(f"Running experiment: {exp.name}")
        analytics = exp.analytics
        # Set evidence
        for analytic in analytics:
            print(f"  Setting evidence for node: {analytic.nodeId}")
            if analytic.slices is None:
                # Set static evidence: node_id, outcome_id
                net.set_evidence(analytic.nodeId, analytic.outcomeId)
            else:
                for slice_num in analytic.slices:
                    # Set temporal evidence: node_id, slice, outcome_id
                    net.set_temporal_evidence(analytic.nodeId, slice_num, analytic.outcomeId)
        
        resDf = pd.DataFrame(columns=["nodeId", "slice", "outcomeId", "value"])
        for result in exp.results:
            # Set target nodes
            net.clear_all_targets()
            net.set_target(result.nodeId, True)
            # Run inference
            net.update_beliefs()
            print(f"  Result for {result.nodeId}")
            val = net.get_node_value(result.nodeId)
            # Build the results dataframe
            resDict = {}
            for i in range(numSlices):
                for outcomeId, j in zip(net.get_outcome_ids(result.nodeId), range(len(net.get_outcome_ids(result.nodeId)))):
                    numOutcomes = len(net.get_outcome_ids(result.nodeId))
                    if result.nodeId in remapOutcomes:
                        outcomeId = outcomesRemap[outcomeId]
                    resDict = {
                        "nodeId": result.nodeId,
                        "slice": i,
                        "outcomeId": outcomeId,
                        "value": val[(i * numOutcomes) + j]
                    }
                    resDf = pd.concat([resDf, pd.DataFrame([resDict])], ignore_index=True)
            
        results.append(resDf)
    return results

def runExperimentsFiltering(net: pysmile.Network, experiments: list[Experiment]) -> list[pd.DataFrame]:
    results = []
    for exp in experiments:
        resDf = pd.DataFrame(columns=["nodeId", "slice", "outcomeId", "value"])
        print(f"Running experiment: {exp.name}")
        for i in range(numSlices):
            print(f"Slice: {i}")
            net.clear_all_evidence()
            analytics = exp.analytics
            for analytic in analytics:
                if analytic.slices is None:
                    # Set static evidence: node_id, outcome_id
                    net.set_evidence(analytic.nodeId, analytic.outcomeId)
                else:
                    j = 0
                    while j < len(analytic.slices) and analytic.slices[j] <= i:
                        slice_num = analytic.slices[j]
                        # Set temporal evidence up to the current time slice
                        net.set_temporal_evidence(analytic.nodeId, slice_num, analytic.outcomeId)
                        j += 1
            # Run inference
            net.update_beliefs()
            # Plot results
            for result in exp.results:
                val = net.get_node_value(result.nodeId)
                # Build the results dataframe
                resDict = {}
                for outcomeId, h in zip(net.get_outcome_ids(result.nodeId), range(len(net.get_outcome_ids(result.nodeId)))):
                    numOutcomes = len(net.get_outcome_ids(result.nodeId))
                    if result.nodeId in remapOutcomes:
                        outcomeId = outcomesRemap[outcomeId]
                    resDict = {
                        "nodeId": result.nodeId,
                        "slice": i,
                        "outcomeId": outcomeId,
                        "value": val[(i * numOutcomes) + h]
                    }
                    resDf = pd.concat([resDf, pd.DataFrame([resDict])], ignore_index=True)
        results.append(resDf)
    return results

if not benchmarkInference:
    results = runExperiments(net, experiments)[0]
else:
    perfRows: list[dict] = []
    for runIdx in range(numRunsInference):
        results, times, memoryUsages = runExperiments(net, experiments, isBanchmarking=True)
        for exp, t, m in zip(experiments, times, memoryUsages):
            perfRows.append({
                "Run": runIdx,
                "Experiment": exp.name,
                "InferenceTime": t,
                "PeakMemoryUsageMBytes": m
            })

    perfDf = pd.DataFrame.from_records(perfRows, columns=["Run", "Experiment", "InferenceTime", "PeakMemoryUsageMBytes"])

    aggregatedRows: list[dict] = []
    for exp in experiments:
        expPerfDf = perfDf[perfDf["Experiment"] == exp.name]
        aggregatedRows.append({
            "Runs": numRunsInference,
            "Experiment": exp.name,
            "AvgInferenceTime": expPerfDf["InferenceTime"].mean(),
            "StdInferenceTime": expPerfDf["InferenceTime"].std(),
            "AvgPeakMemoryUsageMBytes": expPerfDf["PeakMemoryUsageMBytes"].mean(),
            "StdPeakMemoryUsageMBytes": expPerfDf["PeakMemoryUsageMBytes"].std()
        })

    aggregatedPerfDf = pd.DataFrame.from_records(
        aggregatedRows,
        columns=[
            "Runs",
            "Experiment",
            "AvgInferenceTime",
            "StdInferenceTime",
            "AvgPeakMemoryUsageMBytes",
            "StdPeakMemoryUsageMBytes",
        ],
    )
    
    aggregatedPerfDf.to_csv("results/benchmark_inference_times.csv", index=False)    

# %%
# Plot Posterior probability for the outcome "Completed" for the nodes in targetNodes
for exp, resDf in zip(experiments, results):
    sns.set_context("notebook", font_scale=2)
    resDf = resDf.copy()
    resDf["nodeId"] = resDf["nodeId"].replace(nodeRemap)
    resDf = resDf.infer_objects(copy=False)
    sns.lineplot(data=resDf[(resDf['outcomeId'] == 'Completed') & (resDf['nodeId'].isin(remappedTargetNodes))], x="slice", y="value", hue="nodeId", palette="deep", 
                 style="nodeId", markers=True, dashes=False, markersize=10, markevery=10)
    #plt.title(f"Posterior Probability of 'Completed' Outcome")
    plt.xlabel("Time slice")
    plt.ylabel("Posterior probability")
    plt.grid(True)
    step = 10
    plt.xticks(range(0, numSlices+step, step))
    plt.yticks([i / 10 for i in range(11)])
    plt.legend(title="Attack steps", bbox_to_anchor=(1.05, 1), loc='upper left')
plt.savefig(f"plots/{exp.name}_targetNodes_Completed.pdf", bbox_inches='tight')


