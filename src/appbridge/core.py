"""Choosing a route for an app and running commands. Shared by the CLI and the GUI."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .backends import BACKENDS, Backend, Check, Command
from .catalog import App, Config, Route, all_apps, find
from .host import Host

READY, NOT_INSTALLED, NO_BACKEND = "ready", "not installed", "not set up"


@dataclass
class RouteState:
    """One route of an app on this machine: whether its backend is ready, and whether the app is installed there (None if unknown)."""
    route: Route
    backend: Backend
    check: Check
    installed: bool | None

    @property
    def usable(self) -> bool:
        """True if the backend is ready and the app isn't known to be missing."""
        return self.check.ok and self.installed is not False


@dataclass
class Resolved:
    """The route appbridge will use for an app, and why.

    Attributes:
        status: READY, NOT_INSTALLED (the backend works but the app isn't in
            it yet) or NO_BACKEND (nothing is set up).
        state: The chosen route, or None when nothing is set up.
        routes: Every route's state, best first, for `info` and the window.
    """
    app: App
    status: str
    state: RouteState | None
    routes: list[RouteState]

    @property
    def backend(self) -> Backend | None:
        return self.state.backend if self.state else None

    @property
    def summary(self) -> str:
        """Return one line for the user: which backend runs the app, or what's missing."""
        if self.status == READY:
            return f"via {self.state.backend.label}"
        if self.status == NOT_INSTALLED:
            return f"{self.state.backend.label} is set up; {self.app.name} isn't installed there yet"
        first = self.routes[0]
        return f"{first.backend.label}: {first.check.detail}" if self.routes else "no way to run it"


