"""One adapter per upstream project. Each knows how to tell whether it's set up,
whether a given app is installed under it, and the commands that launch,
install and stop that app."""
from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from .catalog import App, Route
from .host import Host


@dataclass
class Command:
    """A command appbridge runs, with the environment it needs.

    Attributes:
        argv: The program and its arguments.
        env: Variables added to the environment.
        interactive: True if it asks questions, so the GUI opens it in a terminal.
        label: What the GUI shows while it runs.
    """
    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)
    interactive: bool = False
    label: str = ""

    def shell(self) -> str:
        """Return the command as one shell line, for printing (`appbridge launch --dry-run`)."""
        import shlex
        envs = " ".join(f"{k}={shlex.quote(v)}" for k, v in self.env.items())
        return (envs + " " if envs else "") + shlex.join(self.argv)


@dataclass
class Check:
    """Whether something is ready (ok), and a line saying why or what's missing (detail)."""
    ok: bool
    detail: str


def to_windows_path(p: str) -> str:
    """Return a Linux path as a Windows app inside Wine sees it (Wine maps Z: to /)."""
    if p.startswith("/"):
        return "Z:" + p.replace("/", "\\")
    return p


class Backend:
    """One way of running Windows apps: an upstream project such as LinDobe or WinApps.

    A subclass describes how to find the project on this machine and the
    commands that launch, install and stop an app through it. The catalog lists
    each app's routes (backend + app-specific target), best first, and
    core.Bridge picks the first route that's ready.

    Attributes:
        name: The backend's ID, used in config.json and `--backend`.
        label: The name shown in the GUI and in menu actions.
        project: The submodule under third_party/ (and the fork to clone).
        single_file: The app opens one file per launch.
        wine_based: The app runs on Wine or Proton, so `appbridge trace` can log it.
        source_kind: "file" or "dir" if installing needs something downloaded
            from the vendor (passed with `--from`), else "".
        source_what: What that download is, for the message when it's missing.
    """
    name = ""
    label = ""
    project = ""
    single_file = False
    wine_based = False

    def tool(self, host: Host) -> list[str] | None:
        """Return the command that drives the project (ms365, adobewine, winapps ...), or None if it isn't set up."""
        return None

    def ready(self, host: Host) -> Check:
        """Check whether the backend is set up on this machine; the default asks tool()."""
        t = self.tool(host)
        return Check(True, " ".join(t)) if t else Check(False, self.hint(host))

    def ready_app(self, app: App, host: Host) -> Check:
        """Check whether this backend can run this particular app; for most backends that's the same for every app."""
        return self.ready(host)

    def installed(self, app: App, route: Route, host: Host) -> bool | None:
        """Return whether the app is installed under this backend, or None if it can't tell (apps inside a VM)."""
        return None

    def launch(self, app: App, route: Route, files: list[str], host: Host) -> list[Command]:
        """Return the commands that open the app, with files if given.

        Backends that open one file per launch (single_file) get one command per file.
        """
        t = self.tool(host) or []
        if self.single_file and len(files) > 1:
            return [Command(t + [self.target(route, host), f]) for f in files]
        return [Command(t + [self.target(route, host), *files])]

    source_kind = ""
    source_what = ""

    def install(self, app: App, route: Route, host: Host, source=None) -> list[Command]:
        """Return the commands that install the app, or [] if appbridge can't.

        Args:
            source: The vendor's installer file or folder from `--from`, for
                backends with a source_kind.
        """
        return []

    def can_install(self, app: App, route: Route, host: Host) -> bool:
        """Return True if appbridge can run an installer for the app (perhaps once given --from FILE)."""
        return bool(self.install(app, route, host))

    def source_needed(self, app: App, route: Route, host: Host) -> str:
        """Return what vendor download the install needs, or "" if none."""
        return self.source_what if self.source_kind else ""

    def stop(self, app: App, route: Route, host: Host) -> Command | None:
        """Return the command that closes the app (or its whole prefix or VM session), or None."""
        return None

    def run_program(self, app: App, route: Route, program: str, args: list[str], host: Host) -> Command | None:
        """Return a command that runs another program in the app's Wine prefix, or None if the backend has no prefix."""
        return None

    def exe_path(self, app: App, route: Route, host: Host) -> Path | None:
        """Return the app's installed .exe on this machine, for icons and `appbridge gap`, or None."""
        return None

    def icon_file(self, app: App, route: Route, host: Host) -> Path | None:
        """Return a ready-made icon file (svg or png) the project ships for the app, or None."""
        return None

    def icon_name(self, app: App, route: Route, host: Host) -> str | None:
        """Return an icon-theme name that the app's own package installs, or None."""
        return None

    def target(self, route: Route, host: Host) -> str:
        """Return what tool() should launch for a route; the default is the route's target."""
        return route.target

    def hint(self, host: Host) -> str:
        """Return how to set the backend up, for when ready() fails."""
        return ""

    def repo_url(self, host: Host) -> str:
        """Return the GitHub URL of the project: your fork once third_party/ points at it."""
        return f"https://github.com/{host.submodule_repo(self.project)}" if self.project else ""


