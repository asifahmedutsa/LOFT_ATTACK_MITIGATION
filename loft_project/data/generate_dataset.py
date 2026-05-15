import pandas as pd
import numpy as np
import random
import time
import os

random.seed(42)
np.random.seed(42)

print("[*] Generating labeled LOFT attack dataset...")

records = []

# --- Generate NORMAL traffic (label=0) ---
print("[*] Generating normal traffic samples...")
base_time = time.time()
normal_macs = [
    ("00:00:00:00:00:01", "00:00:00:00:00:02"),
    ("00:00:00:00:00:03", "00:00:00:00:00:04"),
    ("00:00:00:00:00:05", "00:00:00:00:00:06"),
]
normal_ips = [
    ("10.0.1.1", "10.0.1.2"),
    ("10.0.2.1", "10.0.2.2"),
    ("10.0.3.1", "10.0.3.2"),
]
common_ports = [80, 443, 22, 53, 8080]

for i in range(1500):
    pair = i % 3
    src_mac, dst_mac = normal_macs[pair]
    src_ip, dst_ip = normal_ips[pair]
    records.append({
        'timestamp': base_time + i * 0.1,
        'src_mac': src_mac,
        'dst_mac': dst_mac,
        'eth_type': 2048,
        'src_ip': src_ip,
        'dst_ip': dst_ip,
        'protocol': 6,
        'src_port': 12345,
        'dst_port': common_ports[i % len(common_ports)],
        'label': 0
    })

# --- Generate ATTACK traffic (label=1) ---
print("[*] Generating LOFT attack samples...")
attack_start = base_time + 200

for i in range(1500):
    src_ip = f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
    src_port = random.randint(1024, 65535)
    dst_port = random.randint(1, 1024)
    records.append({
        'timestamp': attack_start + i * 0.01,
        'src_mac': f"{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}",
        'dst_mac': "00:00:00:00:00:01",
        'eth_type': 2048,
        'src_ip': src_ip,
        'dst_ip': "10.0.1.1",
        'protocol': 6,
        'src_port': src_port,
        'dst_port': dst_port,
        'label': 1
    })

# Shuffle and save
df = pd.DataFrame(records)
df = df.sample(frac=1).reset_index(drop=True)

out = os.path.expanduser("~/loft_project/data/full_dataset.csv")
df.to_csv(out, index=False)

print(f"\n[+] Dataset saved to {out}")
print(f"    Total samples  : {len(df)}")
print(f"    Normal (0)     : {len(df[df['label']==0])}")
print(f"    Attack (1)     : {len(df[df['label']==1])}")
print(f"    Features       : {list(df.columns)}")