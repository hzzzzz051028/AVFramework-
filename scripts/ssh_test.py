import paramiko, traceback, sys
try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('192.168.1.109', username='orangepi', password='orangepi', timeout=10)
    stdin, stdout, stderr = client.exec_command('uname -a', timeout=15)
    out = stdout.read().decode()
    err = stderr.read().decode()
    rc = stdout.channel.recv_exit_status()
    with open('d:/video_test/scripts/ssh_test_output.txt', 'w') as f:
        f.write(f"OUT: {out}\nERR: {err}\nRC: {rc}\n")
    client.close()
except Exception as e:
    with open('d:/video_test/scripts/ssh_test_output.txt', 'w') as f:
        f.write(f"ERROR: {e}\n")
        traceback.print_exc(file=f)
