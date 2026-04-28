#!/usr/bin/env python3
"""Execute a command on the RK3588 board, streaming output in real-time."""
import sys
import paramiko
import select

def run_interactive(cmd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.1.109", username="orangepi", password="orangepi", timeout=15)
    transport = client.get_transport()
    transport.set_keepalive(30)
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=None)

    # Stream output
    import os
    stdout.channel.setblocking(0)
    stderr.channel.setblocking(0)

    while True:
        # Check if command is done
        if stdout.channel.exit_status_ready() and stderr.channel.recv_ready() == 0 and stdout.channel.recv_ready() == 0:
            break

        # Read available data
        import time
        time.sleep(0.1)

        while stdout.channel.recv_ready():
            data = stdout.channel.recv(4096).decode("utf-8", errors="replace")
            if data:
                sys.stdout.write(data)
                sys.stdout.flush()

        while stderr.channel.recv_ready():
            data = stderr.channel.recv(4096).decode("utf-8", errors="replace")
            if data:
                sys.stderr.write(data)
                sys.stderr.flush()

    # Read any remaining
    remaining = stdout.read().decode("utf-8", errors="replace")
    if remaining:
        sys.stdout.write(remaining)

    code = stdout.channel.recv_exit_status()
    client.close()
    return code

if __name__ == "__main__":
    cmd = " ".join(sys.argv[1:])
    sys.exit(run_interactive(cmd))
