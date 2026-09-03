"""Reporting / logging to multiple bounded log files.

Rather than one unbounded log, MoveAny writes several per-category files:
  - session.log   : high-level progress and summaries
  - copied.log    : every file copied to destination
  - identical.log : files verified byte-identical on both sides (scan)
  - missing.log   : files on source but missing on destination
  - different.log : files present on both but with differing content
  - extra.log     : files present on destination only
  - moved.log     : files deleted from source during the delete phase
  - errors.log    : every error encountered
"""
import os


class Reporter:
    def __init__(self, log_dir):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self._handles = {}

    def _fh(self, name):
        if name not in self._handles:
            self._handles[name] = open(
                os.path.join(self.log_dir, name), "a", encoding="utf-8"
            )
        return self._handles[name]

    def write(self, name, line):
        fh = self._fh(name)
        fh.write(line.rstrip("\n") + "\n")
        fh.flush()

    def session(self, line):
        self.write("session.log", line)

    def info(self, line):
        print(line)
        self.write("session.log", line)

    def error(self, line):
        print("[ERROR]", line)
        self.write("errors.log", line)

    def copied(self, rel):
        self.write("copied.log", rel)

    def identical(self, rel):
        self.write("identical.log", rel)

    def missing(self, rel):
        self.write("missing.log", rel)

    def different(self, rel):
        self.write("different.log", rel)

    def moved(self, rel):
        self.write("moved.log", rel)

    def close(self):
        for fh in self._handles.values():
            try:
                fh.close()
            except Exception:
                pass
        self._handles.clear()
