"""The parts of the machine appbridge looks at, behind one object so tests can
fake a whole desktop in a temporary directory."""
from __future__ import annotations

import configparser
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# Upstreams used when appbridge runs outside its git checkout. Inside a
# checkout, .gitmodules wins, so after scripts/fork-upstreams.sh the forks are used.
DEFAULT_UPSTREAMS = {
    "office365_flake": "Tombert/office365_flake",
    "umu-launcher": "Open-Wine-Components/umu-launcher",
    "winapps": "winapps-org/winapps",
    "linoffice": "eylenburg/linoffice",
    "LinDobe": "le-birnes/LinDobe",
    "wine-adobe-installers": "PhialsBasement/wine-adobe-installers",
    "teams-for-linux": "IsmaelMartinez/teams-for-linux",
    "prospect-mail": "julian-alarcon/prospect-mail",
    "onenote": "patrikx3/onenote",
    "onedrive": "abraunegg/onedrive",
    "AutoCAD-2027-Wine": "ExonSounds/AutoCAD-2027-Wine",
    "Autodesk-Inventor-for-Linux": "Harvi654/Autodesk-Inventor-for-Linux",
    "Autodesk-Fusion-360-for-Linux": "cryinkfly/Autodesk-Fusion-360-for-Linux",
    "solidworks-wine": "VV-cephei/solidworks-wine",
    "Linux-Affinity-Installer": "ryzendew/Linux-Affinity-Installer",
    "csp-linux": "minsiam/csp-linux",
    "ableton-linux": "shibco/ableton-linux",
    "fl-studio-linux-setup": "torbuntu/fl-studio-linux-setup",
    "yabridge": "robbert-vdh/yabridge",
    "Bottles": "bottlesdevs/Bottles",
}


def _find_checkout() -> Path | None:
    """Return the appbridge git checkout this module runs from (it has .gitmodules and third_party/), or None."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".gitmodules").is_file() and (parent / "third_party").is_dir():
            return parent
    return None


@dataclass
class Host:
    """Environment, PATH lookup, XDG directories and the appbridge checkout."""

    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    checkout: Path | None = field(default_factory=_find_checkout)

    # ------------------------------------------------------------------ paths
    @property
    def home(self) -> Path:
        return Path(self.env.get("HOME") or Path.home())

    def _xdg(self, var: str, default: str) -> Path:
        v = self.env.get(var)
        return Path(v) if v and os.path.isabs(v) else self.home / default

    @property
    def data_home(self) -> Path:
        return self._xdg("XDG_DATA_HOME", ".local/share")

    @property
    def config_home(self) -> Path:
        return self._xdg("XDG_CONFIG_HOME", ".config")

    @property
    def state_home(self) -> Path:
        return self._xdg("XDG_STATE_HOME", ".local/state")

    def expand(self, p: str) -> Path:
        """Expand a leading ~/ against this host's HOME."""
        if p.startswith("~/"):
            return self.home / p[2:]
        return Path(p)

    # ------------------------------------------------------------------ lookup
    def which(self, name: str) -> str | None:
        """Find a program on this host's PATH; a path with a slash must exist and be executable."""
        if os.sep in name:
            return name if os.access(name, os.X_OK) and os.path.isfile(name) else None
        return shutil.which(name, path=self.env.get("PATH", os.defpath))

    def flatpak_installed(self, app_id: str) -> bool:
        """Return True if a Flatpak app is installed, for the user or system-wide."""
        dirs = [self.data_home / "flatpak/app", Path(self.env.get("APPBRIDGE_FLATPAK_SYSTEM_DIR", "/var/lib/flatpak/app"))]
        return any((d / app_id / "current").exists() for d in dirs)

    @property
    def desktop(self) -> str:
        """Return the running desktop, lower-cased (kde, gnome, xfce, ...)."""
        return (self.env.get("XDG_CURRENT_DESKTOP") or self.env.get("DESKTOP_SESSION") or "").split(":")[0].lower()

    # ------------------------------------------------------------------ checkout
    def submodule_dir(self, name: str) -> Path | None:
        """Return third_party/<name> if it's checked out (has files), else None."""
        if not self.checkout:
            return None
        d = self.checkout / "third_party" / name
        return d if d.is_dir() and any(d.iterdir()) else None

    def submodule_repo(self, name: str) -> str:
        """Return the owner/repo that .gitmodules points at for a submodule (your fork, once forked)."""
        if self.checkout:
            cp = configparser.ConfigParser()
            try:
                cp.read(self.checkout / ".gitmodules")
            except configparser.Error:
                cp = None
            sec = f'submodule "third_party/{name}"'
            if cp and cp.has_section(sec):
                m = re.match(r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", cp.get(sec, "url", fallback=""))
                if m:
                    return m.group(1)
        return DEFAULT_UPSTREAMS[name]
