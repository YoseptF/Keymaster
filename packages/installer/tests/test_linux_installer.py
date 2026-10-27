from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import helpers

WORKSPACE: helpers.Workspace | None = None


def setUpModule() -> None:
    global WORKSPACE
    WORKSPACE = helpers.Workspace()


def tearDownModule() -> None:
    if WORKSPACE:
        WORKSPACE.cleanup()


def snapshot(root: Path, skip: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if skip not in p.parents and p != skip}


@unittest.skipIf(sys.platform == "win32" or not shutil.which("bash"), "the Linux installer needs bash")
class LinuxInstallerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="keymaster-linux-installer-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.prefix = self.home / ".local" / "share" / "keymaster"
        self.settings = self.home / ".config" / "keymaster" / "settings.json"
        self.bin = self.tmp / "fakebin"
        self.log = self.tmp / "log.txt"
        self.log.write_text("")
        self.blender = helpers.executable(self.tmp / "blender" / "blender", helpers.FAKE_BLENDER)
        self.blender_profile = self.home / "blender-profile"
        self.ofx = self.tmp / "ofx"
        self.gpu(True)

    def gpu(self, present: bool) -> None:
        text = "#!/bin/sh\necho 'NVIDIA GeForce Fake 4090'\n" if present else "#!/bin/sh\nexit 9\n"
        helpers.executable(self.bin / "nvidia-smi", text)

    def env(self, **extra: str) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("KEYMASTER_", "XDG_", "UV_", "BLENDER_")) and k not in ("LC_ALL", "LC_MESSAGES", "LANG", "OFX_PLUGIN_DIR")}
        env.update({
            "HOME": str(self.home),
            "PATH": f"{self.bin}{os.pathsep}{env.get('PATH', '')}",
            "LANG": "en_US.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "KM_LOG": str(self.log),
            "KM_PY": sys.executable,
            "KM_FAKE_CORE": str(helpers.FAKE_CORE),
            "KEYMASTER_INSTALLER_UV": "download",
            "KEYMASTER_INSTALLER_UV_URL": WORKSPACE.downloads["KEYMASTER_INSTALLER_UV_URL"],
            "KEYMASTER_INSTALLER_UV_SHA256": WORKSPACE.downloads["KEYMASTER_INSTALLER_UV_SHA256"],
            "KEYMASTER_INSTALLER_FFMPEG_URL": WORKSPACE.downloads["KEYMASTER_INSTALLER_FFMPEG_URL"],
            "KEYMASTER_INSTALLER_FFMPEG_SHA256": WORKSPACE.downloads["KEYMASTER_INSTALLER_FFMPEG_SHA256"],
            "KEYMASTER_INSTALLER_FFMPEG_LICENSE_URL": WORKSPACE.downloads["KEYMASTER_INSTALLER_FFMPEG_LICENSE_URL"],
            "KEYMASTER_INSTALLER_FFMPEG_LICENSE_SHA256": WORKSPACE.downloads["KEYMASTER_INSTALLER_FFMPEG_LICENSE_SHA256"],
            "KEYMASTER_INSTALLER_SUDO": str(self.tmp / "no-sudo"),
            "KEYMASTER_INSTALLER_BLENDER": str(self.blender),
            "KEYMASTER_INSTALLER_OFX_HOSTS": "",
            "BLENDER_USER_RESOURCES": str(self.blender_profile),
            "OFX_PLUGIN_DIR": str(self.ofx),
        })
        env.update(extra)
        return env

    def run_installer(self, *args: str, script: Path | None = None, **extra: str) -> subprocess.CompletedProcess:
        cmd = ["bash", str(script or WORKSPACE.linux), *args]
        return subprocess.run(cmd, env=self.env(**extra), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)

    def installed(self, *args: str, **extra: str) -> subprocess.CompletedProcess:
        result = self.run_installer(*args, **extra)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def stored_settings(self) -> dict:
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def test_full_install_then_uninstall_leaves_nothing(self) -> None:
        before = snapshot(self.home, self.blender_profile)
        result = self.installed("--yes", "--components", "core,app,blender,openfx", "--bundled-ffmpeg")
        out = result.stdout
        self.assertIn("Keymaster 0.0.0-test.1 installer", out)
        self.assertIn("Graphics card: NVIDIA GeForce Fake 4090", out)
        self.assertIn("Keymaster is ready.", out)
        python = self.prefix / "core" / ".venv" / "bin" / "python"
        self.assertEqual(self.stored_settings(), {"python": str(python), "core": str(self.prefix / "core"),
                                                  "ffmpeg": str(self.prefix / "ffmpeg" / "ffmpeg")})
        self.assertTrue((self.prefix / "core" / "keymaster" / "cli.py").is_file())
        self.assertTrue((self.prefix / "bin" / "uv").is_file())
        self.assertEqual(subprocess.run([str(self.prefix / "ffmpeg" / "ffmpeg")], capture_output=True, text=True).stdout, "fake ffmpeg\n")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", (self.prefix / "ffmpeg" / "LICENSE").read_text())
        self.assertFalse((self.prefix / "cache").exists())
        log = self.log.read_text()
        wheel = self.prefix / "wheels" / "utils3d-1.7-py3-none-any.whl"
        self.assertIn(f"  | utils3d @ file://{wheel}", log)
        self.assertNotIn("git+", log)
        self.assertIn("--index-url https://download.pytorch.org/whl/cu128", log)
        self.assertIn("uv pip install --python", log)
        launcher = self.home / ".local" / "bin" / "keymaster-app"
        desktop = self.home / ".local" / "share" / "applications" / "keymaster-app.desktop"
        self.assertIn(str(python), launcher.read_text())
        self.assertIn("Exec=", desktop.read_text())
        self.assertIn(f"Start the app from your applications menu or with: {launcher}", out)
        extension = self.blender_profile / "extensions" / "user_default" / "keymaster"
        self.assertTrue((extension / "blender_manifest.toml").is_file())
        self.assertIn("Adding Keymaster to Blender 5.1...", out)
        self.assertTrue((self.ofx / "Keymaster.ofx.bundle" / "Contents" / "Linux-x86-64" / "Keymaster.ofx").is_file())
        self.assertIn(f"bash {self.prefix}/uninstall.sh", out)

        result = self.run_installer("--yes", script=self.prefix / "uninstall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Keymaster was removed.", result.stdout)
        self.assertFalse(extension.exists())
        self.assertFalse((self.ofx / "Keymaster.ofx.bundle").exists())
        self.assertEqual(snapshot(self.home, self.blender_profile), before)

    def test_defaults_follow_detection(self) -> None:
        host = self.tmp / "resolve"
        host.write_text("")
        result = self.installed(KEYMASTER_INSTALLER_OFX_HOSTS=f"{self.tmp / 'nuke'}:{host}")
        self.assertIn("Components: Keymaster core (required), Standalone app, Blender, DaVinci Resolve and Nuke (OpenFX)", result.stdout)
        self.assertTrue((self.ofx / "Keymaster.ofx.bundle").is_dir())
        self.assertTrue((self.blender_profile / "extensions" / "user_default" / "keymaster").is_dir())

    def test_nothing_detected_installs_core_and_app(self) -> None:
        result = self.installed(KEYMASTER_INSTALLER_BLENDER="")
        self.assertIn("Components: Keymaster core (required), Standalone app\n", result.stdout)
        self.assertFalse(self.ofx.exists())
        self.assertFalse(self.blender_profile.exists())

    def test_old_blender_is_skipped(self) -> None:
        result = self.installed("--components", "blender", KM_BLENDER_VERSION="4.2.1")
        self.assertIn("Blender 4.2 is older than 5.0, skipped.", result.stdout)
        self.assertIn("No Blender 5 was found, so the Blender panel was skipped.", result.stdout)
        self.assertFalse(self.blender_profile.exists())

    def test_openfx_is_skipped_without_admin_rights(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root can write anywhere")
        self.ofx.mkdir()
        self.ofx.chmod(0o555)
        self.addCleanup(self.ofx.chmod, 0o755)
        result = self.installed("--components", "openfx")
        self.assertIn("The OpenFX plugin was not copied because that needs administrator rights. To add it later, run:", result.stdout)
        self.assertIn(f"cp -R '{self.prefix}/openfx/Keymaster.ofx.bundle' '{self.ofx}/'", result.stdout)
        self.assertFalse((self.ofx / "Keymaster.ofx.bundle").exists())
        self.assertNotIn("openfx=", (self.prefix / ".keymaster-install").read_text())
        self.assertNotIn("Restart DaVinci Resolve", result.stdout)

    def test_system_ffmpeg_is_used_when_present(self) -> None:
        helpers.executable(self.bin / "ffmpeg", "#!/bin/sh\n")
        result = self.installed("--components", "core")
        self.assertIn(f"Using the ffmpeg already on this computer: {self.bin / 'ffmpeg'}", result.stdout)
        self.assertFalse((self.prefix / "ffmpeg").exists())
        self.assertNotIn("ffmpeg", self.stored_settings())

    def test_existing_uv_is_used(self) -> None:
        uv = helpers.executable(self.bin / "uv", helpers.FAKE_UV)
        self.installed("--components", "core", KEYMASTER_INSTALLER_UV="")
        self.assertFalse((self.prefix / "bin" / "uv").exists())
        self.assertTrue(uv.is_file())

    def test_spanish_messages(self) -> None:
        self.gpu(False)
        result = self.installed("--components", "core", LANG="es_AR.UTF-8")
        self.assertIn("No se encontró una tarjeta gráfica o un driver de NVIDIA.", result.stderr)
        self.assertIn("Keymaster está listo.", result.stdout)
        result = self.run_installer("--uninstall", "--yes", KEYMASTER_LANGUAGE="es-419")
        self.assertIn("Keymaster se quitó.", result.stdout)

    def test_reinstall_keeps_the_environment_and_models(self) -> None:
        self.installed("--components", "core")
        weights = self.prefix / "core" / "upstream" / "weights" / "corridorkey_v2.safetensors"
        weights.write_bytes(b"model")
        marker = self.prefix / "core" / ".venv" / "marker"
        marker.write_text("kept")
        (self.prefix / "core" / "stale.py").write_text("")
        self.installed("--components", "core")
        self.assertEqual(weights.read_bytes(), b"model")
        self.assertEqual(marker.read_text(), "kept")
        self.assertFalse((self.prefix / "core" / "stale.py").exists())

    def test_existing_settings_are_kept_on_uninstall(self) -> None:
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({"language": "es-419", "custom": 1}))
        self.installed("--components", "core", "--prefix", str(self.tmp / "elsewhere"))
        stored = self.stored_settings()
        self.assertEqual((stored["language"], stored["custom"], stored["core"]), ("es-419", 1, str(self.tmp / "elsewhere" / "core")))
        result = self.run_installer("--uninstall", "--prefix", str(self.tmp / "elsewhere"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.tmp / "elsewhere").exists())
        self.assertEqual(self.stored_settings()["custom"], 1)

    def test_core_failure_is_reported(self) -> None:
        result = self.run_installer("--components", "core", KM_FAKE_UV_FAIL="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"The Keymaster core could not be installed. Check your internet connection and that you have about 15 GB free, then run the installer again. The details are in {self.prefix}/logs/install.log.", result.stderr)

    def test_checksum_mismatch_stops_the_install(self) -> None:
        result = self.run_installer("--components", "core", KEYMASTER_INSTALLER_UV_SHA256="0" * 64)
        self.assertEqual(result.returncode, 1)
        self.assertIn("did not match its expected checksum", result.stderr)
        self.assertFalse((self.prefix / "bin" / "uv").exists())

    def test_bad_arguments(self) -> None:
        result = self.run_installer("--components", "core,maya")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown component: maya.", result.stderr)
        self.assertFalse(self.prefix.exists())
        result = self.run_installer("--frobnicate")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown option: --frobnicate.", result.stderr)

    def test_uninstall_without_install(self) -> None:
        result = self.run_installer("--uninstall")
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"Keymaster is not installed in {self.prefix}.", result.stderr)

    def test_help_in_both_languages(self) -> None:
        self.assertIn("--components LIST", self.run_installer("--help").stdout)
        self.assertIn("--components LISTA", self.run_installer("--help", LANG="es_MX.UTF-8").stdout)


@unittest.skipUnless(shutil.which("blender") and sys.platform != "win32", "blender is not on PATH")
class RealBlenderTest(LinuxInstallerTest):
    def setUp(self) -> None:
        super().setUp()
        self.blender = Path(shutil.which("blender"))

    def test_extension_goes_into_a_throwaway_profile(self) -> None:
        result = self.installed("--components", "blender")
        extension = self.blender_profile / "extensions" / "user_default" / "keymaster"
        self.assertTrue((extension / "blender_manifest.toml").is_file(), result.stdout + self.log.read_text())
        check = subprocess.run([str(self.blender), "--background", "--python-expr",
                                "import bpy; print('ENABLED', 'bl_ext.user_default.keymaster' in bpy.context.preferences.addons)"],
                               env=self.env(), capture_output=True, text=True, timeout=120)
        self.assertIn("ENABLED True", check.stdout)
        result = self.run_installer("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(extension.exists())


for name in [n for n in dir(LinuxInstallerTest) if n.startswith("test_")]:
    setattr(RealBlenderTest, name, None)
