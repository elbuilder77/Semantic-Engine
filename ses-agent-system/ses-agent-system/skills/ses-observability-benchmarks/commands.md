# Commands

## Locate instrumentation and hot paths
```powershell
rg -n "metrics|latency|timer|counter|benchmark|throughput|rerank|search|ingest|rust" ses gateway tests core_rs
```

## Run benchmark or perf-related tests if present
```powershell
pytest -q tests -k "benchmark or metrics or latency or search or rerank or ingest"
```

## Check for benches or scripts
```powershell
rg --files tests core_rs gateway ses | rg "bench|benchmark|perf|profile"
```

## End-to-end metrics

Do not treat `tests/performance/benchmark.py` as an end-to-end service benchmark;
it currently measures synthetic vectors and generated text.

## Mandatory result format
State:
- metric name
- workload/dataset
- command used
- result
- interpretation
- decision implied
