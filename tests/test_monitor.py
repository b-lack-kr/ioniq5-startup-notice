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
def save(): statepath.write_text(json.dumps(s))
def record(name, value):
    with (root / name).open("a") as out: out.write(json.dumps(value) + "\n")
def marker():
    p = root / "session"
    return p.read_text() if p.exists() else None
if tool == "getprop":
    values = {"ro.build.product": s["product"], "ro.board.platform": "tcc803x",
              "ro.build.version.release": "4.4.2", "sys.boot_completed": s["boot"]}
    print(values.get(sys.argv[1], ""))
elif tool == "dumpsys":
    if s["display"] == "on": print("mDisplayPowerRequest=policy=BRIGHT")
    elif s["display"] == "off": print("mDisplayPowerRequest=policy=OFF")
    else: print("unknown display")
elif tool == "service":
    assert sys.argv[1:] == ["check", "com.hkmc.factory"], sys.argv
    index = s.get("service_count", 0)
    responses = s.get("service_responses")
    response = responses[min(index, len(responses)-1)] if responses else dict(
        text="Service com.hkmc.factory: " + ("found" if s["service_ready"] else "not found"), rc=0)
    s["service_count"] = index + 1
    if index == 0 and s.get("display_off_during_registry_check"):
        s["display"] = "off"
    save()
    record("service-calls.jsonl", dict(time=s["time"], boot=s["boot"], display=s["display"], **response))
    print(response["text"])
    sys.exit(response["rc"])
elif tool == "app_process":
    assert sys.argv[1:3] == ["/system/bin", "NeevConsent"], sys.argv
    action = sys.argv[3]
    assert action in ("--check", "--dismiss"), action
    key = action[2:]
    count = s.get(key + "_count", 0)
    responses = s.get(key + "_responses", [0])
    rc = responses[min(count, len(responses)-1)]
    s[key + "_count"] = count + 1
    save()
    record("calls.jsonl", dict(action=action, time=s["time"], rc=rc,
                               boot=s["boot"], display=s["display"], marker_before=marker()))
    status = {0: "ready" if action == "--check" else "dismiss-requested",
              10: "boot-incomplete", 11: "service-unavailable", 20: "refused", 21: "error"}.get(rc, "unknown")
    print("status=" + status)
    sys.exit(rc)
elif tool == "sleep":
    requested = int(sys.argv[1])
    record("sleeps.jsonl", dict(time=s["time"], requested=requested, marker=marker()))
    # Accelerate only logical time for long timeout cases. Requested sleep is
    # independently recorded; each step remains below the 45-second resume gap.
    s["time"] += requested * s.get("clock_step", 1)
    for event in s["events"]:
        if not event.get("done") and s["time"] >= event["at"]:
            for key in ("boot", "display", "service_ready"):
                if key in event: s[key] = event[key]
            if event.get("clear_marker"):
                try: (root / "session").unlink()
                except FileNotFoundError: pass
            event["done"] = True
    (root / "uptime").write_text(str(s["time"]) + ".00 0.00\n")
    save()
    if s["time"] >= s["stop"]:
        (root / "finished").write_text("scenario complete\n")
        time.sleep(10)  # Parent terminates this isolated process group.
elif tool == "dirname":
    raise AssertionError("dirname is unavailable on the vehicle")
else:
    raise AssertionError("unrecognized fake " + tool)