def _newest(base: Path, pattern: str) -> Path | None:
    """Resolve a relative path whose folder may contain {year}, choosing the newest year."""
    parts = pattern.split("/")
    cur = base
    for part in parts:
        if "{year}" in part:
            rx = re.compile("^" + re.escape(part).replace(re.escape("{year}"), r"(\d{4})") + "$")
            try:
                found = sorted((m.group(1), e) for e in cur.iterdir() if (m := rx.match(e.name)))
            except OSError:
                return None
            if not found:
                return None
            cur = found[-1][1]
        else:
            cur = cur / part
    return cur if cur.exists() else None


# --------------------------------------------------------------------------- Microsoft 365 on Proton

class Ms365(Backend):
    """Microsoft 365 on Proton, through office365_flake's `ms365` command.

    Uses `ms365` from PATH, else runs the flake with Nix: from the checked-out
    submodule, or from GitHub. The prefix is $MS365_PREFIX, or under
    $MS365_HOME (default ~/.local/share/ms365).
    """
    name, label, project = "ms365", "Wine/Proton (office365_flake)", "office365_flake"
    wine_based = True

    def tool(self, host):
        if p := host.which("ms365"):
            return [p]
        if nix := host.which("nix"):
            sub = host.submodule_dir(self.project)
            flake = str(sub) if sub and (sub / "flake.nix").exists() else f"github:{host.submodule_repo(self.project)}"
            return [nix, "--extra-experimental-features", "nix-command flakes", "run", f"{flake}#ms365", "--"]
        return None

    def prefix(self, host: Host) -> Path:
        """Return the Wine prefix Office is installed in."""
        if p := host.env.get("MS365_PREFIX"):
            return Path(p)
        return Path(host.env.get("MS365_HOME") or host.home / ".local/share/ms365") / "prefix"

    def exe_path(self, app, route, host):
        if not route.exe:
            return None
        rel = Path("drive_c/Program Files/Microsoft Office/root/Office16") / route.exe
        for root in (self.prefix(host), self.prefix(host) / "pfx"):
            if (root / rel).is_file():
                return root / rel
        return None

    def installed(self, app, route, host):
        return self.exe_path(app, route, host) is not None

    def launch(self, app, route, files, host):
        return [Command((self.tool(host) or []) + ["run", route.target, *files])]

    def install(self, app, route, host, source=None):
        t = self.tool(host)
        return [Command(t + ["install"], label="Download and install Microsoft 365 (several GB)")] if t else []

    def stop(self, app, route, host):
        t = self.tool(host)
        return Command(t + ["kill"], label="Stop all Office processes") if t else None

    def run_program(self, app, route, program, args, host):
        t = self.tool(host)
        return Command(t + ["exec", program, *args]) if t else None

    def hint(self, host):
        return ("needs the office365_flake `ms365` command or Nix with flakes "
                f"(https://nixos.org/download), see {self.repo_url(host)}")


# --------------------------------------------------------------------------- Adobe on LinDobe

class LinDobe(Backend):
    """Adobe Creative Cloud apps on LinDobe's patched Wine, through its `adobewine` command or its Flatpak."""
    name, label, project = "lindobe", "Wine (LinDobe)", "LinDobe"
    wine_based = True
    flatpak_id = "io.github.le_birnes.AdobeWine"

    def _via_flatpak(self, host: Host) -> bool:
        return not host.which("adobewine") and host.flatpak_installed(self.flatpak_id)

    def tool(self, host):
        if p := host.which("adobewine"):
            return [p]
        if host.flatpak_installed(self.flatpak_id) and (fp := host.which("flatpak")):
            return [fp, "run", "--command=adobewine", self.flatpak_id]
        sub = host.submodule_dir(self.project)
        if sub and (sub / "bin/adobewine").exists():
            if (sub / "runtime/bin/wine").exists() or (self.home(host) / "runtime/bin/wine").exists():
                return [str(sub / "bin/adobewine")]
        return None

    def home(self, host: Host) -> Path:
        if p := host.env.get("ADOBEWINE_HOME"):
            return Path(p)
        if self._via_flatpak(host):
            return host.home / ".var/app" / self.flatpak_id / "data/adobewine"
        return host.data_home / "adobewine"

    def exe_path(self, app, route, host):
        return _newest(self.home(host) / "prefix/drive_c/Program Files/Adobe", route.exe) if route.exe else None

    def installed(self, app, route, host):
        return self.exe_path(app, route, host) is not None

    def install(self, app, route, host, source=None):
        t = self.tool(host)
        if not t:
            return []
        cmds = [Command(t + ["setup"], label="Set up the LinDobe Wine prefix")]
        if not self.installed(app, route, host) and route.target != "cc":
            cmds.append(Command(t + ["cc"], label=f"Open Creative Cloud to install {app.name}"))
        return cmds

    def stop(self, app, route, host):
        t = self.tool(host)
        return Command(t + ["off"], label="Close Adobe apps and stop Wine") if t else None

    def run_program(self, app, route, program, args, host):
        t = self.tool(host)
        return Command(t + ["run", program, *args]) if t else None

    def hint(self, host):
        return (f"install LinDobe: the CCINSTALLER.flatpak from {self.repo_url(host)}/releases, "
                "its Arch package, or build third_party/LinDobe (docs/INSTALL.md)")


