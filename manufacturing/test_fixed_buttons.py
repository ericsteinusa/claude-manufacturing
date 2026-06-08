import sys
import os
import time
import subprocess

mfg = os.path.dirname(os.path.abspath(__file__))
tests = [
    ('Accounts_payable.py', 'acct_pay', '/tmp/test_ap.png'),
    ('Accounts_receivable.py', 'acct_rcv', '/tmp/test_ar.png'),
    ('Credit_dept.py', 'credit', '/tmp/test_cr.png'),
]

for script, key, shot in tests:
    print(f"Launching {script} with key '{key}' ...")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(mfg, script), key],
        cwd=mfg, env={**os.environ, 'DISPLAY': ':0'},
        stderr=subprocess.PIPE, stdout=subprocess.PIPE
    )
    time.sleep(3)
    ret = proc.poll()
    if ret is not None:
        out, err = proc.communicate()
        print(f"  CRASHED (exit {ret})")
        print(f"  stderr: {err.decode()[:500]}")
    else:
        subprocess.run(['import', '-window', 'root', '-crop', '1150x700+0+0', shot],  # noqa: E501
                       env={**os.environ, 'DISPLAY': ':0'})
        print(f"  Running OK — screenshot saved to {shot}")
        proc.terminate()
        proc.wait()
    time.sleep(1)

print("Done.")
