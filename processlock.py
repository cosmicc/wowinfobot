import fcntl
import os
import sys
from pathlib import Path

from loguru import logger as log

rundir = Path("/run")
tmpdir = Path("/tmp")


def cleanName(filename):
    filename = os.path.basename(filename)
    filename = filename.rsplit(".", 1)[0]
    return filename


class PLock:
    def __init__(self):
        self.pid = str(os.getpid())
        if rundir.is_dir() and os.access(str(rundir), os.W_OK):
            self.lockdir = rundir
        elif tmpdir.is_dir() and os.access(str(tmpdir), os.W_OK):
            self.lockdir = tmpdir
        else:
            log.critical("Cannot find a valid place to put the lockfile. Exiting")
            exit(1)
        self.lockfile = self.lockdir / f"{cleanName(sys.argv[0])}.lock"
        self.pidfile = self.lockdir / f"{cleanName(sys.argv[0])}.pid"

    def _aquirelock(self):
        if not self.lockfile.is_file():
            self.lockfile.touch(mode=0o600)
        try:
            self.lockhandle = open(self.lockfile, "w")
            fcntl.lockf(self.lockhandle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, BlockingIOError):
            log.exception(f"IOError locking file {self.lockfile}. exiting.")
            return False
        except:
            log.exception(f"General error trying to lock process to file {self.lockfile}. exiting.")
            exit(1)
        else:
            log.debug(f"Process [{self.pid}] locked to file [{self.lockfile}]")
            return True

    def _setpidfile(self):
        try:
            self.pidfile.write_text(self.pid)
        except:
            log.exception(f"Error writing pid file {self.pidfile}")
        else:
            log.debug(f"Pid file [{self.pidfile}] holding pid [{self.pid}]")

    def lock(self):
        if self._aquirelock():
            self._setpidfile()
            return True
        else:
            log.error(f"Trying to start, but already running on pid {self.pid}")
            exit(1)

    def unlock(self):
        fcntl.flock(self.lockhandle, fcntl.LOCK_UN)
        self.lockhandle.close()
        if self.pidfile.exists():
            self.pidfile.unlink()
        if self.lockfile.exists():
            self.lockfile.unlink()