# --------------------------------------------------------------------------- Windows VM (WinApps / LinOffice)

class WinApps(Backend):
    """Apps installed in a Windows VM, shown as RemoteApp windows through WinApps and FreeRDP."""
    name, label, project = "winapps", "Windows VM (WinApps)", "winapps"
    single_file = True

    def tool(self, host):
        return [p] if (p := host.which("winapps") or host.which(str(host.home / ".local/bin/winapps"))) else None

    def ready(self, host):
        t = self.tool(host)
        if not t:
            return Check(False, self.hint(host))
        conf = host.config_home / "winapps/winapps.conf"
        if not conf.exists():
            return Check(False, f"WinApps is installed but {conf} is missing; run its setup")
        return Check(True, t[0])

    def _apps_dir(self, host):
        return host.data_home / "winapps/apps"

    def _resolve(self, route, host) -> tuple[str, bool | None]:
        names = route.target.split("|")
        if names == ["windows"]:
            return "windows", True
        d = self._apps_dir(host)
        if not d.is_dir():
            return names[0], None
        for n in names:
            if (d / n / "info").exists():
                return n, True
        return names[0], False

    def target(self, route, host):
        return self._resolve(route, host)[0]

    def installed(self, app, route, host):
        return self._resolve(route, host)[1]

    def icon_file(self, app, route, host):
        p = self._apps_dir(host) / self.target(route, host) / "icon.svg"
        return p if p.is_file() else None

    def install(self, app, route, host, source=None):
        sub = host.submodule_dir(self.project)
        if sub and (sub / "setup.sh").exists():
            return [Command(["bash", str(sub / "setup.sh")], interactive=True,
                            label="WinApps setup (finds the apps installed in your Windows VM)")]
        return []

    def stop(self, app, route, host):
        t = self.tool(host)
        return Command(t + ["killrdp"], label="Close the Windows app windows (FreeRDP)") if t else None

    def hint(self, host):
        return ("needs WinApps with a Windows VM (Docker, Podman or libvirt) and FreeRDP 3, "
                f"see {self.repo_url(host)}")


class LinOffice(Backend):
    """Office in LinOffice's Windows VM (a WinApps setup aimed at Office), from its Flatpak or the submodule."""
    name, label, project = "linoffice", "Windows VM (LinOffice)", "linoffice"
    flatpak_id = "io.github.eylenburg.LinOffice"
    single_file = True

    def tool(self, host):
        for c in ("linoffice", str(host.home / ".local/bin/linoffice/linoffice.sh")):
            if p := host.which(c):
                return [p]
        if host.flatpak_installed(self.flatpak_id) and (fp := host.which("flatpak")):
            return [fp, "run", "--command=/app/linoffice.sh", self.flatpak_id]
        return None

    def install(self, app, route, host, source=None):
        if fp := host.which("flatpak"):
            return [Command([fp, "remote-add", "--if-not-exists", "--user", "linoffice",
                             "https://eylenburg.github.io/linoffice/index.flatpakrepo"], label="Add the LinOffice remote"),
                    Command([fp, "install", "--user", "-y", "linoffice", self.flatpak_id], label="Install LinOffice"),
                    Command([fp, "run", self.flatpak_id], label="LinOffice setup (creates the Windows VM)")]
        sub = host.submodule_dir(self.project)
        if sub and (sub / "setup.sh").exists():
            return [Command(["bash", str(sub / "setup.sh")], interactive=True, label="LinOffice setup")]
        return []

    def stop(self, app, route, host):
        t = self.tool(host)
        return Command(t + ["--stopcontainer"], label="Shut down the Office VM") if t else None

    def hint(self, host):
        return f"needs LinOffice (Office in a Windows container, with Podman), see {self.repo_url(host)}"


# --------------------------------------------------------------------------- native Linux wrappers

_NATIVE_PROJECTS = {"teams-for-linux": "teams-for-linux", "prospect-mail": "prospect-mail",
                    "p3x-onenote": "onenote", "onedrive": "onedrive", "yabridgectl": "yabridge"}


