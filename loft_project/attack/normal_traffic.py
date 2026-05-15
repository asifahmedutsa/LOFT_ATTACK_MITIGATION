from scapy.all import *
import time

def generate_normal_traffic(src_ip, dst_ip, duration=30, iface="h1-eth0"):
    """
    Normal Traffic: Regular communication between hosts
    Same IPs and ports = normal predictable flows
    """
    print(f"[*] Generating normal traffic from {src_ip} to {dst_ip}...")
    
    start = time.time()
    count = 0
    ports = [80, 443, 22, 53, 8080]  # Common ports

    while time.time() - start < duration:
        dst_port = ports[count % len(ports)]

        pkt = IP(src=src_ip, dst=dst_ip) / TCP(
            sport=12345,
            dport=dst_port,
            flags="S"
        )

        send(pkt, iface=iface, verbose=False)
        count += 1
        time.sleep(0.1)  # Slow, normal pace

        if count % 20 == 0:
            print(f"[*] Sent {count} normal packets...")

    print(f"[+] Normal traffic done! Sent {count} packets in {duration} seconds.")

if __name__ == "__main__":
    generate_normal_traffic(
        src_ip="10.0.1.1",
        dst_ip="10.0.1.2",
        duration=30,
        iface="h1-eth0"
    )
