# %%
import argparse
import pysmile
import pysmile_license
from pathlib import Path
from pysmile.learning import DataSet, EM
import itertools
import numpy as np
import time
import pandas as pd
import tracemalloc


argParser = argparse.ArgumentParser(add_help=True)
argParser.add_argument(
    "--bench",
    action="store_true",
    help="Run in benchmark mode (repeats learning multiple times and writes results/*.csv).",
)
args, _unknownArgs = argParser.parse_known_args()

# %%
fileName = "models/DBNfromAG.xdsl"
outFileName = "models/DBNfromAG_learned.xdsl"
tracesFileName = "traces/dbnLogs.csv"
numSlices = 100

benchmarkLearning = bool(args.bench)
numReps = 10

outcomes = ["N", "C"]
priorNodes = ["workStation_compromise"]

analyticAccuracy = 0.95
analyticNodes = []
analyticsDict = {}
for node in analyticNodes:
    analyticsDict[node] = analyticAccuracy

orNodes = ["historianServer_NodeOR1"]
andNodes = ["historianServer_remoteShellAND", "MMSclient1_AND52", "MMSserver1_NodeAND23"]

# %%
net = pysmile.Network()
net.read_file(fileName)
net.set_slice_count(numSlices)

# %%
def flattenExtended(cpt: list):
    """Flatten a list of lists into a single list."""
    listCpt = []
    for subitem in cpt:
        if isinstance(subitem, list):
            for item in subitem:
                listCpt.append(item)
        else:
            listCpt.append(subitem)
    return listCpt

def plotDefinitions(net: pysmile.Network):
    nodeHandles = net.get_all_nodes()
    nodeIds = net.get_all_node_ids()
    for nodeHandle, nodeId in zip(nodeHandles, nodeIds):
        nodeDef = net.get_node_definition(nodeHandle)
        nodeOutcomes = net.get_outcome_ids(nodeHandle)
        print(f"Node ID: {nodeId}, Definition: {nodeDef}, Outcomes: {nodeOutcomes}")

def learnParams(net: pysmile.Network, fileName: str, randomize: bool = False, uniformize: bool = False, relevance: bool = True):
    ds = DataSet()
    train = pd.read_csv(fileName)
    ds.read_pandas_dataframe(train)
    matching = ds.match_network(net)
    em = EM()
    em.set_seed(98)
    em.set_relevance(relevance)
    em.set_randomize_parameters(randomize)
    em.set_uniformize_parameters(uniformize)
    em.learn(ds, net, matching)

def findNodeHandle(net: pysmile.Network, nodeId: str):
    nodeIds = net.get_all_node_ids()
    nodeHandles = net.get_all_nodes()
    for nodeHandle, id in zip(nodeHandles, nodeIds):
        if id == nodeId:
            return nodeHandle
    return None

def fixDiscrParams(net: pysmile.Network, tacticsDict: dict, analyticsDict: dict, orNodes: list, andNodes: list):
    for nodeId, accuracy in analyticsDict.items():
        nodeHandle = findNodeHandle(net, nodeId)
        if nodeHandle is not None:
            net.set_node_definition(nodeHandle, [accuracy, 1-accuracy, 1-accuracy, accuracy])
            print("Set parameters for analytic node:", nodeId)
        else:
            print(f"Node {nodeId} not found in the network.")

    for nodeId in itertools.chain(orNodes, andNodes):
        nodeHandle = findNodeHandle(net, nodeId)
        if nodeHandle is not None:
            parents = net.get_parents(nodeHandle)
            # Compute all possible combinations of parent outcomes
            numParents = len(parents)
            if numParents > 0:
                parentOutcomes = [net.get_outcome_ids(parent) for parent in parents]
                combinations = [list(comb) for comb in itertools.product(*parentOutcomes)]
                # Set the definition for the OR node based on parent outcomes
                if nodeId in orNodes:
                    nodeDefinition = [[0,1] if outcomes[1] in comb else [1,0] for comb in combinations]
                else:
                    nodeDefinition = [[0,1] if outcomes[0] not in comb else [1,0] for comb in combinations]
                nodeDefinition = [item for sublist in nodeDefinition for item in sublist]
                net.set_node_definition(nodeHandle, nodeDefinition)
        else:
            print(f"Node {nodeId} not found in the network.")

# %%
if benchmarkLearning:
    times = []
    perfDf = pd.DataFrame(columns=["Run", "TimeSeconds", "MemoryPeakBytes"])
    aggrPerfDf = pd.DataFrame(columns=["NumReps", "AvgTimeSeconds", "StdTimeSeconds", "AvgMemoryPeakBytes", "StdMemoryPeakBytes"])
    for rep in range(numReps):
        print(f"--- Benchmarking parameter learning: Run {rep + 1}/{numReps} ---")
        startTime = time.time()
        print("Starting parameter learning at ", time.ctime(startTime))
        tracemalloc.start()
        learnParams(net, tracesFileName, randomize=False, uniformize=True, relevance=False)
        fixDiscrParams(net, None, analyticsDict, orNodes, andNodes)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        endTime = time.time()
        print(f"Parameter learning completed in {endTime - startTime:.2f} seconds.")
        times.append(endTime - startTime)
        perfDf = pd.concat([perfDf, pd.DataFrame({
            "Run": [rep + 1],
            "TimeSeconds": [endTime - startTime],
            "MemoryPeakMBytes": [peak * 1e-6],
        })], ignore_index=True) 
    perfDf.to_csv("results/parameter_learning_benchmark.csv", index=False)
    aggrPerfDf = pd.concat([aggrPerfDf, pd.DataFrame({
        "NumReps": [numReps],
        "AvgTimeSeconds": [np.mean(times)],
        "StdTimeSeconds": [np.std(times)],
        "AvgMemoryPeakMBytes": [perfDf["MemoryPeakMBytes"].mean()],
        "StdMemoryPeakMBytes": [perfDf["MemoryPeakMBytes"].std()],
    })], ignore_index=True)
    aggrPerfDf.to_csv("results/parameter_learning_benchmark_aggregated.csv", index=False)
    print(f"Average parameter learning time over {numReps} runs: {np.mean(times):.2f} ± {np.std(times):.2f} seconds")
    print(f"Average peak memory usage over {numReps} runs: {perfDf['MemoryPeakMBytes'].mean():.2f} ± {perfDf['MemoryPeakMBytes'].std():.2f} MBytes")

else:
    print("--- Performing single parameter learning run ---")
    startTime = time.time()
    print("Starting parameter learning at ", time.ctime(startTime))
    learnParams(net, tracesFileName, randomize=False, uniformize=True, relevance=False)
    fixDiscrParams(net, None, analyticsDict, orNodes, andNodes)
    endTime = time.time()
    print(f"Parameter learning completed in {endTime - startTime:.2f} seconds.")
# %%
net.write_file(outFileName)


