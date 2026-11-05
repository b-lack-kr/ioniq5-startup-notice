#!/usr/bin/env python3
"""Run the actual monitor with isolated host fakes; never invoke vehicle tools."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

BASE = Path(__file__).resolve().parents[1]
MOCK = r'''
import json, os, sys, time
from pathlib import Path
root = Path(os.environ["NEEV_TEST_ROOT"])
statepath = root / "mock-state.json"
s = json.loads(statepath.read_text())
tool = Path(sys.argv[0]).name
def save():
    statepath.write_text(json.dumps(s))
if tool == "getprop":
    values = {"ro.build.product": s["product"], "ro.board.platform": "tcc803x",
              "ro.build.version.release": "4.4.2", "sys.boot_completed": s["boot"]}
    print(values.get(sys.argv[1], ""))
elif tool == "dumpsys":
    if s["display"] == "on": print("mDisplayPowerRequest=policy=BRIGHT")
    elif s["display"] == "off": print("mDisplayPowerRequest=policy=OFF")
    else: print("unknown display")
elif tool == "app_process":
    if sys.argv[1:3] != ["/system/bin", "NeevConsent"]:
        raise AssertionError("unexpected Java invocation " + repr(sys.argv))
    action = sys.argv[3]
    if action not in ("--check", "--dismiss"): raise AssertionError(action)
    key = action[2:]
    count = s.get(key + "_count", 0)
    responses = s.get(key + "_responses", [0])
    rc = responses[min(count, len(responses)-1)]
    s[key + "_count"] = count + 1
    save()
    with (root / "calls.jsonl").open("a") as out:
        out.write(json.dumps({"action": action, "time": s["time"], "rc": rc,
                              "boot": s["boot"], "display": s["display"]}) + "\n")
    status = {0: "ready" if action == "--check" else "dismiss-requested",
              10: "boot-incomplete", 11: "service-unavailable", 20: "refused", 21: "error"}[rc]
    print("status=" + status)
    sys.exit(rc)
elif tool == "sleep":
    s["time"] += int(sys.argv[1])
    for event in s["events"]:
        if not event.get("done") and s["time"] >= event["at"]:
            for key in ("boot", "display"):
                if key in event: s[key] = event[key]
            if event.get("clear_marker"):
                try: (root / "session").unlink()
                except FileNotFoundError: pass
            event["done"] = True
    (root / "uptime").write_text(str(s["time"]) + ".00 0.00\n")
    save()
    if s["time"] >= s["stop"]:
        (root / "finished").write_text("scenario complete\n")
        # The test parent terminates this isolated process group immediately.
        time.sleep(10)
else:
    raise AssertionError("unrecognized fake " + tool)
'''


class MonitorTests(unittest.TestCase):
    def scenario(self, *, marker=None, script="package/svc/watch.sh", **overrides):
        state = dict(product="NEEV.KOR.0000.V039.001.260902", boot="1", display="on",
                     time=20, stop=55, events=[], check_responses=[0], dismiss_responses=[0])
        state.update(overrides)
        with tempfile.TemporaryDirectory(prefix="neev-monitor-test-") as temp:
            root = Path(temp)
            tools = root / "tools"
            tools.mkdir()
            for name in ("getprop", "dumpsys", "app_process", "sleep", "dirname"):
                file = tools / name
                file.write_text("#!" + sys.executable + "\n" + MOCK)
                file.chmod(0o700)
            (root / "mock-state.json").write_text(json.dumps(state))
            (root / "uptime").write_text(str(state["time"]) + ".00 0.00\n")
            (root / "boot-id").write_text("current-boot\n")
            if marker is not None:
                (root / "session").write_text(marker + "\n")
            env = os.environ.copy()
            env.update(NEEV_TEST_ROOT=str(root),
                       NEEV_GETPROP=str(tools / "getprop"),
                       NEEV_APP_PROCESS=str(tools / "app_process"),
                       NEEV_DUMPSYS=str(tools / "dumpsys"),
                       NEEV_STATE=str(root / "state"),
                       NEEV_SESSION=str(root / "session"),
                       NEEV_UPTIME_FILE=str(root / "uptime"),
                       NEEV_BOOT_ID_FILE=str(root / "boot-id"),
                       NEEV_FB_BLANK=str(root / "no-framebuffer"),
                       PATH=str(tools) + ":/usr/bin:/bin:/usr/sbin:/sbin")
            with (root / "output").open("w") as output:
                proc = subprocess.Popen(["/bin/sh", BASE / script], env=env,
                                        stdout=output, stderr=subprocess.STDOUT,
                                        start_new_session=True)
                completed = False
                deadline = time.monotonic() + 15
                try:
                    while time.monotonic() < deadline:
                        if proc.poll() is not None:
                            completed = True
                            break
                        if (root / "finished").exists():
                            completed = True
                            break
                        time.sleep(0.01)
                finally:
                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=2)
            log = (root / "output").read_text()
            self.assertTrue(completed, "monitor scenario hung: " + log)
            callfile = root / "calls.jsonl"
            calls = [json.loads(line) for line in callfile.read_text().splitlines()] if callfile.exists() else []
            last = root / "state/last_attempt.txt"
            return dict(calls=calls, log=log, rc=proc.returncode,
                        marker=(root / "session").read_text() if (root / "session").exists() else None,
                        attempt=last.read_text() if last.exists() else None)

    @staticmethod
    def dismissals(result):
        return [c for c in result["calls"] if c["action"] == "--dismiss"]

    def test_wrong_firmware_never_loads_helper(self):
        r = self.scenario(product="NEEV.USA.0000.V039.001.260902")
        self.assertEqual(r["rc"], 20)
        self.assertEqual(r["calls"], [])
        self.assertIsNone(r["marker"])

    def test_boot_delay_prevents_early_dismissal(self):
        r = self.scenario(time=3, stop=50, boot="0", events=[dict(at=30, boot="1")])
        calls = self.dismissals(r)
        self.assertEqual(len(calls), 1)
        self.assertGreaterEqual(calls[0]["time"], 30)
        self.assertEqual(calls[0]["boot"], "1")

    def test_stable_display_calls_once(self):
        r = self.scenario()
        self.assertEqual(len(self.dismissals(r)), 1)
        self.assertIn("status=dismiss-requested", r["attempt"])
        self.assertIn("current-boot", r["marker"])

    def test_prior_kernel_marker_does_not_suppress_new_boot(self):
        r = self.scenario(marker="100 prior-boot")
        self.assertEqual(len(self.dismissals(r)), 1)
        self.assertIn("current-boot", r["marker"])

    def test_same_boot_restart_does_not_repeat_call(self):
        r = self.scenario(marker="18 current-boot")
        self.assertEqual(r["calls"], [])

    def test_dark_screen_waits_for_display_wake(self):
        r = self.scenario(display="off", events=[dict(at=32, display="on")])
        calls = self.dismissals(r)
        self.assertEqual(len(calls), 1)
        self.assertGreaterEqual(calls[0]["time"], 32)
        self.assertEqual(calls[0]["display"], "on")

    def test_subsequent_display_wake_calls_once_more(self):
        r = self.scenario(stop=70, events=[dict(at=31, display="off"), dict(at=49, display="on")])
        calls = self.dismissals(r)
        self.assertEqual(len(calls), 2)
        self.assertGreaterEqual(calls[1]["time"], 49)

    def test_quickboot_marker_clear_rearms_after_cooldown(self):
        r = self.scenario(stop=72, events=[dict(at=49, clear_marker=True)])
        calls = self.dismissals(r)
        self.assertEqual(len(calls), 2)
        self.assertGreaterEqual(calls[1]["time"] - calls[0]["time"], 15)
        self.assertIn("quickboot-marker-cleared", r["attempt"])

    def test_unknown_call_error_is_not_blindly_retried(self):
        r = self.scenario(dismiss_responses=[21])
        self.assertEqual(len(self.dismissals(r)), 1)
        self.assertIn("exit=21", r["attempt"])
        self.assertIn("current-boot", r["marker"])

    def test_readiness_service_late_registration_recovers(self):
        r = self.scenario(stop=65, check_responses=[11, 0])
        self.assertEqual(len(self.dismissals(r)), 1)
        self.assertGreaterEqual(self.dismissals(r)[0]["time"], 35)

    def test_persistent_unavailable_service_is_bounded(self):
        r = self.scenario(stop=165, check_responses=[11])
        self.assertEqual(len(r["calls"]), 8)
        self.assertEqual(self.dismissals(r), [])
        self.assertIn("readiness timeout", r["log"])
        self.assertIn("current-boot", r["marker"])

    def test_display_off_during_grace_prevents_call(self):
        r = self.scenario(stop=38, events=[dict(at=21, display="off")])
        self.assertTrue(r["calls"])
        self.assertEqual(self.dismissals(r), [])

    def test_preflight_refusal_stops_without_dismissal(self):
        r = self.scenario(check_responses=[20])
        self.assertEqual(r["rc"], 20)
        self.assertEqual(self.dismissals(r), [])

    def test_repeated_service_race_at_dismissal_is_bounded(self):
        r = self.scenario(stop=190, dismiss_responses=[11])
        self.assertEqual(len(self.dismissals(r)), 8)
        self.assertIn("current-boot", r["marker"])

    def test_framework_restart_rearms_with_same_kernel_marker(self):
        r = self.scenario(stop=75, events=[dict(at=40, boot="0"), dict(at=49, boot="1")])
        calls = self.dismissals(r)
        self.assertEqual(len(calls), 2)
        self.assertGreaterEqual(calls[1]["time"], 49)
        self.assertIn("framework-ready", r["attempt"])

    def test_install_defers_transient_binder_registration(self):
        r = self.scenario(script="package/scripts/preinstall.sh", check_responses=[11])
        self.assertEqual(r["rc"], 0)
        self.assertEqual(len(r["calls"]), 1)
        self.assertEqual(self.dismissals(r), [])

    def test_install_rejects_api_mismatch(self):
        r = self.scenario(script="package/scripts/preinstall.sh", check_responses=[20])
        self.assertEqual(r["rc"], 20)
        self.assertEqual(self.dismissals(r), [])

    def test_install_preflight_is_read_only(self):
        r = self.scenario(script="package/scripts/preinstall.sh")
        self.assertEqual(r["rc"], 0)
        self.assertEqual(len(r["calls"]), 1)
        self.assertEqual(self.dismissals(r), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
