import pandas as pd
import numpy as np
import random
import time
import os

random.seed(42)
np.random.seed(42)

print("[*] Generating FL-DualGuard highly realistic dataset...")

records   = []
base_time = time.time()

common_ports = [80, 443, 22, 53, 8080, 3306, 21, 25, 110, 143]
protocols    = [6, 17, 1]  # TCP, UDP, ICMP
known_macs   = [
    "00:1A:2B:3C:4D:01", "00:0C:29:3B:5C:02",
    "08:00:27:4A:6B:03", "00:50:56:2D:7E:04",
    "00:1B:21:1F:8A:05", "00:25:9C:0E:9B:06",
]

def lan_ip():
    subnet = random.randint(1, 4)
    return f"10.0.{subnet}.{random.randint(1, 254)}"

def random_ip():
    if random.random() < 0.4:
        prefix = random.choice(['10.', '172.16.', '192.168.'])
        if prefix == '10.':
            return f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        elif prefix == '172.16.':
            return f"172.{random.randint(16,31)}.{random.randint(0,255)}.{random.randint(1,254)}"
        else:
            return f"192.168.{random.randint(0,255)}.{random.randint(1,254)}"
    else:
        return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

def random_mac():
    vendors = ['00:1A:2B', '00:0C:29', '08:00:27', '00:50:56', '00:1B:21', '00:25:9C']
    if random.random() < 0.3:
        return random.choice(vendors) + f":{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}"
    else:
        return ":".join(f"{random.randint(0,255):02x}" for _ in range(6))

def ip_entropy(ip):
    parts = [int(x) for x in ip.split('.')]
    return -sum((p/255)*np.log2(p/255+1e-9) for p in parts)

# Define TTL pools
SHARED_TTL = [32, 64, 64, 64, 128, 128, 128, 255]

