import pandas as pd
import os
import glob

def label_attack_traffic(data_dir, attack_start, attack_end):
    """
    Label packets during attack window as malicious (label=1)
    """
    files = glob.glob(f"{data_dir}/traffic_log_*.csv")
    
    for f in files:
        df = pd.read_csv(f)
        if df.empty:
            continue

        # Label packets in attack time window as 1
        df['label'] = df['timestamp'].apply(
            lambda t: 1 if attack_start <= float(t) <= attack_end else 0
        )

        df.to_csv(f, index=False)
        attack_count = df[df['label']==1].shape[0]
        normal_count = df[df['label']==0].shape[0]
        print(f"[+] Labeled {f}")
        print(f"    Normal packets : {normal_count}")
        print(f"    Attack packets : {attack_count}")

if __name__ == "__main__":
    import time
    data_dir = os.path.expanduser("~/loft_project/data")
    
    # Set your attack window here (unix timestamps)
    attack_start = float(input("Enter attack START timestamp: "))
    attack_end = float(input("Enter attack END timestamp: "))
    
    label_attack_traffic(data_dir, attack_start, attack_end)
    print("[+] Labeling complete!")
