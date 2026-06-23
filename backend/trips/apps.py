import os
import sys
import threading

from django.apps import AppConfig


class TripsConfig(AppConfig):
    name = 'trips'

    def ready(self):
        self._probe_codex_login()

    def _probe_codex_login(self):
        """Confirm the Codex CLI is logged in — once, in the background.

        Codex auth is machine-level and persists across restarts, so this is a
        one-time check per server process (not per request). It runs in a daemon
        thread to avoid blocking startup, and is skipped for management commands
        (migrate, test, …) and for the autoreloader's watcher process.
        """
        argv = sys.argv
        # Never probe during tests (pytest imports its module) — keeps the test
        # run hermetic and avoids spawning subprocesses in CI.
        if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
            return
        management_cmds = {
            "migrate", "makemigrations", "test", "collectstatic",
            "shell", "shell_plus", "createsuperuser", "loaddata", "dumpdata",
        }
        if any(cmd in argv for cmd in management_cmds):
            return
        # Under `runserver`, ready() fires in both the watcher and the worker;
        # RUN_MAIN is set only in the worker, so run the probe just once there.
        if "runserver" in argv and os.environ.get("RUN_MAIN") != "true":
            return

        def _run():
            from .agent import log_login_status
            log_login_status()

        threading.Thread(target=_run, name="codex-login-probe", daemon=True).start()