# ── NORMAL traffic - MORE DIVERSE AND VARIABLE ──────────────────────────
print("  Generating diverse normal traffic (2500 samples)...")
for i in range(2500):
    # Normal traffic with diverse patterns
    src_mac = random.choice(known_macs) if random.random() < 0.6 else random_mac()
    dst_mac = random.choice(known_macs) if random.random() < 0.5 else random_mac()
    
    src_ip = lan_ip() if random.random() < 0.4 else random_ip()
    dst_ip = lan_ip() if random.random() < 0.3 else random_ip()
    
    # Different traffic types
    traffic_type = random.choice(['web', 'dns', 'email', 'streaming', 'chat', 'update', 'scan'])
    
    proto = 6  # Most normal traffic is TCP
    ts = base_time + i * random.uniform(0.01, 0.8)
    
    if traffic_type == 'web':
        dst_port = random.choice([80, 443, 8080, 8443])
        src_port = random.randint(49152, 65535)
        pkt_size = random.choice([64]*3 + [128]*2 + [256]*2 + [512]*2 + [1500]*1)
        ttl = random.choice([64, 64, 128, 255])
        iat = max(0.001, random.expovariate(3.0))
        flow_duration = max(0.1, random.weibullvariate(1.5, 8.0))
        pkts_per_flow = max(1, int(random.gammavariate(2.0, 15.0)))
        flow_table_util = random.betavariate(2.0, 4.0) * 0.7 + 0.1
        new_flow_rate = max(0.1, random.expovariate(0.3))
        
    elif traffic_type == 'dns':
        proto = 17
        dst_port = 53
        src_port = random.randint(49152, 65535)
        pkt_size = random.choice([64, 64, 64, 128, 256, 512])
        ttl = random.choice([64, 128])
        iat = max(0.001, random.expovariate(8.0))
        flow_duration = max(0.001, random.expovariate(5.0))
        pkts_per_flow = max(1, int(random.expovariate(0.5)))
        flow_table_util = random.betavariate(3.0, 6.0) * 0.4 + 0.05
        new_flow_rate = max(0.1, random.expovariate(0.15))
        
    elif traffic_type == 'streaming':
        dst_port = random.choice([443, 8080, 1935, 554])
        src_port = random.randint(49152, 65535)
        pkt_size = 1500
        ttl = random.choice([64, 128])
        iat = max(0.0001, random.expovariate(50.0))
        flow_duration = max(0.1, random.gammavariate(3.0, 20.0))
        pkts_per_flow = max(1, int(random.gammavariate(5.0, 50.0)))
        flow_table_util = random.betavariate(4.0, 2.0) * 0.5 + 0.2
        new_flow_rate = max(0.1, random.expovariate(0.5))
        
    elif traffic_type == 'scan':
        dst_port = random.randint(1, 1024)
        src_port = random.randint(1024, 65535)
        pkt_size = random.choice([64, 128])
        ttl = random.choice(SHARED_TTL)
        iat = max(0.0001, random.expovariate(20.0))
        flow_duration = max(0.001, random.expovariate(2.0))
        pkts_per_flow = max(1, int(random.expovariate(1.0)))
        flow_table_util = random.betavariate(1.5, 3.0) * 0.6 + 0.1
        new_flow_rate = max(0.1, random.expovariate(0.1))
        
    else:  # chat, email, update
        dst_port = random.choice(common_ports)
        src_port = random.randint(49152, 65535)
        pkt_size = random.choice([64, 128, 256, 512, 1024])
        ttl = random.choice([32, 64, 128])
        iat = max(0.001, random.gammavariate(2.0, 0.1))
        flow_duration = max(0.1, random.weibullvariate(2.0, 5.0))
        pkts_per_flow = max(1, int(random.gammavariate(3.0, 10.0)))
        flow_table_util = random.betavariate(2.0, 3.0) * 0.5 + 0.1
        new_flow_rate = max(0.1, random.expovariate(0.4))
    
    bytes_per_flow = pkts_per_flow * pkt_size
    
    # Add noise to make distributions overlap more
    flow_table_util += random.gauss(0, 0.1)
    new_flow_rate += random.gauss(0, 5.0)
    
    # Clip values
    iat = max(0.0001, min(iat, 5.0))
    flow_duration = max(0.0001, min(flow_duration, 120.0))
    pkts_per_flow = max(1, min(pkts_per_flow, 1000))
    bytes_per_flow = max(64, min(bytes_per_flow, 1500000))
    flow_table_util = max(0.01, min(flow_table_util, 1.0))
    new_flow_rate = max(0.1, min(new_flow_rate, 100.0))
    
    # Port entropy based on traffic type
    if traffic_type == 'scan':
        port_entropy = random.betavariate(4.0, 1.5) * 4.0 + 1.0
    else:
        port_entropy = random.betavariate(2.0, 4.0) * 3.0 + 0.1
    
    port_entropy = max(0.1, min(port_entropy, 5.5))
    
    flow_pkt_ratio = (new_flow_rate * flow_duration) / max(pkts_per_flow, 1)
    burst_score = new_flow_rate / max(flow_duration / 10, 0.1)
    e_delta = abs(ip_entropy(src_ip) - ip_entropy(dst_ip))
    
    # Spoofing confidence
    if traffic_type == 'scan':
        spoofing_conf = random.betavariate(1.5, 3.0) * 0.7 + 0.1
    else:
        spoofing_conf = random.betavariate(1.5, 8.0) * 0.3
    
    spoofing_conf = max(0.01, min(spoofing_conf, 1.0))
    
    records.append({
        'timestamp': ts, 'src_mac': src_mac, 'dst_mac': dst_mac,
        'eth_type': 2048, 'protocol': proto,
        'src_ip': src_ip, 'dst_ip': dst_ip,
        'src_port': src_port, 'dst_port': dst_port,
        'pkt_size': pkt_size, 'ttl': ttl,
        'iat': round(iat, 6),
        'flow_duration': round(flow_duration, 6),
        'pkts_per_flow': pkts_per_flow,
        'bytes_per_flow': int(bytes_per_flow),
        'flow_table_util': round(flow_table_util, 6),
        'new_flow_rate': round(new_flow_rate, 6),
        'port_entropy': round(port_entropy, 6),
        'flow_pkt_ratio': round(min(flow_pkt_ratio, 50), 6),
        'burst_score': round(min(burst_score, 100), 6),
        'entropy_delta': round(e_delta, 6),
        'spoofing_conf': round(spoofing_conf, 6),
        'label': 0
    })

# ── ATTACK traffic - SOPHISTICATED LOFT WITH SIGNIFICANT OVERLAP ─────────
print("  Generating sophisticated LOFT attack traffic (1500 samples)...")
attack_start = base_time + 500
victim_ips = ["10.0.1.1", "10.0.2.1", "10.0.3.1", "192.168.1.1", "172.16.0.1"]

# LOFT attack phases
attack_phases = ['slow_scan', 'fast_flood', 'stealth_probe', 'mixed']

