#!/usr/bin/env python3
"""Helper to run commands on the RK3588 board via SSH."""
import sys
import paramiko

def run(cmd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.1.109", username="orangepi", password="orangepi", timeout=15)
    transport = client.get_transport()
    transport.set_keepalive(30)
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    # No channel timeout — let the command run as long as needed
    stdout.channel.settimeout(None)
    stderr.channel.settimeout(None)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    if out:
        print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    return code

if __name__ == "__main__":
    cmd = " ".join(sys.argv[1:])
    sys.exit(run(cmd))
