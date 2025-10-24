# %%
import pysmile
import pysmile_license
from pathlib import Path
from pysmile.learning import DataSet, EM
import itertools
import numpy as np

# %%
fileName = "DBNfromAG.xdsl"
outFileName = "DBNfromAG_learned.xdsl"
tracesFileName = "dbnLogs.csv"
numSlices = 100

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
    ds.read_file(fileName)
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
learnParams(net, tracesFileName, randomize=False, uniformize=True, relevance=False)

# %%
fixDiscrParams(net, None, analyticsDict, orNodes, andNodes)

# %%
net.write_file(outFileName)

# %%
plotDefinitions(net)


