class Analytic:
    def __init__(self, nodeId: str, outcomeId: str, slices: range | None = None):
        self.nodeId = nodeId
        self.slices = slices
        self.outcomeId = outcomeId

class Result:
    def __init__(self, nodeId: str, group: int):
        self.group = group
        self.nodeId = nodeId

class Experiment:
    def __init__(self, name: str, analytics: list[Analytic], results: list[Result]):
        self.name = name
        self.analytics = analytics
        self.results = results