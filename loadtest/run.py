import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path

K6_IMAGE = "grafana/k6:2.3.0"
NAMESPACE = "cinecloud-production"
HOST = "localhost"  # the name the gateway routes to production by
LOADTEST = Path(__file__).resolve().parent
RESULTS = LOADTEST / "results"

STEP = "15s"
PROMETHEUS = {
    "cpu_by_pod": 'sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="cinecloud-production", container!="", container!="POD"}[2m]))',
    "cpu_by_namespace": 'sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="", container!="POD"}[2m]))',
    "throttled_share": 'sum by (pod) (rate(container_cpu_cfs_throttled_periods_total{namespace="cinecloud-production", container="backend"}[2m])) / sum by (pod) (rate(container_cpu_cfs_periods_total{namespace="cinecloud-production", container="backend"}[2m]))',
    "memory_by_pod": 'sum by (pod) (container_memory_working_set_bytes{namespace="cinecloud-production", container="backend"})',
    "ready_pods": 'sum(kube_pod_status_ready{namespace="cinecloud-production", pod=~"backend-.*", condition="true"})',
    "hpa_replicas": 'max by (__name__) ({__name__=~"kube_horizontalpodautoscaler_status_(current|desired)_replicas", namespace="cinecloud-production", horizontalpodautoscaler="backend"})',
    "hpa_utilization": 'max(kube_horizontalpodautoscaler_status_target_metric{namespace="cinecloud-production", horizontalpodautoscaler="backend", metric_target_type="utilization"})',
    "server_requests": 'sum by (handler, status) (rate(http_requests_total{namespace="cinecloud-production"}[1m]))',
    "server_p95_seconds": 'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_highr_seconds_bucket{namespace="cinecloud-production"}[1m])))',
}