class Flatpak(Backend):
    """Apps that ship as Flatpaks (Teams for Linux, Prospect Mail ...); installs from the route's remote."""
    name, label = "flatpak", "Flatpak"

    def tool(self, host):
        return [p] if (p := host.which("flatpak")) else None

    def ready_app(self, app, host):
        route = next(r for r in app.routes if r.backend == self.name)
        fp = host.which("flatpak")
        if not fp:
            return Check(False, "needs flatpak")
        if route.remote or host.flatpak_installed(route.target):
            return Check(True, fp)
        # Not on a remote we know: only counts once you've installed the bundle yourself.
        return Check(False, f"install the {route.target} .flatpak bundle from the project's releases")

    def installed(self, app, route, host):
        return host.flatpak_installed(route.target)

    def launch(self, app, route, files, host):
        return [Command((self.tool(host) or ["flatpak"]) + ["run", route.target, *files])]

    def install(self, app, route, host, source=None):
        t = self.tool(host)
        if t and route.remote:
            return [Command(t + ["install", "--user", "-y", route.remote, route.target], label=f"Install {route.target}")]
        return []

    def stop(self, app, route, host):
        t = self.tool(host)
        return Command(t + ["kill", route.target]) if t else None

    def icon_name(self, app, route, host):
        return route.target

    def hint(self, host):
        return "needs flatpak"


class Native(Backend):
    """Linux programs on PATH, such as yabridge."""
    name, label = "native", "Linux app"

    def ready(self, host):
        return Check(True, "")

    def ready_app(self, app, host):
        # A native wrapper is "set up" exactly when its program is on PATH.
        route = next(r for r in app.routes if r.backend == self.name)
        if p := host.which(route.target):
            return Check(True, p)
        where = self.release_url(route, host)
        return Check(False, f"install `{route.target}` from your distro" + (f" or {where}" if where else ""))

    def installed(self, app, route, host):
        return host.which(route.target) is not None

    def launch(self, app, route, files, host):
        return [Command([host.which(route.target) or route.target, *route.args, *files])]

    def icon_name(self, app, route, host):
        return route.target

    def release_url(self, route: Route, host: Host) -> str:
        proj = _NATIVE_PROJECTS.get(route.target)
        return f"https://github.com/{host.submodule_repo(proj)}/releases" if proj else ""


class Service(Backend):
    """OneDrive sync, run as the onedrive client's systemd user service."""
    name, label, project = "service", "systemd user service", "onedrive"

    def tool(self, host):
        return [p] if host.which("onedrive") and (p := host.which("systemctl")) else None

    def installed(self, app, route, host):
        return (host.config_home / "onedrive/refresh_token").exists()

    def sync_dir(self, host: Host) -> Path:
        try:
            for line in (host.config_home / "onedrive/config").read_text().splitlines():
                m = re.match(r'\s*sync_dir\s*=\s*"([^"]+)"', line)
                if m:
                    return host.expand(m.group(1))
        except OSError:
            pass
        return host.home / "OneDrive"

    def launch(self, app, route, files, host):
        cmds = [Command([(self.tool(host) or ["systemctl"])[0], "--user", "start", route.target])]
        if opener := host.which("xdg-open"):
            cmds.append(Command([opener, str(self.sync_dir(host))]))
        return cmds

    def install(self, app, route, host, source=None):
        t = self.tool(host)
        od = host.which("onedrive")
        if not t or not od:
            return []
        return [Command([od], interactive=True, label="Sign in to OneDrive (paste the redirect URL when asked)"),
                Command(t + ["--user", "enable", "--now", route.target], label="Start syncing at login")]

    def stop(self, app, route, host):
        t = self.tool(host)
        return Command(t + ["--user", "stop", route.target]) if t else None

    def hint(self, host):
        return f"needs the `onedrive` client (your distro's package, or {self.repo_url(host)}) and systemd"


# --------------------------------------------------------------------------- your own Windows apps on Wine / umu

