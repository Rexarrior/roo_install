#!/usr/bin/env python3
"""Install the C++ Russia userver workshop environment on Ubuntu 24.04.

The installer intentionally targets Ubuntu 24.04 only. It installs SourceCraft
(Code Assistant) instead of Roo Code, copies agent rules into a workspace,
installs system dependencies, clones the workshop repository, and verifies that
both frontend and backend build successfully.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path


SOURCECRAFT_VSIX_URL = (
    "https://storage.yandexcloud.net/yandex-code-assistant/plugins/vscode/"
    "yandex-code-assist.vsix"
)
SOURCECRAFT_CLI_INSTALL_URL = "https://s3.yandexcloud.net/sourcecraft-cli/install.sh"
NODE_SOURCE_SETUP_URL = "https://deb.nodesource.com/setup_current.x"
TEMPLATE_REPO_URL = "https://github.com/Malevrovich/cpprussia2026_template.git"
TEMPLATE_REPO_DIR_NAME = "cpprussia2026_template"
UBUNTU_VERSION = "24.04"


class InstallerError(RuntimeError):
    """Raised when installation cannot continue."""


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
) -> str:
    """Run a command and fail with a readable diagnostic on errors."""
    printable_command = " ".join(command)
    location = f" in {cwd}" if cwd else ""
    print(f"\n$ {printable_command}{location}")

    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
        )
    except subprocess.CalledProcessError as exc:
        message = [f"Command failed: {printable_command}"]
        if cwd:
            message.append(f"Working directory: {cwd}")
        if capture_output:
            if exc.stdout:
                message.append(f"stdout:\n{exc.stdout}")
            if exc.stderr:
                message.append(f"stderr:\n{exc.stderr}")
        raise InstallerError("\n".join(message)) from exc

    return result.stdout.strip() if capture_output and result.stdout else ""


def run_shell(command: str, *, cwd: Path | None = None) -> None:
    """Run a shell pipeline. Used only for trusted install scripts."""
    run_command(["bash", "-lc", command], cwd=cwd)


def require_command(name: str) -> None:
    if not shutil.which(name):
        raise InstallerError(f"Required command is not available after installation: {name}")


def sudo_prefix() -> list[str]:
    return [] if os.geteuid() == 0 else ["sudo"]


def apt_install(packages: list[str]) -> None:
    run_command(sudo_prefix() + ["apt-get", "install", "-y", *packages])


@contextmanager
def prevent_service_autostart_during_apt():
    """Prevent package post-install scripts from auto-starting daemons.

    Some workshop hosts already have ports 80/443 occupied by existing services.
    Installing nginx must still succeed in that case, so we temporarily add the
    standard Debian/Ubuntu policy hook that tells invoke-rc.d not to start
    services automatically. Services required by this installer are started
    explicitly later.
    """
    policy_path = Path("/usr/sbin/policy-rc.d")
    created_policy = False

    if not policy_path.exists():
        run_shell(
            "printf '%s\n' '#!/bin/sh' 'exit 101' "
            "| sudo tee /usr/sbin/policy-rc.d > /dev/null"
        )
        run_command(sudo_prefix() + ["chmod", "755", "/usr/sbin/policy-rc.d"])
        created_policy = True

    try:
        yield
    finally:
        if created_policy:
            run_command(sudo_prefix() + ["rm", "-f", "/usr/sbin/policy-rc.d"])


def parse_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    path = Path("/etc/os-release")
    if not path.exists():
        raise InstallerError("/etc/os-release was not found; this installer supports Ubuntu 24.04 only")

    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key] = value.strip().strip('"')
    return data


def ensure_ubuntu_24() -> None:
    os_release = parse_os_release()
    os_id = os_release.get("ID", "")
    version_id = os_release.get("VERSION_ID", "")
    if os_id != "ubuntu" or version_id != UBUNTU_VERSION:
        raise InstallerError(
            f"Unsupported OS: ID={os_id!r}, VERSION_ID={version_id!r}. "
            f"This installer is intended for Ubuntu {UBUNTU_VERSION}."
        )
    print(f"Detected Ubuntu {UBUNTU_VERSION}")


def install_base_packages() -> None:
    print("Installing base tools and C++/userver build dependencies...")
    run_command(sudo_prefix() + ["apt-get", "update"])
    with prevent_service_autostart_during_apt():
        apt_install(
            [
                "apt-transport-https",
                "bash",
                "build-essential",
                "ca-certificates",
                "clang",
                "cmake",
                "curl",
                "g++",
                "gcc",
                "git",
                "gnupg",
                "libboost-all-dev",
                "libcrypto++-dev",
                "libcurl4-openssl-dev",
                "libev-dev",
                "libfmt-dev",
                "libhttp-parser-dev",
                "libicu-dev",
                "libnghttp2-dev",
                "libpcre2-dev",
                "libpq-dev",
                "libssl-dev",
                "libyaml-cpp-dev",
                "libzstd-dev",
                "lsb-release",
                "make",
                "nginx",
                "ninja-build",
                "pkg-config",
                "postgresql",
                "postgresql-contrib",
                "python3",
                "python3-pip",
                "python3-venv",
                "unzip",
                "wget",
            ]
        )


def install_nodejs_latest() -> None:
    print("Installing latest Node.js from NodeSource...")
    run_shell(f"curl -fsSL {NODE_SOURCE_SETUP_URL} | sudo -E bash -")
    apt_install(["nodejs"])
    require_command("node")
    require_command("npm")
    print(run_command(["node", "--version"], capture_output=True))
    print(run_command(["npm", "--version"], capture_output=True))


def install_docker() -> None:
    print("Installing Docker Engine and Docker Compose plugin from the official Docker repository...")
    run_command(sudo_prefix() + ["install", "-m", "0755", "-d", "/etc/apt/keyrings"])
    run_command(sudo_prefix() + ["rm", "-f", "/etc/apt/keyrings/docker.gpg"])
    run_shell(
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg "
        "| sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg"
    )
    run_command(sudo_prefix() + ["chmod", "a+r", "/etc/apt/keyrings/docker.gpg"])
    run_shell(
        "echo \"deb [arch=$(dpkg --print-architecture) "
        "signed-by=/etc/apt/keyrings/docker.gpg] "
        "https://download.docker.com/linux/ubuntu "
        "$(. /etc/os-release && echo $VERSION_CODENAME) stable\" "
        "| sudo tee /etc/apt/sources.list.d/docker.list > /dev/null"
    )
    run_command(sudo_prefix() + ["apt-get", "update"])
    apt_install(["docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin", "docker-compose-plugin"])
    require_command("docker")
    run_command(["docker", "--version"])
    run_command(["docker", "compose", "version"])


def ensure_postgresql_running() -> None:
    print("Enabling local PostgreSQL service...")
    run_command(sudo_prefix() + ["systemctl", "enable", "--now", "postgresql"])
    run_command(sudo_prefix() + ["systemctl", "status", "postgresql", "--no-pager"])


def parse_version_tuple(output: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", output)
    if not match:
        raise InstallerError(f"Could not parse version from: {output}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def require_min_version(command: str, minimum: tuple[int, int, int]) -> None:
    output = run_command([command, "--version"], capture_output=True)
    actual = parse_version_tuple(output)
    if actual < minimum:
        raise InstallerError(
            f"{command} version {actual[0]}.{actual[1]}.{actual[2]} is too old; "
            f"required >= {minimum[0]}.{minimum[1]}.{minimum[2]}"
        )
    print(f"{command} version OK: {actual[0]}.{actual[1]}.{actual[2]}")


def validate_compilers() -> None:
    print("Validating compiler versions...")
    require_min_version("gcc", (11, 2, 0))
    require_min_version("g++", (11, 2, 0))
    require_min_version("clang", (16, 0, 0))


def install_vscode_if_missing() -> None:
    if shutil.which("code"):
        print("VS Code CLI is already available")
        return

    print("Installing VS Code because the `code` CLI was not found...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        deb_path = Path(tmp_dir) / "vscode.deb"
        run_command(["wget", "https://go.microsoft.com/fwlink/?LinkID=760868", "-O", str(deb_path)])
        run_command(sudo_prefix() + ["apt-get", "install", "-y", str(deb_path)])
    require_command("code")


def find_sourcecraft_binary() -> str:
    candidates = [
        shutil.which("src"),
        str(Path.home() / "sourcecraft" / "bin" / "src"),
        str(Path.home() / ".local" / "bin" / "src"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise InstallerError(
        "SourceCraft CLI was installed, but the `src` binary was not found. "
        "Expected it in PATH or in ~/sourcecraft/bin/src."
    )


def install_sourcecraft() -> None:
    print("Installing SourceCraft Code Assistant VS Code extension and CLI...")
    install_vscode_if_missing()
    with tempfile.TemporaryDirectory() as tmp_dir:
        vsix_path = Path(tmp_dir) / "yandex-code-assist.vsix"
        run_command(["wget", SOURCECRAFT_VSIX_URL, "-O", str(vsix_path)])
        run_command(["code", "--install-extension", str(vsix_path), "--force"])

    run_shell(f"curl -fsSL {SOURCECRAFT_CLI_INSTALL_URL} | sh")
    src_binary = find_sourcecraft_binary()
    run_command([src_binary, "code", "install"])


def copy_rules(config_folder: Path, target_folder: Path) -> None:
    print(f"Copying agent rules from {config_folder} to {target_folder}...")
    if not config_folder.exists():
        raise InstallerError(f"Rules folder does not exist: {config_folder}")
    target_folder.mkdir(parents=True, exist_ok=True)

    for item in config_folder.iterdir():
        destination = target_folder / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def clone_template(repo_dir: Path, *, update_existing: bool) -> None:
    if repo_dir.exists():
        if update_existing:
            print(f"Template repository already exists at {repo_dir}; updating it...")
            run_command(["git", "pull", "--ff-only"], cwd=repo_dir)
        else:
            print(f"Template repository already exists at {repo_dir}; keeping existing checkout")
        return

    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    run_command(["git", "clone", TEMPLATE_REPO_URL, str(repo_dir)])


def verify_frontend(repo_dir: Path) -> None:
    frontend_dir = repo_dir / "frontend"
    if not frontend_dir.exists():
        raise InstallerError(f"Frontend directory was not found: {frontend_dir}")

    print("Verifying frontend build...")
    package_lock = frontend_dir / "package-lock.json"
    install_command = ["npm", "ci"] if package_lock.exists() else ["npm", "install"]
    run_command(install_command, cwd=frontend_dir)
    run_command(["npm", "run", "build"], cwd=frontend_dir)


def verify_backend(repo_dir: Path) -> None:
    backend_dir = repo_dir / "backend"
    if not backend_dir.exists():
        raise InstallerError(f"Backend directory was not found: {backend_dir}")

    print("Verifying backend build...")
    run_command(["cmake", "-B", "build", "-S", "backend"], cwd=repo_dir)
    jobs = str(os.cpu_count() or 2)
    run_command(["cmake", "--build", "build", f"-j{jobs}"], cwd=repo_dir)


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_rules_folder = script_dir.parent / "service"
    default_target_folder = Path.cwd() / "cpprussia2026_workspace"

    parser = argparse.ArgumentParser(
        description="Install Ubuntu 24.04 dependencies, SourceCraft tools, rules, and C++ Russia template"
    )
    parser.add_argument(
        "--target-folder",
        "--target_folder",
        default=str(default_target_folder),
        help="Workspace folder where agent rules will be copied and the template repo will be cloned",
    )
    parser.add_argument(
        "--config-folder",
        "--config_folder",
        default=str(default_rules_folder),
        help="Folder with AGENTS.md, rules, and skills to copy into the target workspace",
    )
    parser.add_argument(
        "--repo-dir",
        default=None,
        help="Destination for the cloned template repository; defaults to <target-folder>/cpprussia2026_template",
    )
    parser.add_argument(
        "--update-existing-repo",
        action="store_true",
        help="Run `git pull --ff-only` if the template repository already exists",
    )
    parser.add_argument(
        "--skip-sourcecraft",
        action="store_true",
        help="Skip SourceCraft VS Code extension and CLI installation",
    )
    parser.add_argument(
        "--skip-dependencies",
        action="store_true",
        help="Skip apt, Node.js, Docker, PostgreSQL, and compiler installation",
    )
    parser.add_argument(
        "--skip-clone",
        action="store_true",
        help="Skip cloning/updating the template repository",
    )
    parser.add_argument(
        "--skip-build-checks",
        action="store_true",
        help="Skip frontend and backend build verification",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    target_folder = Path(args.target_folder).expanduser().resolve()
    config_folder = Path(args.config_folder).expanduser().resolve()
    repo_dir = Path(args.repo_dir).expanduser().resolve() if args.repo_dir else target_folder / TEMPLATE_REPO_DIR_NAME

    try:
        ensure_ubuntu_24()

        copy_rules(config_folder, target_folder)

        if not args.skip_dependencies:
            install_base_packages()
            install_nodejs_latest()
            install_docker()
            ensure_postgresql_running()
            validate_compilers()
        else:
            print("Skipping system dependency installation by request")

        if not args.skip_sourcecraft:
            install_sourcecraft()
        else:
            print("Skipping SourceCraft installation by request")

        if not args.skip_clone:
            clone_template(repo_dir, update_existing=args.update_existing_repo)
        else:
            print("Skipping repository clone/update by request")

        if not args.skip_build_checks:
            verify_frontend(repo_dir)
            verify_backend(repo_dir)
        else:
            print("Skipping frontend/backend build verification by request")

    except InstallerError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1

    print("\nInstallation completed successfully")
    print(f"Rules workspace: {target_folder}")
    print(f"Template repository: {repo_dir}")
    print("Installed agent: SourceCraft Code Assistant")
    return 0


if __name__ == "__main__":
    sys.exit(main())
