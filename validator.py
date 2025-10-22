from typing import List, Tuple
from pysmile import Network
from pysmile.learning import DataSet, EM, DataMatch
import pandas as pd

class Validator:

    def __init__(self, net: Network, fileName: str, fixedNodes: List[str] | List[int] | None):
        self.net: Network = net
        self.fileName = fileName
        self.classNodes: set[str] = set()
        self.fixedNodes: List[str] | List[int] | None = fixedNodes 


    def addClassNode(self, classNode: str):
        self.classNodes.add(classNode)

    def kFold(self, nFolds: int = 5):
        em = EM()
        em.set_uniformize_parameters(True)
        em.set_randomize_parameters(False)
        em.set_seed(98)
        df = pd.read_csv(self.fileName)
        if nFolds < 0 or nFolds > len(df):
            raise Exception("Invalid number of folds specified")

        for i in range(0, nFolds):
            train, test = self._getSplit(df, i, nFolds)
            ds = DataSet()
            ds.read_pandas_dataframe(train)
            matching: List[DataMatch] = ds.match_network(self.net)
            em.learn(ds, self.net, matching, self.fixedNodes)
            self._test(test)

    def _test(self, test: pd.DataFrame):
        numSlices = self.net.get_slice_count()
        nodeIds = self.net.get_all_node_ids()
        for i in range(0, len(test)):
            # Setting the temporal evidence for non-class nodes
            for nodeId in nodeIds:
                if nodeId not in self.classNodes:
                    for j in range(0, numSlices):
                        if j == 0:
                            self.net.set_temporal_evidence(nodeId, j, test.iloc[i][f"{nodeId}"])
                        else:
                            self.net.set_temporal_evidence(nodeId, j, test.iloc[i][f"{nodeId}_{j}"])
            # Get the results for the current evidence stream and compare it to the groundtruth (compute the confusion matrix)
            self.net.update_beliefs()
            resDf = pd.DataFrame(columns=["nodeId", "slice", "outcomeId", "value"])
            for nodeId in self.classNodes:
                TP, FP, TN, FN = 0, 0, 0, 0
                val = self.net.get_node_value(nodeId)
                for k in range(0, numSlices):
                    for outcomeId, h in zip(self.net.get_outcome_ids(nodeId), range(len(self.net.get_outcome_ids(nodeId)))):
                        numOutcomes = len(self.net.get_outcome_ids(nodeId))
                        resDict = {
                            "nodeId": nodeId,
                            "slice": k,
                            "outcomeId": outcomeId,
                            "value": val[(k * numOutcomes) + h]
                        }
                        resDf = pd.concat([resDf, pd.DataFrame([resDict])], ignore_index=True)
                    # Check if the prediction was right or wrong
                    if k == 0:
                        groundTruth: str = test.iloc[i][f"{nodeId}"]
                    else:
                        groundTruth: str = test.iloc[i][f"{nodeId}_{k}"]
                    prediction: str = resDf[(resDf["nodeId"] == nodeId) & (resDf["slice"] == k)].sort_values(by="value", ascending=False).iloc[0]["outcomeId"]
                    if prediction == groundTruth:
                        if prediction == "C":
                            TP += 1
                        else:
                            TN += 1
                    else:
                        if prediction == "N":
                            FN += 1
                        else:
                            FP += 1

                print(f"Confusion Matrix for node {nodeId}:\nTP: {TP}, FP: {FP}, TN: {TN}, FN: {FN}")
            self.net.clear_all_evidence()





    
    def _getSplit(self, df: pd.DataFrame, foldNum: int, nFolds: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
        numSamples = len(df)
        foldSize: int = numSamples // nFolds
        start = foldNum * foldSize
        end = numSamples if (start + foldSize) >= numSamples else (start + foldSize)
        test: pd.DataFrame = df.iloc[start:end]
        train: pd.DataFrame = df.drop(test.index)
        test.reset_index(inplace=True)
        train.reset_index(inplace=True)
        return train, test

        

        