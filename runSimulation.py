#!/usr/bin/env python3

import argparse
import csv
import os
import shutil
import signal
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None


OMNET_N_PATH = (
    ".:../src:../../inet4.5/examples:../../inet4.5/showcases:../../inet4.5/src:"
    "../../inet4.5/tests/validation:../../inet4.5/tests/networks:../../inet4.5/tutorials:"
    "../../simu5g/emulation:../../simu5g/simulations:../../simu5g/src"
)

OMNET_X_EXCLUDES = (
    "inet.common.selfdoc;inet.linklayer.configurator.gatescheduling.z3;inet.emulation;"
    "inet.showcases.visualizer.osg;inet.examples.emulation;inet.showcases.emulation;"
    "inet.transportlayer.tcp_lwip;inet.applications.voipstream;inet.visualizer.osg;"
    "inet.examples.voipstream;simu5g.simulations.LTE.cars;simu5g.simulations.NR.cars;"
    "simu5g.nodes.cars"
)

OMNET_IMAGE_PATH = "../../inet4.5/images:../../simu5g/images"

# Hardcoded paths to mirror runSimulation.sh
OMNET_SETENV_PATH = "~/omnetpp/setenv"
SIMULATIONS_DIR = "~/omnetpp-projects/MQTT_MMS_Medium/simulations"
LOGS_DIR = "~/omnetpp-projects/MQTT_MMS_Medium/simulations/logs"
FILE_NAME_PREFIX = "dbnLogs"
POLL_INTERVAL_S = 0.1


@dataclass
class RunMetrics:
    runId: int
    pid: int
    startTs: float
    endTs: Optional[float] = None
    wallclockS: Optional[float] = None
    maxRssMb: float = 0.0
    exitCode: Optional[int] = None


def expandPath(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path))).resolve()


def safeMean(values: Sequence[float]) -> float:
    return float(statistics.mean(values)) if values else float("nan")


def safeStdev(values: Sequence[float]) -> float:
    if not values:
        return float("nan")
    if len(values) == 1:
        return 0.0
    return float(statistics.stdev(values))


def rssMbForPid(pid: int) -> float:
    if psutil is None:
        raise RuntimeError(
            "psutil is required for RAM monitoring. Install it with: pip install psutil"
        )

    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return 0.0

    totalRss = 0
    try:
        with proc.oneshot():
            procs = [proc]
            try:
                procs.extend(proc.children(recursive=True))
            except psutil.Error:
                pass

        for p in procs:
            try:
                totalRss += p.memory_info().rss
            except psutil.Error:
                continue
    except psutil.Error:
        return 0.0

    return totalRss / (1024 * 1024)


def buildSimCommand(runId: int) -> List[str]:
    return [
        "../MQTT_MMS_Medium",
        "-r",
        str(runId),
        "-m",
        "-u",
        "Cmdenv",
        "-n",
        OMNET_N_PATH,
        "-x",
        OMNET_X_EXCLUDES,
        f"--image-path={OMNET_IMAGE_PATH}",
        "omnetpp_new.ini",
    ]