class Bridge:
    """The catalog, your config and the machine, in one place."""

    def __init__(self, host: Host | None = None):
        self.host = host or Host()
        self.config = Config(self.host)
        self.apps = all_apps(self.config)

    def reload(self) -> None:
        """Read the config again, after it changed on disk or through add_custom."""
        self.config = Config(self.host)
        self.apps = all_apps(self.config)

    def app(self, app_id: str) -> App:
        """Return the app with this ID.

        Raises:
            KeyError: No such app.
        """
        a = find(self.apps, app_id)
        if not a:
            raise KeyError(f"unknown app '{app_id}' (see `appbridge list --all`)")
        return a

    def route_states(self, app: App) -> list[RouteState]:
        """Check every route of an app on this machine, best first."""
        out = []
        for r in app.routes:
            b = BACKENDS[r.backend]
            chk = b.ready_app(app, self.host)
            out.append(RouteState(r, b, chk, b.installed(app, r, self.host) if chk.ok else None))
        return out

    def resolve(self, app: App, backend: str | None = None) -> Resolved:
        """Choose the route to run an app through.

        The order of preference:
            1. backend, when given (`--backend`), even if it can't launch the app yet.
            2. The saved preference (`appbridge prefer`), if it can launch the app.
            3. The first route that's ready with the app installed.
            4. The first ready route that can install the app, then any ready route.

        Raises:
            KeyError: backend isn't one of the app's routes.
        """
        states = self.route_states(app)
        want = backend or self.config.prefer.get(app.id)
        if want:
            pick = next((s for s in states if s.backend.name == want), None)
            if backend and not pick:
                raise KeyError(f"{app.name} can't run through '{backend}' "
                               f"(choices: {', '.join(s.backend.name for s in states)})")
            # --backend is obeyed as asked; a saved preference only wins when it can launch the app
            if pick and (pick.usable or backend):
                status = READY if pick.usable else (NOT_INSTALLED if pick.check.ok else NO_BACKEND)
                return Resolved(app, status, pick, states)
        for s in states:
            if s.usable:
                return Resolved(app, READY, s, states)
        settable = [s for s in states if s.check.ok]
        for s in settable:   # prefer a route appbridge can install the app through
            if s.backend.can_install(app, s.route, self.host):
                return Resolved(app, NOT_INSTALLED, s, states)
        if settable:
            return Resolved(app, NOT_INSTALLED, settable[0], states)
        return Resolved(app, NO_BACKEND, None, states)

    # ------------------------------------------------------------------ custom apps
    def add_custom(self, app_id: str, exe: str, name: str = "", runner: str = "wine", prefix: str = "",
                   mime: list[str] | None = None, categories: list[str] | None = None,
                   env: dict[str, str] | None = None, proton: str = "", installer: str = "",
                   generic: str = "") -> App:
        """Add (or replace) one of your own Windows apps and save it to apps.json.

        Raises:
            ValueError: An invalid ID, the ID of a built-in app, a runner other than
                wine or umu, or no exe.
        """
        from .catalog import BUILTIN, valid_id
        if not valid_id(app_id):
            raise ValueError("ID must be lower-case letters, digits, '.', '_' or '-'")
        if any(x.id == app_id for x in BUILTIN):
            raise ValueError(f"'{app_id}' is a built-in app; pick another ID")
        if runner not in ("wine", "umu"):
            raise ValueError("runner must be wine or umu")
        if not exe:
            raise ValueError("give the program's .exe")
        d = {"id": app_id, "name": name or app_id, "exe": exe, "runner": runner,
             "prefix": prefix or str(self.config.default_prefix(app_id)), "mime": list(mime or []),
             "categories": list(categories or ["Office"]), "env": dict(env or {})}
        for k, v in (("proton", proton), ("installer", installer), ("generic", generic)):
            if v:
                d[k] = v
        self.config.custom = [x for x in self.config.custom if x["id"] != app_id] + [d]
        self.config.save()
        self.reload()
        return self.app(app_id)

    def remove_custom(self, app_id: str) -> None:
        """Remove one of your own apps and its saved preference.

        Raises:
            ValueError: app_id isn't a custom app.
        """
        if not any(x["id"] == app_id for x in self.config.custom):
            raise ValueError(f"'{app_id}' isn't one of your custom apps")
        self.config.custom = [x for x in self.config.custom if x["id"] != app_id]
        self.config.prefer.pop(app_id, None)
        self.config.save()
        self.reload()

    # ------------------------------------------------------------------ commands
    def launch_commands(self, res: Resolved, files: list[str]) -> list[Command]:
        """Return the commands that open the app; local file paths become absolute, URIs pass through."""
        files = [str(Path(f).expanduser().resolve()) if not _is_uri(f) else f for f in files]
        return res.backend.launch(res.app, res.state.route, files, self.host)

    def install_commands(self, res: Resolved, source: str | None = None) -> list[Command]:
        """Return the commands that install the app through its chosen route, or [] if there are none."""
        if not res.state:
            return []
        if source:
            source = str(Path(source).expanduser().resolve())
        return res.backend.install(res.app, res.state.route, self.host, source=source)

    def can_install(self, res: Resolved) -> bool:
        """Return True if appbridge can run an installer for the app on its chosen route."""
        return bool(res.state) and res.state.check.ok and res.backend.can_install(res.app, res.state.route, self.host)

    def source_needed(self, res: Resolved) -> tuple[str, str]:
        """Return ("file" or "dir", what) when installing needs a vendor download; ("", "") if not."""
        if not res.state:
            return "", ""
        what = res.backend.source_needed(res.app, res.state.route, self.host)
        return (res.backend.source_kind, what) if what else ("", "")

    def stop_command(self, res: Resolved) -> Command | None:
        """Return the command that closes the app, or None."""
        return res.backend.stop(res.app, res.state.route, self.host) if res.state else None

    def install_hint(self, res: Resolved) -> str:
        """Return what to do by hand when appbridge has no command to run for the app."""
        if not res.state:   # nothing set up: list every way to get it, best first
            return "; or ".join(f"{s.backend.label}: {s.check.detail}" for s in res.routes)
        s = res.state
        if not s.check.ok:
            return s.check.detail
        b = s.backend
        if b.name == "native":
            return f"install `{s.route.target}` from your distro or {b.release_url(s.route, self.host)}"
        if b.name == "flatpak" and not s.route.remote:
            return "download the .flatpak from the project's releases page and run `flatpak install --user FILE`"
        if b.name == "wine":
            return f"run its installer in the prefix: appbridge run {res.app.id} /path/to/setup.exe"
        return b.hint(self.host)

    def env_for(self, cmd: Command) -> dict[str, str]:
        """Return the environment to run cmd in: ours plus the command's own variables."""
        env = dict(self.host.env)
        env.update(cmd.env)
        return env

    def log_path(self, app_id: str) -> Path:
        """Return the log file for an app started from the menu or window (~/.local/state/appbridge/logs/ID.log)."""
        d = self.host.state_home / "appbridge/logs"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{app_id}.log"

    def spawn(self, cmd: Command, log: Path | None = None) -> subprocess.Popen:
        """Start a command detached from us (it keeps running if the GUI closes)."""
        out = open(log, "ab") if log else subprocess.DEVNULL
        try:
            return subprocess.Popen(cmd.argv, env=self.env_for(cmd), stdin=subprocess.DEVNULL, stdout=out,
                                    stderr=subprocess.STDOUT, start_new_session=True)
        finally:
            if log:
                out.close()

    def terminal(self, cmd: Command) -> Command:
        """Wrap an interactive command in a terminal window, Konsole first (GNOME Terminal first on GNOME).

        The terminal stays in the foreground until the command ends, so the next
        install step waits for it.

        Raises:
            RuntimeError: No known terminal emulator is installed.
        """
        import shlex
        script = cmd.shell() + '; echo; read -r -p "Done (exit $?). Press Enter to close. " _'
        inner = ["bash", "-c", script]
        order = ["konsole", "gnome-terminal", "kgx", "xfce4-terminal", "x-terminal-emulator", "alacritty",
                 "kitty", "foot", "xterm"]
        if self.host.desktop in ("gnome", "ubuntu"):
            order.remove("gnome-terminal")
            order.insert(0, "gnome-terminal")
        for t in order:
            if p := self.host.which(t):
                # each terminal must stay in the foreground until the command ends,
                # so the next step (e.g. "start syncing") waits for this one
                if t == "gnome-terminal":
                    return Command([p, "--wait", "--", *inner], cmd.env, False, cmd.label)
                if t == "kgx":
                    return Command([p, "--", *inner], cmd.env, False, cmd.label)
                if t == "konsole":
                    return Command([p, "--nofork", "-e", *inner], cmd.env, False, cmd.label)
                if t in ("kitty", "foot"):
                    return Command([p, *inner], cmd.env, False, cmd.label)
                return Command([p, "-e", *inner] if t != "xfce4-terminal" else [p, "-x", *inner],
                               cmd.env, False, cmd.label)
        raise RuntimeError(f"no terminal emulator found to run: {shlex.join(cmd.argv)}")


def _is_uri(s: str) -> bool:
    """Return True for a URI (https://, msteams:, mailto:) rather than a file path."""
    return "://" in s or s.startswith(("msteams:", "mailto:"))
