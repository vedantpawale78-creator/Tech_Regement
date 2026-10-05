import os
import json
import csv
from config_loader import load_config
from database import Database
import pandas as pd

def main():
    print("Running Semantic Sentinel Benchmark...")
    os.makedirs('results', exist_ok=True)
    
    config = load_config()
    db = Database(config.get('database', {}).get('path', 'data/sentinel.db'))
    
    # Simulate collecting data from DB
    try:
        metrics_df = pd.read_sql_query("SELECT * FROM system_metrics", db.get_connection())
    except:
        metrics_df = pd.DataFrame()
        
    if metrics_df.empty:
        print("No metrics data found. Run the detector first to generate metrics.")
        latency = "N/A"
        fps = "N/A"
    else:
        latency = metrics_df['processing_latency_ms'].mean()
        fps = metrics_df['fps'].mean()
        
    try:
        alerts_df = pd.read_sql_query("SELECT * FROM alerts", db.get_connection())
    except:
        alerts_df = pd.DataFrame()
        
    alerts_count = len(alerts_df)
    
    # 1. Latency JSON
    latency_data = {
        "avg_processing_latency_ms": latency if isinstance(latency, float) else "N/A",
        "avg_fps": fps if isinstance(fps, float) else "N/A",
        "total_alerts": alerts_count
    }
    with open('results/latency.json', 'w') as f:
        json.dump(latency_data, f, indent=4)
        
    # 2. Bandwidth CSV
    with open('results/bandwidth.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Method", "Data Size (KB)", "Savings %"])
        # Estimates
        raw_size = 15.0 * 1024 # 15 MB
        semantic_size = alerts_count * 0.25 # 250 bytes per alert
        savings = ((raw_size - semantic_size) / raw_size) * 100 if raw_size > 0 else 0
        
        writer.writerow(["Raw Video (1 min est)", raw_size, "0.00%"])
        writer.writerow(["Semantic Alerts", semantic_size, f"{savings:.2f}%"])
        
    # 3. False Alarms CSV
    with open('results/false_alarms.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Total Candidate Events", "Verified Events", "Suppressed Events"])
        if not alerts_df.empty:
            verified = len(alerts_df[alerts_df['verified'] == 1])
            suppressed = len(alerts_df[alerts_df['verified'] == 0])
            writer.writerow([alerts_count, verified, suppressed])
        else:
            writer.writerow([0, 0, 0])
            
    # 4. Quantization CSV (Placeholder/Unmeasured)
    with open('results/quant.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Precision", "mAP", "FPS"])
        writer.writerow(["FP32", "Not benchmarked", "Not benchmarked"])
        writer.writerow(["FP16", "Not benchmarked", "Not benchmarked"])
        writer.writerow(["INT8", "Not benchmarked", "Not benchmarked"])
        
    # 5. Summary MD
    with open('results/summary.md', 'w') as f:
        f.write("# Benchmark Summary\n\n")
        f.write(f"- Avg FPS: {fps if isinstance(fps, float) else 'N/A'}\n")
        f.write(f"- Avg Latency: {latency if isinstance(latency, float) else 'N/A'} ms\n")
        f.write(f"- Total Alerts: {alerts_count}\n")
        
    print("Benchmark results saved to results/")

if __name__ == '__main__':
    main()
