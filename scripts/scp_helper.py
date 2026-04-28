#!/usr/bin/env python3
"""Upload a file to the RK3588 board via SCP."""
import sys
import paramiko

def upload(local_path, remote_path):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.1.109", username="orangepi", password="orangepi", timeout=15)
    transport = client.get_transport()
    transport.set_keepalive(30)
    sftp = paramiko.SFTPClient.from_transport(transport)
    sftp.put(local_path, remote_path)
    sftp.close()
    client.close()
    print(f"Uploaded: {local_path} -> {remote_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: scp_helper.py <local_path> <remote_path>")
        sys.exit(1)
    upload(sys.argv[1], sys.argv[2])