for i in range(1500):
    phase = random.choice(attack_phases)
    src_ip = random_ip()
    dst_ip = random.choice(victim_ips)
    proto = random.choice([6, 6, 6, 17])  # Mostly TCP, some UDP
    
    # Sophisticated evasion
    if proto == 6:
        src_port = random.randint(1024, 65535)
        if random.random() < 0.4:
            dst_port = random.choice(common_ports)
        else:
            dst_port = random.randint(1, 65535)
    else:
        src_port = random.randint(1024, 65535)
        dst_port = random.choice([53, 161, 514, 80, 443])
    
    # MAC spoofing with legitimate MACs mixed in
    if random.random() < 0.25:
        src_mac = random.choice(known_macs)
    else:
        src_mac = random_mac()
    
    ts = attack_start + i * random.uniform(0.001, 0.05)
    
    # Packet sizes that match normal traffic patterns
    pkt_size = random.choice([64]*4 + [128]*3 + [256]*2 + [512]*2 + [1024]*1 + [1500]*1)
    ttl = random.choice(SHARED_TTL)
    
    # Attack characteristics based on phase
    if phase == 'slow_scan':
        iat = max(0.001, random.expovariate(15.0))
        flow_duration = max(0.01, random.weibullvariate(1.0, 3.0))
        pkts_per_flow = max(1, int(random.gammavariate(1.5, 5.0)))
        flow_table_util = random.betavariate(3.0, 3.0) * 0.6 + 0.1
        new_flow_rate = max(0.1, random.gammavariate(2.0, 10.0))
        port_entropy = random.betavariate(3.0, 2.0) * 4.0 + 0.5
        
    elif phase == 'fast_flood':
        iat = max(0.0001, random.expovariate(50.0))
        flow_duration = max(0.01, random.weibullvariate(0.8, 2.0))
        pkts_per_flow = max(1, int(random.gammavariate(1.0, 3.0)))
        flow_table_util = random.betavariate(5.0, 1.5) * 0.5 + 0.4
        new_flow_rate = max(10.0, random.gammavariate(3.0, 20.0))
        port_entropy = random.betavariate(4.0, 1.0) * 4.0 + 1.0
        
    elif phase == 'stealth_probe':
        iat = max(0.01, random.gammavariate(2.0, 0.5))
        flow_duration = max(0.1, random.weibullvariate(2.0, 5.0))
        pkts_per_flow = max(1, int(random.gammavariate(3.0, 8.0)))
        flow_table_util = random.betavariate(2.0, 4.0) * 0.5 + 0.1
        new_flow_rate = max(0.1, random.gammavariate(1.5, 3.0))
        port_entropy = random.betavariate(2.0, 5.0) * 3.0 + 0.2
        
    else:  # mixed
        iat = max(0.0005, random.gammavariate(1.5, 0.05))
        flow_duration = max(0.01, random.weibullvariate(1.5, 2.0))
        pkts_per_flow = max(1, int(random.gammavariate(2.0, 5.0)))
        flow_table_util = random.betavariate(4.0, 2.0) * 0.6 + 0.1
        new_flow_rate = max(0.5, random.gammavariate(2.0, 15.0))
        port_entropy = random.betavariate(3.0, 2.0) * 4.0 + 0.5
    
    bytes_per_flow = pkts_per_flow * pkt_size
    
    # Add noise to create overlap
    flow_table_util += random.gauss(0, 0.15)
    new_flow_rate += random.gauss(0, 10.0)
    port_entropy += random.gauss(0, 0.8)
    
    # Clip values - allowing wider ranges that overlap with normal
    iat = max(0.0001, min(iat, 3.0))
    flow_duration = max(0.001, min(flow_duration, 60.0))
    pkts_per_flow = max(1, min(pkts_per_flow, 500))
    bytes_per_flow = max(40, min(bytes_per_flow, 500000))
    flow_table_util = max(0.01, min(flow_table_util, 1.0))
    new_flow_rate = max(0.1, min(new_flow_rate, 200.0))
    port_entropy = max(0.1, min(port_entropy, 5.5))
    
    flow_pkt_ratio = (new_flow_rate * flow_duration) / max(pkts_per_flow, 1)
    burst_score = new_flow_rate / max(flow_duration, 0.001)
    e_delta = abs(ip_entropy(src_ip) - ip_entropy(dst_ip))
    
    # Spoofing confidence with significant overlap
    if phase == 'stealth_probe' or random.random() < 0.3:
        spoofing_conf = random.betavariate(1.5, 5.0) * 0.5 + 0.05
    else:
        spoofing_conf = random.betavariate(3.0, 2.0) * 0.6 + 0.2
    
    spoofing_conf = max(0.01, min(spoofing_conf, 1.0))
    
    records.append({
        'timestamp': ts, 'src_mac': src_mac, 'dst_mac': random.choice(known_macs),
        'eth_type': 2048, 'protocol': proto,
        'src_ip': src_ip, 'dst_ip': dst_ip,
        'src_port': src_port, 'dst_port': dst_port,
        'pkt_size': pkt_size, 'ttl': ttl,
        'iat': round(iat, 6),
        'flow_duration': round(flow_duration, 6),
        'pkts_per_flow': pkts_per_flow,
        'bytes_per_flow': int(bytes_per_flow),
        'flow_table_util': round(flow_table_util, 6),
        'new_flow_rate': round(new_flow_rate, 6),
        'port_entropy': round(port_entropy, 6),
        'flow_pkt_ratio': round(min(flow_pkt_ratio, 200), 6),
        'burst_score': round(min(burst_score, 5000), 6),
        'entropy_delta': round(e_delta, 6),
        'spoofing_conf': round(spoofing_conf, 6),
        'label': 1
    })

