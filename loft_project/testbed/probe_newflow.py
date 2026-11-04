"""Service-level probe for E5 (as in LOFT and ALFO-Guard): can a benign host still open new
connections while the table is under attack, and how long does each take?

  server:  probe_newflow.py --serve --port 7777
  client:  probe_newflow.py --dst 10.1.0.100 --port 7777 --interval 0.5 --duration 300 --out probe.csv

The client opens a fresh TCP connection every --interval seconds (a new source port, so a new
5-tuple in each direction that needs its own flow entry), sends 1 KB, waits for the echo and
closes. One CSV row per attempt: wall-clock start, ok, connect ms, round-trip ms, error.
Standard library only (runs on the testbed's Python 3.8).
"""
import argparse
import csv
import socket
import threading
import time

PAYLOAD = b"x" * 1024


def serve(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(256)

    def echo(c):
        try:
            c.settimeout(5)
            got = b""
            while len(got) < len(PAYLOAD):
                b = c.recv(65536)
                if not b:
                    break
                got += b
            c.sendall(got)
        except OSError:
            pass
        finally:
            c.close()

    while True:
        c, _ = s.accept()
        threading.Thread(target=echo, args=(c,), daemon=True).start()


def attempt(dst, port, timeout):
    t0 = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((dst, port))
        t1 = time.time()
        s.sendall(PAYLOAD)
        got = b""
        while len(got) < len(PAYLOAD):
            b = s.recv(65536)
            if not b:
                raise OSError("closed early")
            got += b
        t2 = time.time()
        return [round(t0, 3), 1, round(1000 * (t1 - t0), 2), round(1000 * (t2 - t0), 2), ""]
    except OSError as e:
        return [round(t0, 3), 0, "", "", type(e).__name__]
    finally:
        s.close()


def client(a):
    rows = []
    end = time.time() + a.duration
    lock = threading.Lock()

    def run():
        r = attempt(a.dst, a.port, a.timeout)
        with lock:
            rows.append(r)

    threads = []
    nxt = time.time()
    while nxt < end:
        th = threading.Thread(target=run, daemon=True)
        th.start()
        threads.append(th)
        nxt += a.interval
        time.sleep(max(nxt - time.time(), 0))
    for th in threads:
        th.join(a.timeout + 6)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_wall", "ok", "connect_ms", "rtt_ms", "error"])
        w.writerows(sorted(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--dst")
    ap.add_argument("--port", type=int, default=7777)
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--duration", type=float, default=300)
    ap.add_argument("--timeout", type=float, default=3.0)
    ap.add_argument("--out", default="probe.csv")
    a = ap.parse_args()
    serve(a.port) if a.serve else client(a)


if __name__ == "__main__":
    main()
