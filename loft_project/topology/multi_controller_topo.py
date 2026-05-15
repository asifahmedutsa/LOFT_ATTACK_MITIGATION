from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink

def create_topology():
    net = Mininet(switch=OVSSwitch, link=TCLink, autoSetMacs=True)

    print("[*] Creating 3 Remote Controllers...")
    c1 = net.addController('c1', controller=RemoteController, ip='127.0.0.1', port=6633)
    c2 = net.addController('c2', controller=RemoteController, ip='127.0.0.1', port=6634)
    c3 = net.addController('c3', controller=RemoteController, ip='127.0.0.1', port=6635)

    print("[*] Creating 3 Switches...")
    s1 = net.addSwitch('s1', protocols='OpenFlow13')
    s2 = net.addSwitch('s2', protocols='OpenFlow13')
    s3 = net.addSwitch('s3', protocols='OpenFlow13')

    print("[*] Creating 6 Hosts...")
    h1 = net.addHost('h1', ip='10.0.1.1/24')
    h2 = net.addHost('h2', ip='10.0.1.2/24')
    h3 = net.addHost('h3', ip='10.0.2.1/24')
    h4 = net.addHost('h4', ip='10.0.2.2/24')
    h5 = net.addHost('h5', ip='10.0.3.1/24')
    h6 = net.addHost('h6', ip='10.0.3.2/24')

    print("[*] Connecting Hosts to Switches...")
    # Segment 1
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    # Segment 2
    net.addLink(h3, s2)
    net.addLink(h4, s2)
    # Segment 3
    net.addLink(h5, s3)
    net.addLink(h6, s3)

    # Connect switches together (inter-segment links)
    print("[*] Connecting Switches together...")
    net.addLink(s1, s2)
    net.addLink(s2, s3)

    print("[*] Starting Network...")
    net.start()

    # Assign each switch to its controller
    s1.start([c1])
    s2.start([c2])
    s3.start([c3])

    print("\n[+] Network is UP!")
    print("    Segment 1: h1(10.0.1.1), h2(10.0.1.2) --> Switch s1 --> Controller c1 (port 6633)")
    print("    Segment 2: h3(10.0.2.1), h4(10.0.2.2) --> Switch s2 --> Controller c2 (port 6634)")
    print("    Segment 3: h5(10.0.3.1), h6(10.0.3.2) --> Switch s3 --> Controller c3 (port 6635)")

    print("\n[*] Testing connectivity...")
    net.pingAll()

    print("\n[*] Opening Mininet CLI (type 'exit' to quit)...")
    CLI(net)

    net.stop()
    print("[+] Network stopped.")

if __name__ == '__main__':
    setLogLevel('info')
    create_topology()