class Wine(Backend):
    """Your own Windows apps (`appbridge add`), on plain Wine or on Proton through umu.

    Each app gets its own prefix, by default ~/.local/share/appbridge/prefixes/ID.
    """
    name, label, project = "wine", "Wine", "umu-launcher"
    wine_based = True

    def _runner(self, app: App) -> str:
        return app.custom.get("runner", "wine")

    def tool(self, host):   # backend-level: either runner will do
        return [p] if (p := host.which("wine") or host.which("umu-run")) else None

    def ready_app(self, app: App, host: Host) -> Check:
        r = self._runner(app)
        exe = "umu-run" if r == "umu" else "wine"
        p = host.which(exe)
        return Check(True, p) if p else Check(False, f"needs `{exe}` on PATH" +
                                                    (f" (umu-launcher: {self.repo_url(host)})" if r == "umu" else ""))

    def prefix(self, app: App, host: Host) -> Path:
        """Return the app's Wine prefix: its configured prefix, or the default under appbridge's data folder."""
        return host.expand(app.custom.get("prefix") or str(host.data_home / "appbridge/prefixes" / app.id))

    def exe_path(self, app, route, host):
        exe = app.custom.get("exe", "")
        if re.match(r"^[A-Za-z]:\\", exe):
            drive = exe[0].lower()
            p = self.prefix(app, host) / f"drive_{drive}" / exe[3:].replace("\\", "/")
        else:
            p = host.expand(exe)
        return p

    def installed(self, app, route, host):
        p = self.exe_path(app, route, host)
        return bool(p and p.is_file())

    def _cmd(self, app: App, host: Host, program: str, args: list[str]) -> Command:
        """Build a command that runs program in the app's prefix with its runner (wine, or umu-run with GE-Proton)."""
        env = {"WINEPREFIX": str(self.prefix(app, host)), **app.custom.get("env", {})}
        if self._runner(app) == "umu":
            env.setdefault("GAMEID", "umu-default")
            env.setdefault("PROTONPATH", app.custom.get("proton", "GE-Proton"))
            return Command([host.which("umu-run") or "umu-run", program, *args], env)
        return Command([host.which("wine") or "wine", program, *args], env)

    def launch(self, app, route, files, host):
        exe = self.exe_path(app, route, host)
        return [self._cmd(app, host, str(exe), [to_windows_path(f) for f in files])]

    def install(self, app, route, host, source=None):
        inst = app.custom.get("installer")
        return [self._cmd(app, host, str(host.expand(inst)), [])] if inst else []

    def run_program(self, app, route, program, args, host):
        return self._cmd(app, host, program, args)

    def stop(self, app, route, host):
        if self._runner(app) == "umu":
            return None
        ws = host.which("wineserver")
        return Command([ws, "-k"], {"WINEPREFIX": str(self.prefix(app, host))}) if ws else None

    def hint(self, host):
        return "needs wine or umu-run on PATH"




# --------------------------------------------------------------------------- script-driven community projects
#
# CAD, design and audio apps need the GPU or low-latency audio, which a Windows
# VM handles badly, so these run on Wine through projects whose scripts carry
# each app's fixes. appbridge clones the project (your fork, once forked) into
# ~/.local/share/appbridge/projects/NAME on first install and runs its scripts.

class ScriptProject(Backend):
    """A community project whose scripts install and run one app on Wine.

    On first install appbridge clones the project (your fork, once forked) into
    ~/.local/share/appbridge/projects/NAME, or uses $APPBRIDGE_<NAME>_SRC, and
    then runs its installer.

    Attributes:
        requires: Programs the project's installer needs on this machine.
    """
    requires: tuple[str, ...] = ()
    wine_based = True

    def route_of(self, app: App) -> Route:
        """Return the app's route for this backend."""
        return next(r for r in app.routes if r.backend == self.name)

    def project_dir(self, host: Host) -> Path:
        """Return where the project is (or will be) checked out."""
        override = host.env.get(f"APPBRIDGE_{self.name.upper()}_SRC")
        return Path(override) if override else host.data_home / "appbridge/projects" / self.project

    def ready(self, host):
        """Check that the installer's programs are on PATH (and git, if the project isn't cloned yet)."""
        missing = [t for t in self.requires if not host.which(t)]
        d = self.project_dir(host)
        if not (d.is_dir() and any(d.iterdir())) and not host.which("git"):
            missing.append("git")
        if missing:
            return Check(False, f"needs {', '.join(missing)} to install ({self.repo_url(host)})")
        return Check(True, str(d) if d.is_dir() else f"can install (downloads {self.project} to {d})")

    def ready_app(self, app, host):
        """Treat an installed app as ready even if the installer's build tools are gone."""
        # Once installed, the build tools the installer needed don't matter.
        if self.installed(app, self.route_of(app), host):
            return Check(True, "installed")
        return self.ready(host)

    def fetch(self, host: Host) -> list[Command]:
        """Return the git clone command for the project, or [] if it's already there."""
        d = self.project_dir(host)
        if d.is_dir() and any(d.iterdir()):
            return []
        return [Command([host.which("git") or "git", "clone", "--depth", "1", f"{self.repo_url(host)}.git", str(d)],
                        label=f"Download {self.project}")]

    def install_steps(self, app: App, route: Route, host: Host, source) -> list[Command]:
        """Return the project's own install commands; subclasses override this."""
        return []

    def install(self, app, route, host, source=None):
        """Return the clone and install commands, or [] while a needed `--from` source is missing."""
        if self.source_kind and not source:
            return []
        return self.fetch(host) + self.install_steps(app, route, host, source)

    def can_install(self, app, route, host):
        return self.ready(host).ok

    def _wineserver_stop(self, prefix: Path, host: Host, wineserver: str = "wineserver") -> Command | None:
        ws = host.which(wineserver)
        return Command([ws, "-k"], {"WINEPREFIX": str(prefix)}, label="Stop the app's Wine session") if ws else None


