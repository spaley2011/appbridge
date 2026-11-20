# appbridge

One launcher for Microsoft 365, Adobe Creative Cloud and other Windows-only
work apps on Linux, as a command line tool (`appbridge`) and a Qt window with a
tray menu (`appbridge-gui`). Apps it can run show up in your desktop's app menu,
KRunner and "Open With", like native apps.

Running Office or Photoshop on Linux takes a different project for each app,
each with its own commands, prefixes and shortcuts. `appbridge` is one
launcher for all of them. It knows several ways to run each app, checks
which ones are set up on your machine, and uses the best one that works:

| Apps | Ways to run them, best first |
|---|---|
| Word, Excel, PowerPoint, Outlook, OneNote, Access, Publisher | Wine/Proton via [office365_flake](https://github.com/Tombert/office365_flake) (no VM) → Windows VM via [LinOffice](https://github.com/eylenburg/linoffice) → Windows VM via [WinApps](https://github.com/winapps-org/winapps). Outlook and OneNote also fall back to [Prospect Mail](https://github.com/julian-alarcon/prospect-mail) and [P3X OneNote](https://github.com/patrikx3/onenote). |
| Photoshop, Illustrator, Premiere Pro, After Effects, InDesign, InCopy, Animate, Audition, Media Encoder, Bridge, Lightroom (Classic), Acrobat, Creative Cloud | Wine via [LinDobe](https://github.com/le-birnes/LinDobe) (built on [PhialsBasement's patches](https://github.com/PhialsBasement/wine-adobe-installers)) → WinApps |
| Teams, OneDrive | [teams-for-linux](https://github.com/IsmaelMartinez/teams-for-linux) (Flathub or native); [onedrive](https://github.com/abraunegg/onedrive) as a systemd user service |
| AutoCAD, Inventor, Fusion, SOLIDWORKS (experimental) | Wine via [AutoCAD-2027-Wine](https://github.com/ExonSounds/AutoCAD-2027-Wine), [Autodesk-Inventor-for-Linux](https://github.com/Harvi654/Autodesk-Inventor-for-Linux), [cryinkfly's Fusion installer](https://github.com/cryinkfly/Autodesk-Fusion-360-for-Linux) and [solidworks-wine](https://github.com/VV-cephei/solidworks-wine) |
| Affinity, Clip Studio Paint | Wine via [AffinityOnLinux](https://github.com/ryzendew/Linux-Affinity-Installer) → WinApps; Proton via [csp-linux](https://github.com/minsiam/csp-linux) → [Bottles](https://github.com/bottlesdevs/Bottles) |
| Ableton Live, FL Studio, Windows VST/CLAP plugins | Wine via [ableton-linux](https://github.com/shibco/ableton-linux) → Bottles; FL Studio in Bottles ([guide](https://github.com/torbuntu/fl-studio-linux-setup)); [yabridge](https://github.com/robbert-vdh/yabridge) for plugins in native DAWs |
| Visio, Project, Power BI, SQL Server Management Studio, Visual Studio, full Windows desktop | WinApps (Wine can't run these) |
| Your company's own Windows tools | Wine or Proton (umu-launcher), in a prefix per app: `appbridge add` |

CAD, design and audio apps go through Wine on purpose: they need the GPU or
low-latency audio, which a Windows VM handles badly (no real 3D acceleration,
audio over RDP). Their projects are younger, so check each app's note
(`appbridge info APP`); SOLIDWORKS in particular is experimental.

appbridge doesn't install or crack anything itself: you bring your own
subscriptions and licenses, and the upstream project does the installing.

## Install

```sh
git clone https://github.com/spaley2011/appbridge
cd appbridge
pip install --user .            # appbridge and appbridge-gui; no dependencies
appbridge doctor                # what's set up on this machine
```

The projects under `third_party/` are only needed if you want to build or run
one from source, so check out just those:
`git submodule update --init --depth 1 third_party/office365_flake`.

For the window, install Qt for Python from your distribution
(`python3-pyside6`, `pyside6` or `python3-pyqt6`), or `pip install --user '.[gui]'`.
Requires Python 3.10+.

## Command line

```sh
appbridge list                       # every app, its status, and how it would run
appbridge info word                  # all the ways Word can run here and what each one is missing
appbridge install word               # runs the backend's installer (here: ms365 install)
appbridge launch word ~/report.docx  # open files; `--backend winapps` to force a route
appbridge stop photoshop             # close Adobe apps cleanly (adobewine off)
appbridge install autocad --from ~/Downloads/Autodesk_AutoCAD_2027_2_English_en-US_setup_webinstall.exe
appbridge install solidworks --from "$HOME/Downloads/SOLIDWORKS 2026 SP03.2"   # a folder
appbridge launch yabridge            # re-sync Windows audio plugins after installing new ones
appbridge prefer word winapps        # always use the VM for Word (`auto` to undo)
appbridge integrate                  # add every ready app to the app menu
appbridge integrate --default-handlers word excel   # ...and make them the default for .docx/.xlsx
appbridge integrate --remove         # take all of appbridge's entries out again
appbridge doctor                     # what's installed: Nix, Flatpak, FreeRDP, KVM, kbuildsycoca, ...

# your own Windows app
appbridge add expenses --name "Expense Reports" --exe 'C:\Program Files\Acme\Expenses.exe' \
    --installer ~/Downloads/AcmeSetup.exe --runner umu --mime application/x-acme-expense
appbridge install expenses           # runs the installer in its own prefix
appbridge run expenses regedit       # any program in that prefix

# which Windows functions is Wine missing for an installed app? (needs debpak's winegap)
appbridge gap photoshop --index ~/.cache/debpak/wine/11.8_x86_64.json

# what actually goes wrong when it runs: launches it with Wine's debug logging for
# 3 minutes (use the features you care about), closes it, and reports unimplemented
# calls, stubs, missing DLLs and COM objects, and crashes (needs debpak)
appbridge trace word ~/report.docx
appbridge trace photoshop --timeout 600 -- --index ~/.cache/debpak/wine/11.8_x86_64.json -o ps.gap.json
```

Apps that install from a vendor download (AutoCAD, Inventor, SOLIDWORKS,
Ableton's `.run`) take it with `--from`; `appbridge install APP` without it says
what to download. The CAD, design and audio projects are cloned from your forks
into `~/.local/share/appbridge/projects/` on first install.

`launch` exits with status 3 and says what's missing when an app isn't ready.
When it was started from the app menu, it shows that as a desktop notification.

## Window and tray

`appbridge-gui` (or `appbridge gui`) lists the apps by suite with search and
their status. For the selected app you can open it or a file, install or
repair it, stop it, choose how it runs, add it to the app menu, or make it the
default for its file types. You can also drop files onto an app in the list to
open them there. Steps that ask questions, such as WinApps setup or the
OneDrive sign-in, open in Konsole (or your desktop's terminal). The tray menu
launches any ready app. `appbridge-gui --tray` starts the tray only, so you can
put it in Autostart.

The window uses Qt 6 through PySide6 or PyQt6. On KDE Plasma, install them from
your distribution (`python3-pyside6`, `pyside6`, `python3-pyqt6`) rather than
pip. The distro build uses the system Qt, so you get the Breeze style and your
Plasma colours and fonts. The pip wheels bring their own Qt without Plasma's
platform theme.

## Desktop integration

`appbridge integrate` writes standard freedesktop entries to
`~/.local/share/applications/appbridge-<app>.desktop`. Plasma, GNOME, Xfce,
Cinnamon and others read these:

- The apps appear in the app menu (Kickoff, Activities), in KRunner and GNOME
  search, and in Dolphin's and Nautilus' Open With menu for their file types.
- `StartupWMClass` matches the window class Wine gives each app (`winword.exe`),
  so the task manager groups the windows under the right icon and pinned
  launchers work.
- Right-click actions offer the other ready backends ("Open with Windows VM
  (WinApps)") and Stop.
- Icons come from the installed app's own `.exe` (extracted from its icon
  resources) or from the WinApps icon, and otherwise from the icon theme.
  No proprietary icons ship with appbridge.
- Afterwards it runs `kbuildsycoca6` (or 5) so Plasma sees the change right
  away, plus `update-desktop-database` and `xdg-desktop-menu forceupdate`.

Apps that install their own entry (Teams, Prospect Mail and other Flatpak or
native packages) are skipped. So are apps that already have an entry with the
same name, for example from `adobewine launchers` or the flake's `shortcuts`.
Pass `--force` to add an appbridge entry anyway.

## Configuration

- `~/.config/appbridge/config.json`: preferred backend per app.
- `~/.config/appbridge/apps.json`: your custom apps.
- Logs of apps launched from the menu or window: `~/.local/state/appbridge/logs/<app>.log`.
- Every backend honours its project's own variables (`MS365_PREFIX`,
  `ADOBEWINE_HOME`, `~/.config/winapps/winapps.conf`, ...).

## The forks

`third_party/` holds each upstream project as a submodule pinned to a tested
commit. Their licenses are GPL, LGPL, AGPL and MIT, and none of their code is
copied into appbridge.

```sh
scripts/fork-upstreams.sh            # fork them all into your GitHub account (needs `gh auth login`)
git commit -am "third_party: use forks"
scripts/fork-upstreams.sh --sync     # later: pull upstream fixes into your forks
```

Once the submodules point at your forks, appbridge uses them too. For example,
the Microsoft 365 backend runs `nix run github:<you>/office365_flake#ms365`, or
the checked-out submodule when it's present.

## Limits

- Each route works only as well as the project behind it. Microsoft 365 on
  Proton and Adobe on LinDobe are new and change quickly; their READMEs say
  what works. The VM routes run real Windows and are the most compatible.
- `appbridge trace` only works for routes that run on Wine (not WinApps or
  LinOffice, which run real Windows), and only sees what the traced run did. A
  launcher that writes Wine's output to its own log file instead of the
  terminal leaves the trace empty; read that file with `winegap trace --log`.
- Whether an app is installed inside a Windows VM is known only after WinApps
  setup has scanned the VM. Until then appbridge assumes it is.
- So far the Qt window has only been tested against a stand-in for Qt. Run
  `tests/test_appbridge_gui.py` with PySide6 or PyQt6 installed to test it for
  real (offscreen).

## Development

```sh
PYTHONPATH=src:tests python3 -m unittest discover -s tests -v
```

The tests fake a whole desktop (home folder, PATH of stub tools, installed
Office/Adobe/VM apps) in a temporary directory, so they need nothing installed.
The GUI test drives the real window offscreen when PySide6 or PyQt6 is
available, and a stand-in for Qt otherwise.

## License

MIT. The projects under `third_party/` keep their own licenses.