df = pd.DataFrame(records).sample(frac=1, random_state=42).reset_index(drop=True)
home = os.path.expanduser("~")
os.makedirs(f"{home}/loft_project/data", exist_ok=True)
out = f"{home}/loft_project/data/full_dataset.csv"
df.to_csv(out, index=False)

print(f"\n[+] Dataset saved → {out}")
print(f"    Total   : {len(df)}")
print(f"    Normal  : {len(df[df['label']==0])}  ({len(df[df['label']==0])/len(df)*100:.1f}%)")
print(f"    Attack  : {len(df[df['label']==1])}  ({len(df[df['label']==1])/len(df)*100:.1f}%)")

print(f"\n  Feature overlap check (lower ratio = more challenging):")
overlap_stats = []
for feat in ['ttl','pkt_size','bytes_per_flow','flow_duration',
             'pkts_per_flow','iat','flow_table_util',
             'new_flow_rate','port_entropy','burst_score','spoofing_conf']:
    n = df[df['label']==0][feat]
    a = df[df['label']==1][feat]
    ratio = abs(n.mean()-a.mean()) / (n.std()+a.std()+1e-9)
    
    # Check actual overlap percentage
    n_vals = n.values
    a_vals = a.values
    n_range = (n_vals.min(), n_vals.max())
    a_range = (a_vals.min(), a_vals.max())
    overlap_min = max(n_range[0], a_range[0])
    overlap_max = min(n_range[1], a_range[1])
    overlap_pct = 0
    if overlap_min < overlap_max:
        n_overlap = ((n_vals >= overlap_min) & (n_vals <= overlap_max)).mean() * 100
        a_overlap = ((a_vals >= overlap_min) & (a_vals <= overlap_max)).mean() * 100
        overlap_pct = (n_overlap + a_overlap) / 2
    
    if ratio < 0.3:
        quality = "✅ excellent overlap"
    elif ratio < 0.8:
        quality = "✅ good overlap"  
    elif ratio < 1.5:
        quality = "🟡 partial overlap"
    elif ratio < 2.5:
        quality = "🟠 weak overlap"
    else:
        quality = "🔴 separable"
    
    overlap_stats.append((feat, ratio, quality, overlap_pct))
    print(f"    {feat:<20}: ratio={ratio:.2f} {quality} (overlap: {overlap_pct:.1f}%)")
    print(f"      Normal: {n.mean():.3f}±{n.std():.3f} [{n.min():.3f}, {n.max():.3f}]")
    print(f"      Attack: {a.mean():.3f}±{a.std():.3f} [{a.min():.3f}, {a.max():.3f}]")

# Overall challenge score
avg_ratio = sum(s[1] for s in overlap_stats) / len(overlap_stats)
avg_overlap = sum(s[3] for s in overlap_stats) / len(overlap_stats)
print(f"\n  📊 Dataset Challenge Metrics:")
print(f"    Average separation ratio: {avg_ratio:.2f} (target <1.0)")
print(f"    Average overlap percentage: {avg_overlap:.1f}% (target >50%)")
if avg_ratio < 1.0 and avg_overlap > 50:
    print("    ✅ This dataset is realistically challenging!")
else:
    print("    ⚠️  Dataset may need more overlap for realistic challenge")