class AutoCAD(ScriptProject):
    """AutoCAD 2027 on Wine through AutoCAD-2027-Wine; installs from Autodesk's installer .exe (`--from`)."""
    name, label, project = "autocad", "Wine (AutoCAD-2027-Wine)", "AutoCAD-2027-Wine"
    requires = ("wine", "winetricks", "gcc", "python3", "bsdtar")
    source_kind = "file"
    source_what = ("Autodesk's AutoCAD 2027 installer .exe (the web installer from autodesk.com, "
                   "trial or subscription)")

    def prefix(self, host: Host) -> Path:
        return Path(host.env.get("APPBRIDGE_AUTOCAD_PREFIX") or host.home / ".autocad")

    def exe_path(self, app, route, host):
        return _newest(self.prefix(host) / "drive_c/Program Files/Autodesk", route.exe)

    def installed(self, app, route, host):
        return self.exe_path(app, route, host) is not None and (self.prefix(host) / "launcher/acad.sh").is_file()

    def launch(self, app, route, files, host):
        # acad.sh preloads the shim Autodesk's licensing service needs under Wine
        return [Command([str(self.prefix(host) / "launcher/acad.sh"), *files])]

    def install_steps(self, app, route, host, source):
        return [Command([str(self.project_dir(host) / "install.sh"), str(source), "--prefix", str(self.prefix(host))],
                        interactive=True, label="Install AutoCAD under Wine (30-60 minutes, about 30 GB)")]

    def stop(self, app, route, host):
        return self._wineserver_stop(self.prefix(host), host)


class Inventor(ScriptProject):
    """Inventor 2026/2027 on a patched Wine through Autodesk-Inventor-for-Linux; installs from Autodesk's download folder."""
    name, label, project = "inventor", "Wine (Autodesk-Inventor-for-Linux)", "Autodesk-Inventor-for-Linux"
    requires = ("python3", "curl")
    source_kind = "dir"
    source_what = "the folder with Autodesk's Inventor 2026 or 2027 download"

    def prefix(self, host: Host) -> Path | None:
        if p := host.env.get("INV_PREFIX"):
            return Path(p)
        return _newest(host.home, ".wine-inventor{year}")

    def exe_path(self, app, route, host):
        pre = self.prefix(host)
        return _newest(pre / "drive_c/Program Files/Autodesk", route.exe) if pre else None

    def installed(self, app, route, host):
        return (self.exe_path(app, route, host) is not None
                and (self.project_dir(host) / "scripts/launch-inventor.sh").is_file())

    def launch(self, app, route, files, host):
        pre = self.prefix(host)
        env = {"INV_PREFIX": str(pre)}
        if m := re.search(r"(\d{4})$", pre.name if pre else ""):
            env["INV_YEAR"] = m.group(1)
        return [Command(["bash", str(self.project_dir(host) / "scripts/launch-inventor.sh"), *files], env)]

    def install_steps(self, app, route, host, source):
        return [Command(["bash", str(self.project_dir(host) / "scripts/install.sh"), str(source)], interactive=True,
                        label="Install Inventor under Wine (builds the project's Wine; about an hour)")]

    def stop(self, app, route, host):
        pre = self.prefix(host)
        return self._wineserver_stop(pre, host) if pre else None


class Fusion(ScriptProject):
    """Fusion on Wine through cryinkfly's installer, which downloads Fusion itself."""
    name, label, project = "fusion", "Wine (Autodesk-Fusion-360-for-Linux)", "Autodesk-Fusion-360-for-Linux"
    requires = ("curl",)

    def home(self, host: Host) -> Path:
        return Path(host.env.get("APPBRIDGE_FUSION_DIR") or host.home / ".autodesk_fusion")

    def exe_path(self, app, route, host):
        prod = self.home(host) / "wineprefixes/default/drive_c/Program Files/Autodesk/webdeploy/production"
        try:
            found = [p for p in prod.glob(f"*/{route.exe}") if p.is_file()]
        except OSError:
            return None
        return max(found, key=lambda p: p.stat().st_mtime) if found else None

    def installed(self, app, route, host):
        return (self.home(host) / "bin/autodesk_fusion_launcher.sh").is_file() and \
            self.exe_path(app, route, host) is not None

    def launch(self, app, route, files, host):
        return [Command([str(self.home(host) / "bin/autodesk_fusion_launcher.sh")])]   # takes no files

    def install_steps(self, app, route, host, source):
        script = self.project_dir(host) / "files/setup/autodesk_fusion_installer_x86-64.sh"
        return [Command(["bash", str(script), "--install", "--default"], interactive=True,
                        label="Install Fusion under Wine (asks for your password to install Wine packages)")]

    def stop(self, app, route, host):
        return self._wineserver_stop(self.home(host) / "wineprefixes/default", host)


