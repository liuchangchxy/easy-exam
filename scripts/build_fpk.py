#!/usr/bin/env python3
"""Build tool for fnOS FPK packages (EasyExam).

Supports:
1. Pure Python packaging engine (zero external tools required, cross-platform)
2. Official fnpack CLI integration (if fnpack is installed or downloaded)
3. Bundled offline Docker image packaging (--bundle-image)
4. Thin package mode (--thin)
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP_DIR = REPO_ROOT / "fpk" / "easy-exam"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "dist"


def parse_manifest(manifest_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest file missing at {manifest_path}")
    for raw in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def validate_fpk_sources(app_dir: Path) -> dict[str, str]:
    manifest_path = app_dir / "manifest"
    manifest = parse_manifest(manifest_path)

    required_fields = ["appname", "version", "display_name", "platform", "source", "service_port"]
    for field in required_fields:
        if field not in manifest:
            raise ValueError(f"manifest missing required field: {field}")

    required_paths = [
        app_dir / "config" / "privilege",
        app_dir / "config" / "resource",
        app_dir / "ICON.PNG",
        app_dir / "ICON_256.PNG",
        app_dir / "cmd" / "main",
        app_dir / "app" / "docker" / "docker-compose.yaml",
        app_dir / "app" / "ui" / "config",
    ]
    for p in required_paths:
        if not p.is_file():
            raise FileNotFoundError(f"Required FPK component missing: {p}")

    return manifest


def build_app_tgz(app_dir: Path) -> bytes:
    """Build in-memory gzipped tar archive of app/ and config/ directories."""
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tar:
        # 1. Add app directory contents
        app_sub = app_dir / "app"
        if app_sub.is_dir():
            for item in sorted(app_sub.iterdir()):
                tar.add(item, arcname=item.name, recursive=True)

        # 2. Add config directory contents (as expected by fnpack)
        config_sub = app_dir / "config"
        if config_sub.is_dir():
            tar.add(config_sub, arcname="config", recursive=True)

    return bio.getvalue()


def package_fpk_python(app_dir: Path, output_file: Path) -> Path:
    """Package FPK using standard Python tarfile library, matching fnpack format."""
    manifest_path = app_dir / "manifest"
    manifest_content = manifest_path.read_text(encoding="utf-8")

    # Filter out existing checksum lines if any
    manifest_lines = [line for line in manifest_content.splitlines() if not line.strip().startswith("checksum")]

    # 1. Build app.tgz and compute MD5
    app_tgz_bytes = build_app_tgz(app_dir)
    checksum = hashlib.md5(app_tgz_bytes).hexdigest()

    manifest_lines.append(f"checksum              = {checksum}")
    final_manifest = "\n".join(manifest_lines) + "\n"

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(output_file, mode="w:gz") as tar:
        # Add app.tgz
        tinfo = tarfile.TarInfo(name="app.tgz")
        tinfo.size = len(app_tgz_bytes)
        tinfo.mode = 0o666
        tar.addfile(tinfo, io.BytesIO(app_tgz_bytes))

        # Add cmd directory with executable permissions
        cmd_dir = app_dir / "cmd"
        if cmd_dir.is_dir():
            dinfo = tarfile.TarInfo(name="cmd")
            dinfo.type = tarfile.DIRTYPE
            dinfo.mode = 0o777
            tar.addfile(dinfo)

            for item in sorted(cmd_dir.iterdir()):
                if item.name.startswith("."):
                    continue
                content = item.read_bytes().replace(b"\r\n", b"\n")
                finfo = tarfile.TarInfo(name=f"cmd/{item.name}")
                finfo.size = len(content)
                finfo.mode = 0o755  # Executable
                tar.addfile(finfo, io.BytesIO(content))

        # Add config directory
        config_dir = app_dir / "config"
        if config_dir.is_dir():
            dinfo = tarfile.TarInfo(name="config")
            dinfo.type = tarfile.DIRTYPE
            dinfo.mode = 0o777
            tar.addfile(dinfo)

            for item in sorted(config_dir.iterdir()):
                if item.name.startswith("."):
                    continue
                content = item.read_bytes().replace(b"\r\n", b"\n")
                finfo = tarfile.TarInfo(name=f"config/{item.name}")
                finfo.size = len(content)
                finfo.mode = 0o666
                tar.addfile(finfo, io.BytesIO(content))

        # Add wizard directory
        wizard_dir = app_dir / "wizard"
        dinfo = tarfile.TarInfo(name="wizard")
        dinfo.type = tarfile.DIRTYPE
        dinfo.mode = 0o777
        tar.addfile(dinfo)
        if wizard_dir.is_dir():
            for item in sorted(wizard_dir.iterdir()):
                if item.name.startswith("."):
                    continue
                content = item.read_bytes()
                finfo = tarfile.TarInfo(name=f"wizard/{item.name}")
                finfo.size = len(content)
                finfo.mode = 0o666
                tar.addfile(finfo, io.BytesIO(content))

        # Add icons
        for icon_name in ["ICON.PNG", "ICON_256.PNG"]:
            icon_file = app_dir / icon_name
            if icon_file.is_file():
                icon_bytes = icon_file.read_bytes()
                iinfo = tarfile.TarInfo(name=icon_name)
                iinfo.size = len(icon_bytes)
                iinfo.mode = 0o666
                tar.addfile(iinfo, io.BytesIO(icon_bytes))

        # Add final manifest with checksum
        mbytes = final_manifest.encode("utf-8")
        minfo = tarfile.TarInfo(name="manifest")
        minfo.size = len(mbytes)
        minfo.mode = 0o666
        tar.addfile(minfo, io.BytesIO(mbytes))

    return output_file


def find_fnpack_cli() -> str | None:
    # 1. System PATH
    found = shutil.which("fnpack")
    if found:
        return found

    # 2. Local project or scratch paths
    candidates = [
        REPO_ROOT / ".tools" / "fnpack.exe",
        REPO_ROOT / ".tools" / "fnpack",
        Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "antigravity" / "brain" / "7e22fbfa-84e1-44a1-9139-54b431530624" / "scratch" / "fnpack.exe",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def package_fpk_fnpack(fnpack_bin: str, app_dir: Path, output_file: Path) -> Path:
    cmd = [fnpack_bin, "build", "--directory", str(app_dir)]
    print(f"Running fnpack: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"fnpack build failed: {res.stderr or res.stdout}")

    manifest = parse_manifest(app_dir / "manifest")
    appname = manifest.get("appname", "easy-exam")
    default_fpk = REPO_ROOT / f"{appname}.fpk"
    if default_fpk.is_file() and default_fpk != output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(default_fpk), str(output_file))

    return output_file


def prepare_bundled_image(app_dir: Path, image_tag: str) -> Path:
    """Save Docker image to app/images/{image_name}.tar.gz for self-contained FPK."""
    images_dir = app_dir / "app" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    ver = image_tag.split(":")[-1]
    out_archive = images_dir / f"easy-exam-{ver}.tar.gz"

    print(f"[EXPORT] Exporting self-contained Docker image '{image_tag}' to {out_archive}...")
    save_cmd = ["docker", "save", image_tag]
    save_proc = subprocess.Popen(save_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    import gzip
    with open(out_archive, "wb") as f_out:
        with gzip.GzipFile(fileobj=f_out, mode="wb") as gz_out:
            shutil.copyfileobj(save_proc.stdout, gz_out)

    save_proc.stdout.close()
    save_proc.wait()
    if save_proc.returncode != 0:
        err = save_proc.stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"docker save failed: {err}")

    size_mb = out_archive.stat().st_size / (1024 * 1024)
    print(f"[OK] Docker image exported successfully ({size_mb:.1f} MB)")
    return out_archive


def build_fpk(
    app_dir: Path = DEFAULT_APP_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    bundle_image: bool = False,
    engine: str = "auto",
) -> Path:
    manifest = validate_fpk_sources(app_dir)
    appname = manifest["appname"]
    version = manifest["version"]

    output_file = output_dir / f"{appname}-{version}.fpk"
    bundled_image_path = None

    try:
        if bundle_image:
            image_tag = f"ailm32442/easy-exam:{version}"
            # Verify if image exists locally, build if missing
            check = subprocess.run(
                ["docker", "image", "inspect", image_tag],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if check.returncode != 0:
                print(f"[BUILD] Image {image_tag} not found locally, building from Dockerfile...")
                b_res = subprocess.run(
                    ["docker", "build", "-t", image_tag, "."],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if b_res.returncode != 0:
                    raise RuntimeError(f"docker build failed: {b_res.stderr or b_res.stdout}")

            bundled_image_path = prepare_bundled_image(app_dir, image_tag)

        fnpack_bin = find_fnpack_cli() if engine in ["auto", "fnpack"] else None
        if fnpack_bin and engine != "python":
            print(f"[BUILD] Using official fnpack CLI at: {fnpack_bin}")
            target = package_fpk_fnpack(fnpack_bin, app_dir, output_file)
        else:
            print("[BUILD] Using built-in pure Python packaging engine")
            target = package_fpk_python(app_dir, output_file)

        print(f"[SUCCESS] Successfully generated FPK: {target} ({target.stat().st_size / 1024:.1f} KB)")
        return target
    finally:
        # Clean up temporary bundled image inside source directory after packaging
        if bundled_image_path and bundled_image_path.is_file():
            bundled_image_path.unlink()
            parent = bundled_image_path.parent
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()


def main():
    parser = argparse.ArgumentParser(description="EasyExam fnOS FPK Builder")
    parser.add_argument("--app-dir", type=Path, default=DEFAULT_APP_DIR, help="Path to FPK source directory")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--bundle-image", action="store_true", help="Bundle Docker image inside FPK (self-contained)")
    parser.add_argument("--thin", action="store_true", help="Build lightweight FPK without bundled Docker image")
    parser.add_argument("--engine", choices=["auto", "fnpack", "python"], default="auto", help="Packaging engine")

    args = parser.parse_args()
    bundle = args.bundle_image and not args.thin

    build_fpk(
        app_dir=args.app_dir,
        output_dir=args.output_dir,
        bundle_image=bundle,
        engine=args.engine,
    )


if __name__ == "__main__":
    main()
