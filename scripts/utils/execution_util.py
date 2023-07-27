import shlex
import subprocess

class ExecutionUtil:
    def __init__(self):
        return

    def executeCommand(self, cmd):
        args = shlex.split(cmd)
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding="cp850", universal_newlines=True)
        stdout, err = p.communicate()

        return stdout if err is None else stdout + err