class SolidWorks(ScriptProject):
    """SOLIDWORKS 2026 on solidworks-wine's patched Wine (experimental); installs from the vendor's media folder."""
    name, label, project = "solidworks", "Wine (solidworks-wine)", "solidworks-wine"
    requires = ("python3", "gcc", "make", "winetricks")
    source_kind = "dir"
    source_what = ("the complete SOLIDWORKS 2026 SP03.2 media folder (PreReqs/, swwi/ ...) from your vendor "
                   "or school")

    def prefix(self, host: Host) -> Path:
        return self.project_dir(host) / "prefix"     # the project keeps its prefix next to its scripts

    def exe_path(self, app, route, host):
        p = self.prefix(host) / "drive_c/Program Files/SOLIDWORKS Corp/SOLIDWORKS" / route.exe
        return p if p.is_file() else None

    def installed(self, app, route, host):
        return self.exe_path(app, route, host) is not None

    def launch(self, app, route, files, host):
        return [Command([str(self.project_dir(host) / "bin/run-solidworks.sh"), *(files or ["--no-splash"])])]

    def install_steps(self, app, route, host, source):
        jobs = str(max(1, (os.cpu_count() or 2) - 1))
        steps = " && ".join([
            "cd " + shlex.quote(str(self.project_dir(host))),
            "./bin/build-helpers.sh",
            "{ [ -x wine-runtime/bin/wine ] || { python3 bin/build-wine-runtime.py --prepare-only && "
            f"python3 bin/build-wine-runtime.py --build --jobs {jobs}; }}; }}",
            "./bin/check-host.sh",
            "{ [ -f prefix/system.reg ] || ./bin/setup-prefix.sh; }",
            "./bin/install-vendor-prerequisites.sh --install",
            "./bin/install-solidworks-direct.sh",
            "./bin/install-solidworks-direct.sh --verify",
            "./bin/configure-fonts.sh",
        ])
        return [Command(["bash", "-c", steps], {"SOLIDWORKS_FULL_MEDIA_DIR": str(source)}, interactive=True,
                        label="Build the patched Wine and install SOLIDWORKS (several hours)")]

    def stop(self, app, route, host):
        rt = self.project_dir(host) / "wine-runtime/bin/wineserver"
        return Command([str(rt), "-k"], {"WINEPREFIX": str(self.prefix(host))}) if rt.exists() else None


class Affinity(ScriptProject):
    """Affinity Photo, Designer and Publisher on ElementalWarrior's Wine, through AffinityOnLinux."""
    name, label, project = "affinity", "Wine (AffinityOnLinux)", "Linux-Affinity-Installer"
    requires = ("python3",)

    def home(self, host: Host) -> Path:
        return Path(host.env.get("APPBRIDGE_AFFINITY_DIR") or host.home / ".AffinityLinux")

    def wine(self, host: Host) -> Path:
        return self.home(host) / "ElementalWarriorWine/bin/wine"

    def exe_path(self, app, route, host):
        p = self.home(host) / "drive_c/Program Files/Affinity/Affinity" / route.exe
        return p if p.is_file() else None

    def installed(self, app, route, host):
        return self.exe_path(app, route, host) is not None and self.wine(host).exists()

    def launch(self, app, route, files, host):
        # The installer keeps Affinity.desktop's Exec line in step with its Wine and
        # renderer settings, so use that when it's there.
        entry = host.data_home / "applications/Affinity.desktop"
        argv = _desktop_exec(entry)
        if argv:
            wants_win = any(a.lower().endswith(".exe") for a in argv)
            return [Command(argv + [to_windows_path(f) if wants_win else f for f in files])]
        return [Command([str(self.wine(host)), str(self.exe_path(app, route, host)),
                         *[to_windows_path(f) for f in files]], {"WINEPREFIX": str(self.home(host))})]

    def install_steps(self, app, route, host, source):
        return [Command(["python3", str(self.project_dir(host) / "AffinityScripts/AffinityLinuxInstaller.py")],
                        label="AffinityOnLinux installer (a window opens; it needs PyQt6)")]

    def stop(self, app, route, host):
        ws = self.home(host) / "ElementalWarriorWine/bin/wineserver"
        return Command([str(ws), "-k"], {"WINEPREFIX": str(self.home(host))}) if ws.exists() else None


