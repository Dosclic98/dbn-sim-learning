from typing import List, Tuple
from pysmile import Network
from pysmile.learning import DataSet, EM, DataMatch
import pandas as pd
import numpy as np

class Validator:

    def __init__(self, net: Network, fileName: str, fixedNodes: List[str] | List[int] | None,  evEveryN: int = 1):
        self.net: Network = net
        self.fileName = fileName
        self.classNodes: set[str] = set()
        self.fixedNodes: List[str] | List[int] | None = fixedNodes 
        self.evEveryN = evEveryN

    def get_ev_every_n_slices(self) -> int:
        return self.evEveryN
    
    def set_ev_every_n_slices(self, n: int) -> None:
        if n < 1:
            raise Exception("evEveryNSlices must be at least 1")
        self.evEveryN = n

    def addClassNode(self, classNode: str):
        self.classNodes.add(classNode)

    def kFold(self, nFolds: int = 5) -> pd.DataFrame:
        em = EM()
        em.set_uniformize_parameters(True)
        em.set_randomize_parameters(False)
        em.set_seed(98)
        df = pd.read_csv(self.fileName)
        if nFolds < 0 or nFolds > len(df):
            raise Exception("Invalid number of folds specified")

        accVec, precVec, recallVec, f1Vec, mccVec = [], [], [], [], []
        for i in range(0, nFolds):
            acc, prec, recall, f1 = 0.0, 0.0, 0.0, 0.0
            train, test = self._getSplit(df, i, nFolds)
            ds = DataSet()
            ds.read_pandas_dataframe(train)
            matching: List[DataMatch] = ds.match_network(self.net)
            em.learn(ds, self.net, matching, self.fixedNodes)
            acc, prec, recall, f1, mcc = self._test(test)
            accVec.append(acc)
            precVec.append(prec)
            recallVec.append(recall)
            f1Vec.append(f1)
            mccVec.append(mcc)
            print(f"Fold {i + 1}/{nFolds} -- Accuracy: {acc:.4f}, Precision: {prec:.4f}, Recall: {recall:.4f}, F1-score: {f1:.4f}, MCC: {mcc:.4f}")
        print(f"Average Accuracy: {np.mean(accVec):.4f} ± {np.std(accVec):.4f}")
        print(f"Average Precision: {np.mean(precVec):.4f} ± {np.std(precVec):.4f}")
        print(f"Average Recall: {np.mean(recallVec):.4f} ± {np.std(recallVec):.4f}")
        print(f"Average F1-score: {np.mean(f1Vec):.4f} ± {np.std(f1Vec):.4f}")
        print(f"Average MCC: {np.mean(mccVec):.4f} ± {np.std(mccVec):.4f}")
        
        return pd.DataFrame({
            "nFolds": [nFolds],
            "evEveryN": [self.evEveryN],
            "Mean-Accuracy": [np.mean(accVec)],
            "Std-Accuracy": [np.std(accVec)],
            "Mean-Precision": [np.mean(precVec)],
            "Std-Precision": [np.std(precVec)],
            "Mean-Recall": [np.mean(recallVec)],
            "Std-Recall": [np.std(recallVec)],
            "Mean-F1-score": [np.mean(f1Vec)],
            "Std-F1-score": [np.std(f1Vec)],
            "Mean-MCC": [np.mean(mccVec)],
            "Std-MCC": [np.std(mccVec)],
        })

    # Returns accuracy, precision, recall, F1-score-micro of the evaluated fold
    def _test(self, test: pd.DataFrame) -> Tuple[float, float, float, float, float]:
        numSlices = self.net.get_slice_count()
        nodeIds = self.net.get_all_node_ids()
        totalTP, totalFP, totalTN, totalFN = 0, 0, 0, 0
        for i in range(0, len(test)):
            # Setting the temporal evidence for non-class nodes
            for nodeId in nodeIds:
                if nodeId not in self.classNodes:
                    for j in range(0, numSlices):
                        if j % self.evEveryN == 0:
                            if j == 0:
                                self.net.set_temporal_evidence(nodeId, j, test.iloc[i][f"{nodeId}"])
                            else:
                                self.net.set_temporal_evidence(nodeId, j, test.iloc[i][f"{nodeId}_{j}"])
            # Get the results for the current evidence stream and compare it to the groundtruth (compute the confusion matrix)
            self.net.update_beliefs()
            for nodeId in self.classNodes:
                outcomes = self.net.get_outcome_ids(nodeId)
                vals = self.net.get_node_value(nodeId)
                numOutcomes = len(outcomes)
                for k in range(0, numSlices):
                     # Prediction by argmax for this slice
                    offs = k * numOutcomes
                    probs = vals[offs:offs + numOutcomes]
                    pred_idx = int(np.argmax(probs))
                    prediction = outcomes[pred_idx]
                    # Check if the prediction was right or wrong
                    # Ground truth column
                    col = f"{nodeId}" if k == 0 else f"{nodeId}_{k}"
                    groundTruth: str = test.iloc[i][f"{col}"]
                    if prediction == groundTruth:
                        if prediction == "C":
                            totalTP += 1
                        else:
                            totalTN += 1
                    else:
                        if prediction == "N":
                            totalFN += 1
                        else:
                            totalFP += 1

            # Compute balanced accuracy, precision, recall, and F1-score-micro
            self.net.clear_all_evidence()
        accuracy = (totalTP + totalTN) / (totalTP + totalTN + totalFP + totalFN) if (totalTP + totalTN + totalFP + totalFN) > 0 else 0
        precision = totalTP / (totalTP + totalFP) if (totalTP + totalFP) > 0 else 0
        recall = totalTP / (totalTP + totalFN) if (totalTP + totalFN) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        mcc = ((totalTP * totalTN) - (totalFP * totalFN)) / np.sqrt((totalTP + totalFP) * (totalTP + totalFN) * (totalTN + totalFP) * (totalTN + totalFN)) if (totalTP + totalFP) > 0 and (totalTP + totalFN) > 0 and (totalTN + totalFP) > 0 and (totalTN + totalFN) > 0 else 0
        return accuracy, precision, recall, f1_score, mcc

    
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

        

        