def sh(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and result.returncode:
        sys.exit(f"{' '.join(args[:4])} ...: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def kubectl_json(*args: str) -> dict:
    return json.loads(sh("kubectl", "-n", NAMESPACE, *args, "-o", "json"))


def prometheus(path: str, **params: str) -> dict:
    query = urllib.parse.urlencode(params)
    proxy = "/api/v1/namespaces/monitoring/services/monitoring-prometheus:9090/proxy"
    return json.loads(sh("kubectl", "get", "--raw", f"{proxy}/api/v1/{path}?{query}"))["data"]


def log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", flush=True)


def wait_for_steady_state(settle: int) -> dict:
    """Waits until the autoscaler is back at its minimum with every pod ready."""
    while True:
        hpa = kubectl_json("get", "hpa", "backend")
        pods = kubectl_json("get", "pods", "-l", "app.kubernetes.io/name=backend")["items"]
        minimum = hpa["spec"]["minReplicas"]
        current = hpa["status"].get("currentReplicas")
        desired = hpa["status"].get("desiredReplicas")
        ready = sum(
            any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", []))
            for p in pods
        )
        leaving = sum("deletionTimestamp" in p["metadata"] for p in pods)
        if current == desired == minimum == ready == len(pods) and not leaving:
            break
        log(f"waiting for {minimum} idle backend pods: {current} running, {desired} wanted, {ready} ready")
        time.sleep(20)
    log(f"steady at {minimum} pods, settling for {settle} s")
    time.sleep(settle)
    return hpa


def seed_cinema(scenario: str) -> str:
    """A cinema nobody has booked in yet: the same programme the earlier tests had."""
    stamp = datetime.now()
    slug = f"lt-{stamp:%m%d-%H%M%S}-{scenario}"
    exec_backend = ("kubectl", "-n", NAMESPACE, "exec", "deploy/backend", "--", "python", "-m")
    sh(*exec_backend, "scripts.create_tenant", "--name", f"Lasttest {stamp:%d.%m. %H:%M} {scenario}",
       "--slug", slug, "--user-id", str(uuid.uuid4()))
    log(sh(*exec_backend, "scripts.seed_demo", "--slug", slug, "--days", "60"))
    return slug


def gateway_address() -> str:
    """Where a container finds the gateway: on the node, not behind the tunnel of the host."""
    node_port = sh(
        "kubectl", "-n", "envoy-gateway-system", "get", "svc",
        "-l", "gateway.envoyproxy.io/owning-gateway-name=cinecloud,"
              "gateway.envoyproxy.io/owning-gateway-namespace=envoy-gateway-system",
        "-o", "jsonpath={.items[0].spec.ports[?(@.port==80)].nodePort}",
    )
    return f"{sh('minikube', 'ip')}:{node_port}"


def run_k6(run_dir: Path, scenario: str, env: dict[str, str]) -> int:
    scripts = run_dir / "scripts"
    shutil.copytree(LOADTEST, scripts, ignore=shutil.ignore_patterns("results", "*.py", "__pycache__"))
    command = [
        "docker", "run", "--rm", "--network", "minikube",
        "-v", f"{run_dir}:/out", "-v", f"{scripts}:/scripts:ro",
        # Only for the report, not published as a live view: k6 does not exit
        # while a browser is still connected to it.
        "-e", "K6_WEB_DASHBOARD=true", "-e", "K6_WEB_DASHBOARD_EXPORT=/out/report.html",
        *(arg for key, value in env.items() for arg in ("-e", f"{key}={value}")),
        K6_IMAGE, "run", "--quiet",
        "--summary-export", "/out/summary.json",
        "--summary-trend-stats", "avg,min,med,max,p(90),p(95),p(99)",
        "--out", "csv=/out/k6.csv.gz",
        "--tag", f"testid={run_dir.parent.name}/{run_dir.name}",
        f"/scripts/{scenario}.js",
    ]
    with open(run_dir / "k6.txt", "w", encoding="utf-8") as out:
        process = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT)
    return process.returncode


def export_prometheus(run_dir: Path, start: float, end: float) -> None:
    folder = run_dir / "prometheus"
    folder.mkdir()
    for name, query in PROMETHEUS.items():
        series = prometheus("query_range", query=query, start=str(start), end=str(end), step=STEP)["result"]
        columns = {
            ",".join(f"{k}={v}" for k, v in s["metric"].items()) or "value": dict(s["values"])
            for s in series
        }
        times = sorted({t for values in columns.values() for t in values})
        with open(folder / f"{name}.csv", "w", encoding="utf-8") as out:
            out.write(",".join(["time", *(f'"{c}"' for c in columns)]) + "\n")
            for t in times:
                out.write(",".join([f"{t:.0f}", *(columns[c].get(t, "") for c in columns)]) + "\n")


def peak(query: str, start: float, end: float) -> float:
    result = prometheus("query", query=f"max_over_time(({query})[{int(end - start)}s:15s])", time=str(end))["result"]
    return max((float(r["value"][1]) for r in result), default=0.0)


def one_run(series: str, scenario: str, env: dict[str, str], settle: int) -> None:
    folder = RESULTS / series
    number = 1 + sum(1 for d in folder.glob(f"{scenario}-*") if d.is_dir())
    run_dir = folder / f"{scenario}-{number}"
    run_dir.mkdir(parents=True)

    log(f"=== {series}/{run_dir.name}")
    git = {
        "commit": sh("git", "-C", str(LOADTEST), "rev-parse", "--short", "HEAD"),
        "changed": sh("git", "-C", str(LOADTEST), "status", "--porcelain").splitlines(),
    }
    hpa = wait_for_steady_state(settle)
    slug = seed_cinema(scenario)
    time.sleep(30)  # the seeding's own load fades before the measurement

    env = {"BASE_URL": f"http://{HOST}", "HOSTS": json.dumps({HOST: gateway_address()}), "CINEMA": slug, **env}
    log(f"k6 runs {scenario} against {slug}")
    start = time.time()
    exit_code = run_k6(run_dir, scenario, env)
    end = time.time()
    log(f"k6 done after {end - start:.0f} s, exit code {exit_code}")

    time.sleep(45)  # the last scrapes of the run reach Prometheus
    record(run_dir, series, scenario, slug, env, git, hpa, start, end, exit_code)


def record(run_dir: Path, series: str, scenario: str, slug: str, env: dict, git: dict, hpa: dict,
           start: float, end: float, exit_code: int, note: str = "") -> None:
    export_prometheus(run_dir, start - 60, end + 60)

    summary = run_dir / "summary.json"
    metrics = json.loads(summary.read_text(encoding="utf-8"))["metrics"] if summary.exists() else {}
    checks = {
        # an open model only measures the planned load if k6 could start every visitor
        "dropped_iterations": metrics.get("dropped_iterations", {}).get("count", 0),
        # anything besides the app, its gateway and Kubernetes itself that
        # takes the node's CPU distorts the result - Grafana did once
        "max_cores_elsewhere": round(peak(
            'sum(rate(container_cpu_usage_seconds_total{namespace!~"cinecloud-production|envoy-gateway-system|kube-system", container!="", container!="POD"}[2m]))',
            start, end), 2),
        "pods_at_start": hpa["status"]["currentReplicas"],
    }
    deployment = kubectl_json("get", "deploy", "backend")
    meta = {
        "series": series,
        "scenario": scenario,
        "run": run_dir.name,
        "cinema": slug,
        "start": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "end": datetime.fromtimestamp(end, timezone.utc).isoformat(),
        "k6_exit_code": exit_code,  # 0 thresholds met, 99 thresholds crossed
        "note": note,
        "env": {k: v for k, v in env.items() if k not in ("BASE_URL", "HOSTS")},
        "checks": checks,
        "git": git,
        "backend_image": deployment["spec"]["template"]["spec"]["containers"][0]["image"],
        "autoscaler": {k: hpa["spec"][k] for k in ("minReplicas", "maxReplicas", "metrics")},
        "node_cpus": int(sh("docker", "inspect", "minikube", "--format", "{{.HostConfig.NanoCpus}}")) / 1e9,
        "docker_cpus": int(sh("docker", "info", "--format", "{{.NCPU}}")),
        "k6_image": K6_IMAGE,
        "prometheus_step": STEP,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log(f"checks: {checks}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run load tests and keep their results.")
    parser.add_argument("series", help="name of the measurement series, e.g. baseline")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--scenarios", default="rush,ramp", help="comma-separated, run in this order")
    parser.add_argument("--settle", type=int, default=60, help="idle seconds before each run")
    parser.add_argument("--env", action="append", default=[], metavar="KEY=VALUE",
                        help="passed to k6, e.g. PEAK=30")
    args = parser.parse_args()

    env = dict(item.split("=", 1) for item in args.env)
    scenarios = args.scenarios.split(",")
    for _ in range(args.repeat):
        for scenario in scenarios:
            one_run(args.series, scenario, env, args.settle)
    log("series complete")


if __name__ == "__main__":
    main()