class ClipStudio(ScriptProject):
    """Clip Studio Paint on GE-Proton through csp-linux."""
    name, label, project = "csp", "Proton (csp-linux)", "csp-linux"
    requires = ("wget", "pv")

    def _rc(self, host: Host) -> dict[str, str]:
        try:
            text = (host.home / ".config/csprc").read_text()
        except OSError:
            return {}
        return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)

    def exe_path(self, app, route, host):
        data = self._rc(host).get("STEAM_COMPAT_DATA_PATH")
        if not data:
            return None
        p = Path(data) / "pfx/drive_c/Program Files/CELSYS/CLIP STUDIO 1.5/CLIP STUDIO PAINT" / route.exe
        return p if p.is_file() else None

    def installed(self, app, route, host):
        return self.exe_path(app, route, host) is not None

    def launch(self, app, route, files, host):
        if p := host.which("csp-linux"):
            return [Command([p])]
        return [Command(["bash", str(self.project_dir(host) / "csp-linux")])]

    def install_steps(self, app, route, host, source):
        return [Command(["bash", str(self.project_dir(host) / "csp-installer.sh"), "4"], interactive=True,
                        label="Download GE-Proton and install Clip Studio Paint")]


class Ableton(ScriptProject):
    """Ableton Live on a patched Wine through ableton-linux's .run installer (`--from`)."""
    name, label, project = "ableton", "Wine (ableton-linux)", "ableton-linux"
    requires = ("sh",)
    source_kind = "file"
    source_what = ("install-ableton-latest.run from https://github.com/shibco/ableton-linux/releases "
                   "(it asks for your Live installer .zip)")

    def ready_app(self, app, host):
        if host.which("ableton-live"):
            return Check(True, "installed")
        return Check(True, "installs from the project's .run file")

    def installed(self, app, route, host):
        return host.which("ableton-live") is not None

    def fetch(self, host):
        return []     # installs from its release file, not from source

    def launch(self, app, route, files, host):
        return [Command([host.which("ableton-live") or "ableton-live", *files])]

    def install_steps(self, app, route, host, source):
        return [Command(["sh", str(source), "install"], interactive=True,
                        label="Install Ableton Live with ableton-linux's patched Wine")]


class Bottles(Backend):
    """Apps you set up yourself in Bottles, found by their .exe in a bottle and run with bottles-cli."""
    wine_based = True
    name, label, project = "bottles", "Bottles", "Bottles"
    flatpak_id = "com.usebottles.bottles"

    def tool(self, host):
        if p := host.which("bottles-cli"):
            return [p]
        if host.flatpak_installed(self.flatpak_id) and (fp := host.which("flatpak")):
            return [fp, "run", "--command=bottles-cli", self.flatpak_id]
        return None

    def _bottle_dirs(self, host: Host) -> list[Path]:
        roots = [host.home / ".var/app" / self.flatpak_id / "data/bottles/bottles", host.data_home / "bottles/bottles"]
        out = []
        for r in roots:
            try:
                out += sorted(d for d in r.iterdir() if d.is_dir())
            except OSError:
                pass
        return out

    def find(self, route: Route, host: Host) -> tuple[str, Path] | None:
        """Return (bottle name, exe path) for the first bottle that has the app installed, or None."""
        for d in self._bottle_dirs(host):
            try:
                hits = sorted(p for p in (d / "drive_c").glob(route.target) if p.is_file())
            except (OSError, ValueError):
                continue
            if hits:
                name = d.name
                try:
                    for line in (d / "bottle.yml").read_text(errors="replace").splitlines():
                        if line.startswith("Name:"):
                            name = line.split(":", 1)[1].strip().strip("'\"") or name
                            break
                except OSError:
                    pass
                return name, hits[-1]
        return None

    def installed(self, app, route, host):
        return self.find(route, host) is not None

    def exe_path(self, app, route, host):
        f = self.find(route, host)
        return f[1] if f else None

    def launch(self, app, route, files, host):
        name, exe = self.find(route, host)
        extra = ["--", *[to_windows_path(f) for f in files]] if files else []
        return [Command((self.tool(host) or ["bottles-cli"]) + ["run", "-b", name, "-e", str(exe), *extra])]

    def stop(self, app, route, host):
        f, t = self.find(route, host), self.tool(host)
        return Command(t + ["stop", "-b", f[0]]) if f and t else None

    def hint(self, host):
        return "needs Bottles (flatpak install flathub com.usebottles.bottles)"


def _desktop_exec(path: Path) -> list[str] | None:
    """Return the Exec= command of a .desktop file as argv, without %f-style field codes."""
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return None
    in_main = False
    for line in lines:
        if line.startswith("["):
            in_main = line.strip() == "[Desktop Entry]"
        elif in_main and line.startswith("Exec="):
            try:
                argv = shlex.split(line[5:])
            except ValueError:
                return None
            return [a for a in argv if not re.fullmatch(r"%[fFuUick]", a)] or None
    return None


BACKENDS: dict[str, Backend] = {b.name: b for b in (
    Ms365(), LinDobe(), WinApps(), LinOffice(), Flatpak(), Native(), Service(), Wine(),
    AutoCAD(), Inventor(), Fusion(), SolidWorks(), Affinity(), ClipStudio(), Ableton(), Bottles())}
