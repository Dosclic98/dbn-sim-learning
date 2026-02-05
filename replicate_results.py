#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence


def runCommand(stepName: str, command: List[str], cwd: Optional[Path] = None) -> float:
    print(f"\n=== {stepName} ===")
    print("$ " + " ".join(command))
    start = time.monotonic()
    completed = subprocess.run(command, cwd=str(cwd) if cwd else None)
    elapsed = time.monotonic() - start
    if completed.returncode != 0:
        raise SystemExit(f"Step '{stepName}' failed with exit code {completed.returncode}")
    print(f"{stepName} completed in {elapsed:.2f} s")
    return elapsed


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replicate the full pipeline inside the container: run simulation, parameterizer (normal+bench), "
            "data evaluator, experiment analyzer (normal+bench), and validator playground."
        )
    )
    parser.add_argument(
        "-r",
        type=int,
        default=1000,
        help="Number of simulation runs (passed to runSimulation.py). Default: 1000",
    )
    parser.add_argument(
        "-p",
        type=int,
        default=4,
        help="Simulation parallelism (passed to runSimulation.py). Default: 4",
    )

    args = parser.parse_args(argv)

    if args.r <= 0:
        print("-r must be > 0", file=sys.stderr)
        return 2
    if args.p <= 0:
        print("-p must be > 0", file=sys.stderr)
        return 2

    repoDir = Path(__file__).resolve().parent

    # Ensure common output dirs exist (some scripts assume they do)
    (repoDir / "results").mkdir(parents=True, exist_ok=True)
    (repoDir / "plots").mkdir(parents=True, exist_ok=True)
    (repoDir / "traces").mkdir(parents=True, exist_ok=True)

    pythonExe = sys.executable or "python3"

    totalStart = time.monotonic()
    try:
        runCommand(
            "Simulation",
            [pythonExe, "runSimulation.py", "-r", str(args.r), "-p", str(args.p)],
            cwd=repoDir,
        )
        runCommand("Parameterizer (normal)", [pythonExe, "parameterizer.py"], cwd=repoDir)
        runCommand(
            "Parameterizer (benchmark)",
            [pythonExe, "parameterizer.py", "--bench"],
            cwd=repoDir,
        )
        runCommand("Data evaluator", [pythonExe, "data_evaluator.py"], cwd=repoDir)
        runCommand(
            "Experiment analyzer (normal)",
            [pythonExe, "experiment_analyzer.py"],
            cwd=repoDir,
        )
        runCommand(
            "Experiment analyzer (benchmark)",
            [pythonExe, "experiment_analyzer.py", "--bench"],
            cwd=repoDir,
        )
        runCommand("Validator playground", [pythonExe, "validator_playground.py"], cwd=repoDir)
    finally:
        totalElapsed = time.monotonic() - totalStart
        print(f"\nTOTAL TIME: {totalElapsed:.2f} s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