def startRun(
    runId: int,
    simulationsDir: Path,
    omnetSetenv: Path,
    logFile,
) -> subprocess.Popen:
    cmd = buildSimCommand(runId)

    # Match runSimulation.sh behavior: source OMNeT++ env then run.
    # Use exec so the PID we monitor is the launched process group leader.
    bashCmd = (
        f"source {shlexQuote(str(omnetSetenv))} && "
        f"cd {shlexQuote(str(simulationsDir))} && "
        + "exec "
        + " ".join(shlexQuote(part) for part in cmd)
    )

    return subprocess.Popen(
        ["bash", "-lc", bashCmd],
        stdout=logFile,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def shlexQuote(s: str) -> str:
    # Minimal, dependency-free quoting for bash -lc.
    # Uses single-quote strategy: ' -> '\''
    return "'" + s.replace("'", "'\\''") + "'"


def terminateProcessTree(pid: int, graceS: float = 5.0) -> None:
    if psutil is None:
        try:
            os.killpg(pid, signal.SIGTERM)
        except Exception:
            return
        return

    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    procs = [root]
    try:
        procs.extend(root.children(recursive=True))
    except psutil.Error:
        pass

    for p in procs:
        try:
            p.terminate()
        except psutil.Error:
            pass

    gone, alive = psutil.wait_procs(procs, timeout=graceS)
    _ = gone
    for p in alive:
        try:
            p.kill()
        except psutil.Error:
            pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Python equivalent of runSimulation.sh with per-run peak RAM (MB) and wall-clock time monitoring. "
            "Only -r (runs) and -p (parallelism) are accepted; other paths are hardcoded to match the bash script."
        )
    )
    parser.add_argument("-r", type=int, required=True, help="Number of runs")
    parser.add_argument(
        "-p",
        type=int,
        required=True,
        help="Maximum number of concurrent runs (parallelism)",
    )

    args = parser.parse_args(argv)

    numRuns = int(args.r)
    parallelism = int(args.p)

    if numRuns <= 0:
        print("-r must be > 0", file=sys.stderr)
        return 1
    if parallelism <= 0:
        print("-p must be > 0", file=sys.stderr)
        return 1
    if psutil is None:
        print(
            "ERROR: psutil is not installed; needed for max RAM monitoring. Install with: pip install psutil",
            file=sys.stderr,
        )
        return 2

    omnetSetenv = expandPath(OMNET_SETENV_PATH)
    simulationsDir = expandPath(SIMULATIONS_DIR)
    logsDir = expandPath(LOGS_DIR)
    resultsDir = (Path(__file__).resolve().parent / "results").resolve()
    resultsDir.mkdir(parents=True, exist_ok=True)

    loggerPath = resultsDir / "logger.log"

    perRunCsv = resultsDir / f"simulation_resources.csv"
    summaryCsv = resultsDir / f"simulation_resources_summary.csv"

    print("Simulation runs started: see output in the 'logger.log' file")
    print("Running...")

    running: Dict[int, subprocess.Popen] = {}
    metrics: Dict[int, RunMetrics] = {}

    loggerPath.parent.mkdir(parents=True, exist_ok=True)
    with open(loggerPath, "a", encoding="utf-8") as logFile:
        try:
            nextRunId = 0
            while nextRunId < numRuns or running:
                # Start new runs up to parallelism
                while nextRunId < numRuns and len(running) < parallelism:
                    proc = startRun(
                        runId=nextRunId,
                        simulationsDir=simulationsDir,
                        omnetSetenv=omnetSetenv,
                        logFile=logFile,
                    )
                    running[nextRunId] = proc
                    metrics[nextRunId] = RunMetrics(
                        runId=nextRunId,
                        pid=proc.pid,
                        startTs=time.monotonic(),
                    )
                    print(f"Started run {nextRunId} (pid={proc.pid})")
                    nextRunId += 1

                # Poll metrics / completions
                finishedRunIds: List[int] = []
                for runId, proc in list(running.items()):
                    m = metrics[runId]
                    try:
                        rssMb = rssMbForPid(proc.pid)
                        if rssMb > m.maxRssMb:
                            m.maxRssMb = rssMb
                    except Exception:
                        # If process is gone between checks, ignore; we'll finalize below.
                        pass

                    rc = proc.poll()
                    if rc is not None:
                        m.exitCode = rc
                        m.endTs = time.monotonic()
                        m.wallclockS = m.endTs - m.startTs
                        finishedRunIds.append(runId)

                for runId in finishedRunIds:
                    running.pop(runId, None)

                time.sleep(max(0.01, float(POLL_INTERVAL_S)))

        except KeyboardInterrupt:
            print("Interrupted: terminating active runs...", file=sys.stderr)
            for proc in running.values():
                try:
                    terminateProcessTree(proc.pid)
                except Exception:
                    pass
            return 130

    print("Simulation runs terminated")
    print("Aggregating DBN traces...")

    # Run aggregator.sh as in runSimulation.sh
    aggregatorCmd = [
        str(simulationsDir / "./aggregator.sh"),
        "-p",
        str(logsDir),
        "-f",
        str(FILE_NAME_PREFIX),
        "-n",
        str(numRuns),
    ]

    with open(loggerPath, "a", encoding="utf-8") as logFile:
        agg = subprocess.run(
            aggregatorCmd,
            cwd=str(simulationsDir),
            stdout=logFile,
            stderr=subprocess.STDOUT,
        )
    if agg.returncode != 0:
        print("Error aggregating traces: see logger.log for more info", file=sys.stderr)
        return 3

    # Copy aggregated CSV to results directory
    aggregatedCsv = logsDir / f"{FILE_NAME_PREFIX}.csv"
    if aggregatedCsv.exists():
        shutil.copy2(aggregatedCsv, resultsDir / aggregatedCsv.name)
        print(f"Copying results to {resultsDir}")

        tracesDir = expandPath("~/dbn-sim-learning/traces")
        tracesDir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(aggregatedCsv, tracesDir / aggregatedCsv.name)
        print(f"Copying traces to {tracesDir}")

    # Write per-run and summary reports
    rows = [metrics[i] for i in sorted(metrics.keys())]
    with open(perRunCsv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "pid", "exit_code", "wallclock_s", "max_rss_mb"])
        for r in rows:
            w.writerow(
                [
                    r.runId,
                    r.pid,
                    r.exitCode,
                    f"{(r.wallclockS or 0.0):.6f}",
                    f"{r.maxRssMb:.3f}",
                ]
            )

    okRows = [r for r in rows if r.exitCode == 0 and r.wallclockS is not None]
    wall = [float(r.wallclockS) for r in okRows]
    ram = [float(r.maxRssMb) for r in okRows]

    with open(summaryCsv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["runs_requested", numRuns])
        w.writerow(["runs_successful", len(okRows)])
        w.writerow(["wallclock_s_mean", f"{safeMean(wall):.6f}"])
        w.writerow(["wallclock_s_stdev", f"{safeStdev(wall):.6f}"])
        w.writerow(["max_rss_mb_mean", f"{safeMean(ram):.3f}"])
        w.writerow(["max_rss_mb_stdev", f"{safeStdev(ram):.3f}"])

    print("Simulation completed successfully!")
    print(f"Resource report (per-run): {perRunCsv}")
    print(f"Resource report (summary): {summaryCsv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
