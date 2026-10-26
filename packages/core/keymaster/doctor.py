from __future__ import annotations

import shutil

from . import assets, paths


def import_torch():
    import torch
    return torch


def check(check_id: str, ok: bool, message_key: str, params: dict | None = None) -> dict:
    return {"id": check_id, "ok": ok, "message_key": message_key, "params": params or {}}


def run_doctor(torch_loader=None) -> dict:
    torch_loader = torch_loader or import_torch
    paths.add_upstream_to_path(paths.UPSTREAM_DIR)
    try:
        torch = torch_loader()
    except Exception as exc:
        torch = None
        torch_check = check("torch", False, message_key="core.doctor.torch_missing", params={"detail": f"{type(exc).__name__}: {exc}"})
    else:
        torch_check = check("torch", True, message_key="core.doctor.torch_ok",
                            params={"version": str(torch.__version__), "cuda": str(getattr(torch.version, "cuda", None) or "-")})

    gpu_check = check("gpu", False, message_key="core.doctor.gpu_missing")
    if torch is not None:
        try:
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                gpu_check = check("gpu", True, message_key="core.doctor.gpu_ok",
                                  params={"name": torch.cuda.get_device_name(0),
                                          "memory": round(props.total_memory / 2**30, 1)})
        except Exception as exc:
            gpu_check["params"] = {"detail": f"{type(exc).__name__}: {exc}"}

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        ffmpeg_check = check("ffmpeg", True, message_key="core.doctor.ffmpeg_ok", params={"path": ffmpeg})
    else:
        ffmpeg_check = check("ffmpeg", False, message_key="core.doctor.ffmpeg_missing")

    lacking = assets.missing()
    if lacking:
        weights_check = check("weights", False, message_key="core.doctor.weights_missing", params={"missing": ", ".join(lacking)})
    else:
        weights_check = check("weights", True, message_key="core.doctor.weights_ok", params={"path": str(paths.UPSTREAM_DIR)})

    checks = [gpu_check, ffmpeg_check, weights_check, torch_check]
    return {"event": "doctor", "ok": all(c["ok"] for c in checks), "checks": checks}
