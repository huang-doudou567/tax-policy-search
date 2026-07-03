#!/usr/bin/env python3
"""
Tunnel daemon — keep the serveo.net SSH tunnel alive.
Restarts on disconnect. Prints the public URL on each (re)connect.
"""
import subprocess
import time
import re
import sys
import os

LOCAL_PORT = 5080
TUNNEL_HOST = "serveo.net"
RETRY_DELAY = 10  # seconds between reconnect attempts

os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def run_tunnel():
    """Start SSH tunnel and yield public URLs as they appear."""
    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ExitOnForwardFailure=yes",
        "-tt",
        "-R", f"80:localhost:{LOCAL_PORT}",
        TUNNEL_HOST,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    url_pattern = re.compile(
        r"https://[a-z0-9]+-[0-9\-]+\.serveousercontent\.com"
    )
    try:
        for line in iter(proc.stdout.readline, ""):
            print(line, end="", flush=True)
            m = url_pattern.search(line)
            if m:
                yield m.group(0)
    finally:
        proc.kill()
        proc.wait()


def main():
    print(f"  Tunnel daemon started (port {LOCAL_PORT} -> {TUNNEL_HOST})")
    last_url = None
    while True:
        try:
            for url in run_tunnel():
                if url != last_url:
                    print(f"\n  🌐 Public URL: {url}\n")
                    last_url = url
        except KeyboardInterrupt:
            print("\n  Daemon stopped.")
            break
        except Exception as e:
            print(f"  ⚠️ Tunnel error: {e}")
        print(f"  🔄 Reconnecting in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)


if __name__ == "__main__":
    main()
