#!/usr/bin/env python3
"""Exercise the real USB installer using temporary payloads and host tool fakes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
PACKAGE = "local.hkmc.factory82-4.3.1-neev.zip"
HELPER = "NEEV_STARTUP_NOTICE/neev-consent.jar"
MOCK = r'''
import hashlib, json, os, sys
from pathlib import Path
root = Path(os.environ["NEEV_INSTALL_TEST_ROOT"])
config = json.loads((root / "config.json").read_text())
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / "calls.jsonl").open("a") as f:
    f.write(json.dumps({"tool": tool, "args": args,
                        "classpath": os.environ.get("CLASSPATH", "")}) + "\n")
if tool == "getprop":
    props = {"ro.build.product": config["product"], "ro.board.platform": config["platform"],
             "ro.build.version.release": config["android"], "ro.mobis.targetdir": "/system/onebin/neev_kr",
             "ro.mobis.onebindir": "neev_kr", "sys.boot_completed": "1"}
    print(props.get(args[0], ""))
elif tool == "id":
    print("uid=" + str(config["uid"]) + "(root) gid=0(root)")
elif tool == "md5":
    print(hashlib.md5(Path(args[0]).read_bytes()).hexdigest() + "  " + args[0])
elif tool == "app_process":
    if args != ["/system/bin", "NeevConsent", "--check"]:
        raise AssertionError("unexpected/mutating helper command: " + repr(args))
    cp = os.environ["CLASSPATH"].split(":")
    assert Path(cp[0]).read_bytes() == b"isolated fake helper jar\n"
    assert cp[1:] == ["/system/framework/automotive.jar"]
    (root / "preflight-completed").write_text(str(config["preflight_rc"]))
    print("status=mock-preflight-" + str(config["preflight_rc"]))
    sys.exit(config["preflight_rc"])
elif tool == "nemesis":
    if args == ["version"]:
        print("NEMESIS 1.16.7 fake")
    elif args[:1] == ["install"]:
        assert args[:2] == ["install", "--update"] and len(args) == 3
        assert (root / "preflight-completed").read_text() in ("0", "11")
        assert Path(args[2]).parent == root / "usb"
        print("mock installer result " + str(config["install_rc"]))
        sys.exit(config["install_rc"])
    elif args == ["service", "status", "local.hkmc.factory82/apply"]:
        print("mock service running")
    else:
        raise AssertionError("unexpected nemesis command: " + repr(args))
elif tool in ("am", "sync"):
    pass
elif tool == "dirname":
    print("ERROR: dirname is not available on this vehicle", file=sys.stderr)
    sys.exit(127)
else:
    raise AssertionError(tool)
'''


class InstallerTests(unittest.TestCase):
    def scenario(self, *, corrupt=None, manifest_mode=None, **overrides):
        config = dict(product="NEEV.KOR.0000.V039.001.260902", platform="tcc803x",
                      android="4.4.2", uid=0, preflight_rc=0, install_rc=0)
        config.update(overrides)
        with tempfile.TemporaryDirectory(prefix="neev-installer-test-") as temporary:
            root = Path(temporary)
            usb, tools, stage = root / "usb", root / "tools", root / "stage"
            usb.mkdir()
            tools.mkdir()
            (usb / "NEEV_STARTUP_NOTICE").mkdir()
            (usb / PACKAGE).write_bytes(b"isolated fake install package\n")
            (usb / HELPER).write_bytes(b"isolated fake helper jar\n")
            manifest = [hashlib.md5((usb / rel).read_bytes()).hexdigest() + "  " + rel
                        for rel in (PACKAGE, HELPER)]
            if manifest_mode == "incomplete":
                manifest.pop()
            elif manifest_mode == "duplicate":
                manifest.append(manifest[0])
            elif manifest_mode == "unexpected":
                manifest.append("0" * 32 + "  ../outside")
            (usb / "NEEV_STARTUP_NOTICE/payload.md5").write_text("\n".join(manifest) + "\n")
            if corrupt:
                (usb / corrupt).write_bytes(b"altered after manifest\n")
            (root / "config.json").write_text(json.dumps(config))
            for name in ("getprop", "id", "nemesis", "md5", "app_process", "am", "sync", "dirname"):
                executable = tools / name
                executable.write_text("#!" + sys.executable + "\n" + MOCK)
                executable.chmod(0o700)
            env = os.environ.copy()
            env.update(NEEV_TEST_MODE="1", NEEV_INSTALL_USB=str(usb),
                       NEEV_INSTALL_STAGE=str(stage), NEEV_INSTALL_TEST_ROOT=str(root),
                       PATH=str(tools) + ":/usr/bin:/bin")
            process = subprocess.run(["/bin/sh", str(BASE / "usb-install/NEMESIS.sh")],
                                     env=env, text=True, capture_output=True, timeout=20)
            outputs = list(usb.glob("NEEV_STARTUP_NOTICE_RESULT_*"))
            self.assertEqual(len(outputs), 1, process.stdout + process.stderr)
            output = outputs[0]
            self.assertEqual((usb / "NEEV_STARTUP_NOTICE_LAST_RESULT.txt").read_text().strip(), str(output))
            calls = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]
            self.assertFalse(any(call["tool"] == "dirname" for call in calls), "installer depends on unavailable dirname")
            self.assertFalse(stage.exists(), "staged helper was not cleaned up")
            return dict(rc=process.returncode, status=(output / "STATUS.txt").read_text().strip(),
                        log=(output / "INSTALL.log").read_text(), calls=calls,
                        files={path.name: path.read_text() for path in output.iterdir() if path.is_file()})

    def installs(self, result):
        return [call for call in result["calls"] if call["tool"] == "nemesis" and call["args"][:1] == ["install"]]

    def assert_blocked(self, result, status):
        self.assertNotEqual(result["rc"], 0, result["log"])
        self.assertEqual(result["status"], status, result["log"])
        self.assertEqual(self.installs(result), [])

    def test_success_install_once_after_read_only_check(self):
        result = self.scenario()
        self.assertEqual(result["rc"], 0, result["log"])
        self.assertEqual(result["status"], "INSTALLED_TEST_NEXT_START")
        self.assertEqual(len(self.installs(result)), 1)
        helper = [call for call in result["calls"] if call["tool"] == "app_process"]
        self.assertEqual(len(helper), 1)
        self.assertEqual(helper[0]["args"][-1], "--check")
        self.assertLess(result["calls"].index(helper[0]), result["calls"].index(self.installs(result)[0]))
        self.assertIn("ro.mobis.targetdir=/system/onebin/neev_kr", result["log"])
        self.assertIn("status=mock-preflight-0", result["files"]["PREFLIGHT.txt"])
        self.assertIn("mock service running", result["files"]["SERVICE.txt"])

    def test_preflight_refusal_does_not_replace_old_installation(self):
        result = self.scenario(preflight_rc=20)
        self.assert_blocked(result, "PREFLIGHT_FAILED_RC_20")
        self.assertIn("status=mock-preflight-20", result["log"])

    def test_preflight_missing_service_is_allowed_after_api_validation(self):
        result = self.scenario(preflight_rc=11)
        self.assertEqual(result["rc"], 0, result["log"])
        self.assertEqual(len(self.installs(result)), 1)

    def test_unexpected_helper_failure_blocks_install(self):
        self.assert_blocked(self.scenario(preflight_rc=127), "PREFLIGHT_FAILED_RC_127")

    def test_wrong_product_never_calls_helper_or_installer(self):
        result = self.scenario(product="CVEV.KOR.0000.V039.001.260902")
        self.assert_blocked(result, "WRONG_PRODUCT")
        self.assertFalse(any(call["tool"] == "app_process" for call in result["calls"]))

    def test_wrong_platform_blocks_install(self):
        self.assert_blocked(self.scenario(platform="other"), "WRONG_PLATFORM")

    def test_wrong_android_blocks_install(self):
        self.assert_blocked(self.scenario(android="5.1"), "WRONG_ANDROID")

    def test_nonroot_blocks_install(self):
        self.assert_blocked(self.scenario(uid=2000), "ROOT_REQUIRED")

    def test_install_failure_preserves_return_code_in_status_and_log(self):
        result = self.scenario(install_rc=5)
        self.assertNotEqual(result["rc"], 0)
        self.assertEqual(result["status"], "INSTALL_FAILED_RC_5")
        self.assertEqual(len(self.installs(result)), 1)
        self.assertIn("nemesis_install_exit=5", result["log"])
        self.assertIn("mock installer result 5", result["log"])
        self.assertNotIn("SERVICE.txt", result["files"])

    def test_corrupted_package_blocks_before_preflight(self):
        result = self.scenario(corrupt=PACKAGE)
        self.assert_blocked(result, "PAYLOAD_HASH_MISMATCH")
        self.assertFalse(any(call["tool"] == "app_process" for call in result["calls"]))

    def test_corrupted_helper_blocks_before_preflight(self):
        self.assert_blocked(self.scenario(corrupt=HELPER), "PAYLOAD_HASH_MISMATCH")

    def test_incomplete_manifest_blocks_install(self):
        self.assert_blocked(self.scenario(manifest_mode="incomplete"), "INCOMPLETE_MANIFEST")

    def test_duplicate_manifest_blocks_install(self):
        self.assert_blocked(self.scenario(manifest_mode="duplicate"), "DUPLICATE_MANIFEST")

    def test_unexpected_manifest_path_blocks_install(self):
        self.assert_blocked(self.scenario(manifest_mode="unexpected"), "INVALID_MANIFEST")


if __name__ == "__main__":
    unittest.main(verbosity=2)
