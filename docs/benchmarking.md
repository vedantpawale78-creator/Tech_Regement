# Benchmarking

The benchmark suite (`benchmark.py`) calculates:
- System FPS and Processing Latency (from metrics database).
- Bandwidth reduction percentage (comparing raw video size estimates to semantic JSON alert sizes).
- False alarm rates (Verified vs Suppressed events).

Results are saved to the `results/` directory as JSON and CSV files.
