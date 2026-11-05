#!/usr/bin/env python3
"""Build, test and package on the host; never execute a vehicle entry point."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

BASE = Path(__file__).resolve().parent
WORKSPACE = BASE
VERSION = "4.3.1"
PACKAGE_NAME = "local.hkmc.factory82-4.3.1-neev.zip"
USB_NAME = "NEEV_260902_STARTUP_NOTICE_v4.3.1_USB.zip"
REMOVE_NAME = "NEEV_260902_STARTUP_NOTICE_v4.3.1_REMOVE_USB.zip"
SOURCE_NAME = "NEEV_260902_STARTUP_NOTICE_v4.3.1_SOURCE.zip"
ZIP_DATE = (2026, 11, 5, 0, 0, 0)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files_under(folder):
    return [p for p in sorted(folder.rglob("*")) if p.is_file()
            and not any(part.startswith(".") or part == "__pycache__"
                        for part in p.relative_to(folder).parts)
            and p.suffix != ".pyc"]


def archive(path, entries):
    """Canonical order, timestamps and permissions for reproducible archives."""
    seen = set()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for name, content in sorted(entries):
            parts = name.split("/")
            if name in seen or name.startswith("/") or any(p in ("", ".", "..") for p in parts):
                raise ValueError("Invalid or duplicate archive member: " + name)
            seen.add(name)
            info = zipfile.ZipInfo(name, ZIP_DATE)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            out.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(path) as result:
        if result.testzip() is not None:
            raise RuntimeError("Archive CRC verification failed: " + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jdk", type=Path, required=True, help="JDK 17 home directory")
    parser.add_argument("--r8", type=Path, required=True, help="R8 JAR containing com.android.tools.r8.D8")
    args = parser.parse_args()
    jdk, r8 = args.jdk.resolve(), args.r8.resolve()
    for path in [jdk / "bin/javac", jdk / "bin/java", r8]:
        if not path.is_file():
            parser.error("Missing build dependency: " + str(path))
    build = BASE / "build"
    build.mkdir(exist_ok=True)
    classes, testclasses, dex = [build / name for name in ("classes", "test-classes", "dex")]
    for folder in (classes, testclasses, dex):
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir()
    records = []

    def run(label, command):
        print(label, flush=True)
        result = subprocess.run([str(x) for x in command], cwd=BASE, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(result.stdout, end="", flush=True)
        records.append({"check": label, "exit_code": result.returncode, "output": result.stdout})
        (build / "HOST_TEST_RESULTS.txt").write_text("\n".join(
            item["check"] + "\n" + item["output"] for item in records), encoding="utf-8")
        if result.returncode:
            raise RuntimeError(label + " failed; see build/HOST_TEST_RESULTS.txt")

    sources = sorted((BASE / "src").rglob("*.java"))
    tests = sorted((BASE / "tests/java").rglob("*.java"))
    if not sources or not tests or not (BASE / "tests/test_monitor.py").is_file():
        raise RuntimeError("Production sources or required host tests are missing")
    run("Compile production Java 8", [jdk / "bin/javac", "--release", "8", "-encoding", "UTF-8", "-d", classes, *sources])
    run("Compile host Java tests", [jdk / "bin/javac", "--release", "8", "-encoding", "UTF-8", "-cp", classes, "-d", testclasses, *tests])
    run("Java API guard tests", [jdk / "bin/java", "-cp", str(testclasses) + os.pathsep + str(classes), "NeevConsentTest"])
    run("Build Android API 19 DEX", [jdk / "bin/java", "-cp", r8, "com.android.tools.r8.D8", "--release", "--min-api", "19", "--lib", jdk, "--output", dex, *sorted(classes.rglob("*.class"))])
    jar = BASE / "package/lib/neev-consent.jar"
    jar.parent.mkdir(parents=True, exist_ok=True)
    archive(jar, [(p.name, p.read_bytes()) for p in sorted(dex.glob("*.dex"))])
    shells = sorted((BASE / "package").rglob("*.sh")) + sorted((BASE / "usb-remove").rglob("*.sh")) + sorted((BASE / "usb-install").rglob("*.sh"))
    if not shells:
        raise RuntimeError("Package shell scripts are missing")
    for shell in shells:
        run("Shell syntax: " + shell.relative_to(BASE).as_posix(), ["/bin/sh", "-n", shell])
    run("Monitor behavior tests", [sys.executable, BASE / "tests/test_monitor.py"])
    run("Logged USB installer tests", [sys.executable, BASE / "tests/test_installer.py"])
    required = [BASE / "package/NEMESIS.data", BASE / "usb-remove/NEMESIS.data", BASE / "usb-remove/NEMESIS.sh", BASE / "README-KO.txt", BASE / "evidence.json"]
    for path in required:
        if not path.is_file():
            raise RuntimeError("Missing package input: " + str(path))
    dist = WORKSPACE / "dist"
    dist.mkdir(exist_ok=True)
    package = dist / PACKAGE_NAME
    entries = [(p.relative_to(BASE / "package").as_posix(), p.read_bytes()) for p in files_under(BASE / "package")]
    if not any(name == "README-KO.txt" for name, _ in entries):
        entries.append(("README-KO.txt", (BASE / "README-KO.txt").read_bytes()))
    archive(package, entries)
    usb_entries = [(p.relative_to(BASE / "usb-install").as_posix(), p.read_bytes()) for p in files_under(BASE / "usb-install")]
    usb_entries += [(PACKAGE_NAME, package.read_bytes()),
                    ("README-KO.txt", (BASE / "README-KO.txt").read_bytes()),
                    ("NEEV_STARTUP_NOTICE/neev-consent.jar", jar.read_bytes())]
    payload_hashes = (hashlib.md5(package.read_bytes()).hexdigest() + "  " + PACKAGE_NAME + "\n" +
                      hashlib.md5(jar.read_bytes()).hexdigest() + "  NEEV_STARTUP_NOTICE/neev-consent.jar\n").encode()
    usb_entries.append(("NEEV_STARTUP_NOTICE/payload.md5", payload_hashes))
    archive(dist / USB_NAME, usb_entries)
    remove_entries = [(p.relative_to(BASE / "usb-remove").as_posix(), p.read_bytes()) for p in files_under(BASE / "usb-remove")]
    remove_entries.append(("README-KO.txt", (BASE / "README-KO.txt").read_bytes()))
    archive(dist / REMOVE_NAME, remove_entries)
    source_entries = []
    for dirname in ("src", "tests", "package", "usb-remove", "usb-install"):
        for path in files_under(BASE / dirname):
            if path.suffix not in (".jar", ".class", ".dex"):
                source_entries.append((path.relative_to(BASE).as_posix(), path.read_bytes()))
    for name in ("build.py", "README.md", "README-KO.txt", "evidence.json", "LICENSE", "NOTICE.txt", ".gitignore"):
        source_entries.append((name, (BASE / name).read_bytes()))
    archive(dist / SOURCE_NAME, source_entries)
    artifact_names = (PACKAGE_NAME, USB_NAME, REMOVE_NAME, SOURCE_NAME)
    hashes = {name: digest(dist / name) for name in artifact_names}
    report = {
        "version": VERSION, "target": "NEEV.KOR.0000.V039.001.260902",
        "java_release": 8, "android_min_api": 19,
        "jdk_release_sha256": digest(jdk / "release"), "r8_sha256": digest(r8),
        "helper_jar_sha256": digest(jar), "host_checks": records,
        "vehicle_tested": False, "artifacts_sha256": hashes,
        "deterministic_archive_timestamp": list(ZIP_DATE),
    }
    (build / "BUILD_RESULT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    release = BASE / "release"
    release.mkdir(parents=True, exist_ok=True)
    for name in artifact_names:
        shutil.copyfile(dist / name, release / name)
        checksum = hashes[name] + "  " + name + "\n"
        (dist / (name + ".sha256")).write_text(checksum)
        (release / (name + ".sha256")).write_text(checksum)
    for path in [BASE / "README-KO.txt", BASE / "evidence.json", build / "BUILD_RESULT.json", build / "HOST_TEST_RESULTS.txt"]:
        shutil.copyfile(path, release / path.name)
    (release / "SHA256SUMS.txt").write_text("".join(hashes[name] + "  " + name + "\n" for name in artifact_names))
    for name in artifact_names:
        if digest(release / name) != hashes[name]:
            raise RuntimeError("Release copy verification failed: " + name)
    print("Verified release: " + str(release))
    print(json.dumps(hashes, indent=2))


if __name__ == "__main__":
    main()