'''


class MonitorTests(unittest.TestCase):
    def scenario(self, *, marker=None, script="package/svc/watch.sh", **overrides):
        state = dict(product="NEEV.KOR.0000.V039.001.260902", boot="1", display="on",
                     time=20, stop=24, events=[], check_responses=[0], dismiss_responses=[0],
                     service_ready=True, clock_step=1)
        state.update(overrides)
        with tempfile.TemporaryDirectory(prefix="neev-monitor-test-") as temp:
            root = Path(temp)
            tools = root / "tools"
            tools.mkdir()
            for name in ("getprop", "dumpsys", "service", "app_process", "sleep", "dirname"):
                file = tools / name
                file.write_text("#!" + sys.executable + "\n" + MOCK)
                file.chmod(0o700)
            (root / "mock-state.json").write_text(json.dumps(state))
            (root / "uptime").write_text(str(state["time"]) + ".00 0.00\n")
            (root / "boot-id").write_text("current-boot\n")
            if marker is not None: (root / "session").write_text(marker + "\n")
            env = os.environ.copy()
            env.update(NEEV_TEST_ROOT=str(root), NEEV_GETPROP=str(tools / "getprop"),
                       NEEV_APP_PROCESS=str(tools / "app_process"),
                       NEEV_DUMPSYS=str(tools / "dumpsys"), NEEV_SERVICE=str(tools / "service"),
                       NEEV_STATE=str(root / "state"), NEEV_SESSION=str(root / "session"),
                       NEEV_UPTIME_FILE=str(root / "uptime"), NEEV_BOOT_ID_FILE=str(root / "boot-id"),
                       NEEV_FB_BLANK=str(root / "no-framebuffer"),
                       PATH=str(tools) + ":/usr/bin:/bin:/usr/sbin:/sbin")
            with (root / "output").open("w") as output:
                proc = subprocess.Popen(["/bin/sh", BASE / script], env=env,
                                        stdout=output, stderr=subprocess.STDOUT,
                                        start_new_session=True)
                completed = False
                deadline = time.monotonic() + 45
                try:
                    while time.monotonic() < deadline:
                        if proc.poll() is not None or (root / "finished").exists():
                            completed = True
                            break
                        time.sleep(0.01)
                finally:
                    if proc.poll() is None: os.killpg(proc.pid, signal.SIGTERM)
                    try: proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=2)
            log = (root / "output").read_text()
            self.assertTrue(completed, "monitor scenario hung: " + log)
            def records(name):
                path = root / name
                return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
            last = root / "state/last_attempt.txt"
            return dict(calls=records("calls.jsonl"), native=records("service-calls.jsonl"),
                        sleeps=records("sleeps.jsonl"), log=log, rc=proc.returncode,
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

    def test_early_ready_calls_immediately_without_floor_or_grace(self):
        r = self.scenario(time=3, stop=6)
        self.assertEqual([(c["action"], c["time"]) for c in r["calls"]], [("--dismiss", 3)])
        self.assertTrue(r["sleeps"])
        self.assertEqual({s["requested"] for s in r["sleeps"]}, {1})

    def test_ready_at_zero_uptime_is_a_real_attempt(self):
        r = self.scenario(time=0, stop=4, events=[dict(at=1, clear_marker=True)])
        self.assertEqual([c["time"] for c in r["calls"]], [0])
        self.assertIn("current-boot", r["marker"])

    def test_boot_gate_releases_on_next_one_second_poll(self):
        r = self.scenario(time=3, stop=9, boot="0", events=[dict(at=6, boot="1")])
        self.assertEqual([c["time"] for c in self.dismissals(r)], [6])
        self.assertTrue(all(c["boot"] == "1" for c in r["native"]))

    def test_stable_display_uses_one_jvm_and_marker_precedes_request(self):
        r = self.scenario()
        self.assertEqual(len(r["calls"]), 1)
        self.assertEqual(r["calls"][0]["action"], "--dismiss")
        self.assertIn("current-boot", r["calls"][0]["marker_before"])
        self.assertIn("status=dismiss-requested", r["attempt"])

    def test_prior_kernel_marker_does_not_suppress_new_boot(self):
        r = self.scenario(marker="100 prior-boot")
        self.assertEqual(len(self.dismissals(r)), 1)
        self.assertIn("current-boot", r["marker"])

    def test_same_boot_restart_does_not_repeat_call(self):
        r = self.scenario(marker="18 current-boot")
        self.assertEqual(r["calls"], [])
        self.assertEqual(r["native"], [])

    def test_dark_screen_waits_for_display_wake(self):
        r = self.scenario(display="off", stop=27, events=[dict(at=24, display="on")])
        self.assertEqual([c["time"] for c in self.dismissals(r)], [24])
        self.assertTrue(all(c["display"] == "on" for c in r["native"]))

    def test_fast_confirmed_display_wake_bypasses_ambiguous_cooldown(self):
        r = self.scenario(stop=26, events=[dict(at=21, display="off"), dict(at=23, display="on")])
        self.assertEqual([c["time"] for c in self.dismissals(r)], [20, 23])

    def test_fast_framework_restart_bypasses_ambiguous_cooldown(self):
        r = self.scenario(stop=26, events=[dict(at=21, boot="0"), dict(at=23, boot="1")])
        self.assertEqual([c["time"] for c in self.dismissals(r)], [20, 23])
        self.assertIn("framework-ready", r["attempt"])

    def test_quickboot_marker_clear_rearms_after_cooldown(self):
        r = self.scenario(stop=38, events=[dict(at=35, clear_marker=True)])
        self.assertEqual([c["time"] for c in self.dismissals(r)], [20, 35])
        self.assertIn("quickboot-marker-cleared", r["attempt"])

    def test_ambiguous_marker_clear_during_cooldown_does_not_repeat(self):
        r = self.scenario(stop=25, events=[dict(at=21, clear_marker=True)])
        self.assertEqual(len(self.dismissals(r)), 1)
        self.assertIn("current-boot", r["marker"])

    def test_unknown_call_error_is_not_blindly_retried(self):
        r = self.scenario(dismiss_responses=[21])
        self.assertEqual(len(self.dismissals(r)), 1)
        self.assertIn("exit=21", r["attempt"])
        self.assertIn("current-boot", r["marker"])

    def test_unknown_process_exit_retains_marker_without_retry(self):
        r = self.scenario(dismiss_responses=[127])
        self.assertEqual(len(self.dismissals(r)), 1)
        self.assertIn("current-boot", r["marker"])

    def test_native_registration_is_polled_each_second_without_extra_jvm(self):
        r = self.scenario(time=3, stop=10, service_ready=False, events=[dict(at=7, service_ready=True)])
        self.assertEqual([c["time"] for c in r["native"]], [3, 4, 5, 6, 7])
        self.assertEqual([(c["action"], c["time"]) for c in r["calls"]], [("--dismiss", 7)])

    def test_native_exit_zero_with_wrong_service_text_is_not_ready(self):
        r = self.scenario(service_responses=[dict(text="Service another.factory: found", rc=0)])
        self.assertEqual(r["calls"], [])

    def test_native_found_text_with_failure_exit_is_not_ready(self):
        r = self.scenario(service_responses=[dict(text="Service com.hkmc.factory: found", rc=1)])
        self.assertEqual(r["calls"], [])

    def test_display_off_during_registry_check_defers_until_next_wake(self):
        r = self.scenario(stop=25, display_off_during_registry_check=True,
                          events=[dict(at=22, display="on")])
        self.assertEqual([c["time"] for c in self.dismissals(r)], [22])
        self.assertIsNone(r["sleeps"][0]["marker"])

    def test_persistent_native_unavailable_stops_after_120_second_window(self):
        r = self.scenario(stop=160, clock_step=10, service_ready=False)
        self.assertEqual(r["calls"], [])
        self.assertEqual([c["time"] for c in r["native"]], list(range(20, 140, 10)))
        self.assertIn("readiness timeout", r["log"])
        self.assertTrue(r["marker"].startswith("140 "), r["marker"])
        self.assertEqual({s["requested"] for s in r["sleeps"]}, {1})

    def test_long_preboot_does_not_consume_readiness_window(self):
        r = self.scenario(time=0, stop=160, clock_step=10, boot="0", service_ready=False,
                          events=[dict(at=130, boot="1"), dict(at=140, service_ready=True)])
        self.assertEqual([c["time"] for c in self.dismissals(r)], [140])
        self.assertNotIn("readiness timeout", r["log"])

    def test_next_confirmed_wake_rearms_after_readiness_timeout(self):
        r = self.scenario(stop=190, clock_step=10, service_ready=False,
                          events=[dict(at=160, display="off"),
                                  dict(at=170, display="on", service_ready=True)])
        self.assertIn("readiness timeout", r["log"])
        self.assertEqual([c["time"] for c in self.dismissals(r)], [170])

    def test_long_dark_screen_does_not_consume_readiness_window(self):
        r = self.scenario(time=0, stop=160, clock_step=10, display="off", service_ready=False,
                          events=[dict(at=130, display="on"), dict(at=140, service_ready=True)])
        self.assertEqual([c["time"] for c in self.dismissals(r)], [140])
        self.assertNotIn("readiness timeout", r["log"])

    def test_ineligible_interval_resets_started_readiness_window(self):
        r = self.scenario(time=0, stop=230, clock_step=10, service_ready=False,
                          events=[dict(at=100, display="off"), dict(at=150, display="on"),
                                  dict(at=210, service_ready=True)])
        self.assertEqual([c["time"] for c in self.dismissals(r)], [210])
        self.assertNotIn("readiness timeout", r["log"])

    def test_no_call_boot_race_retries_next_second(self):
        r = self.scenario(dismiss_responses=[10, 0])
        self.assertEqual([(c["time"], c["rc"]) for c in r["calls"]], [(20, 10), (21, 0)])
        self.assertIsNone(r["sleeps"][0]["marker"])

    def test_no_call_service_race_retries_next_second(self):
        r = self.scenario(dismiss_responses=[11, 0])
        self.assertEqual([(c["time"], c["rc"]) for c in r["calls"]], [(20, 11), (21, 0)])
        self.assertIsNone(r["sleeps"][0]["marker"])

    def test_no_call_race_leaves_restart_retryable(self):
        first = self.scenario(stop=21, dismiss_responses=[11])
        self.assertEqual(len(first["calls"]), 1)
        self.assertIsNone(first["marker"])
        # Restart from persisted session state with the same kernel ID.
        resumed = self.scenario(time=21, stop=23, marker=first["marker"])
        self.assertEqual([c["time"] for c in self.dismissals(resumed)], [21])

    def test_repeated_service_race_at_dismissal_is_bounded_by_time(self):
        r = self.scenario(stop=160, clock_step=10, dismiss_responses=[11])
        self.assertEqual([c["time"] for c in r["calls"]], list(range(20, 140, 10)))
        self.assertIn("readiness timeout", r["log"])
        self.assertTrue(r["marker"].startswith("140 "), r["marker"])

    def test_helper_compatibility_refusal_stops_without_blind_retry(self):
        r = self.scenario(dismiss_responses=[20])
        self.assertEqual(r["rc"], 20)
        self.assertEqual(len(self.dismissals(r)), 1)

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
