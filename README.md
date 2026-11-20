# appbridge

appbridge is one launcher for Microsoft 365, Adobe Creative Cloud, Autodesk and
other Windows-only work apps on Linux. Each app needs a different community
project (Proton for Office, a patched Wine for Adobe, a Windows VM for Visio),
with its own commands and shortcuts. appbridge knows those projects, checks
which ones are set up on your machine, and runs each app the best way that
works. It comes as a command-line tool (`appbridge`) and a Qt window with a tray
menu (`appbridge-gui`), and it puts the apps in your desktop's app menu, KRunner
and **Open With** like native apps.

Quick links: [Install](#install) · [How to use](#how-to-use) ·
[Troubleshooting](#troubleshooting) · [Desktop integration](#desktop-integration)

## Features

- One command, or one click, for Office, Adobe, Autodesk, Affinity, Ableton
  and others, whichever project runs them on your machine.
- Tells you what's missing for each app and installs it through the upstream
  project.
- Menu entries that group windows correctly in the task manager, use the app's
  own icon, and offer the other ways to run it on right-click.
- Your company's own Windows tools, each in its own Wine or Proton prefix.
- `appbridge trace` runs an app with Wine's logging on and reports what failed
  (with [debpak](https://github.com/spaley2011/debpak)'s winegap).
- No dependencies beyond Python; the window needs Qt for Python.

## Example

`appbridge list` shows every app and how it would run. On a machine with
nothing set up yet:

```console
$ appbridge list

Microsoft 365
  ○ word              Microsoft Word                 not set up     -
  ○ excel             Microsoft Excel                not set up     -
  ○ powerpoint        Microsoft PowerPoint           not set up     -
  ...

● ready   ◐ set up, app not installed (appbridge install APP)   ○ nothing set up (appbridge info APP)
```

`appbridge info word` then lists each way Word can run, best first, and what
each one needs.

## Supported apps

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

CAD, design and audio apps go through Wine on purpose. They need the GPU or
low-latency audio, and a Windows VM has no real 3D acceleration and sends audio
over RDP. Several of their projects are new (the AutoCAD, Inventor and
SOLIDWORKS ones target the 2026 and 2027 releases), so read each app's note
with `appbridge info APP`. SOLIDWORKS is experimental.

You bring your own subscriptions and licenses. appbridge cracks nothing, and
the upstream project for each app does the installing.

## Install

```sh
git clone https://github.com/spaley2011/appbridge
cd appbridge
pip install --user .            # appbridge and appbridge-gui; no dependencies
appbridge doctor                # what's set up on this machine
```

For the window, install Qt for Python from your distribution
(`python3-pyside6`, `pyside6` or `python3-pyqt6`), or `pip install --user '.[gui]'`.
appbridge needs Python 3.10 or newer.

You only need the projects under `third_party/` to build or run one from
source, so check out the ones you want:
`git submodule update --init --depth 1 third_party/office365_flake`.

## How to use

### See what can run

```sh
appbridge list                       # every app, its status, and how it would run
appbridge info word                  # all the ways Word can run here and what each one is missing
appbridge doctor                     # what's installed: Nix, Flatpak, FreeRDP, KVM, kbuildsycoca, ...
```

### Install an app

```sh
appbridge install word               # runs the backend's installer (here: ms365 install)
appbridge install autocad --from ~/Downloads/Autodesk_AutoCAD_2027_2_English_en-US_setup_webinstall.exe
appbridge install solidworks --from "$HOME/Downloads/SOLIDWORKS 2026 SP03.2"   # a folder
```

appbridge shows the commands and asks before running them. Apps that install
from a vendor download (AutoCAD, Inventor, SOLIDWORKS, Ableton's `.run`) take
the file with `--from`; without it, `appbridge install APP` tells you what to
download. On first install, appbridge clones the CAD, design or audio project
from your fork into `~/.local/share/appbridge/projects/`.

### Open an app or a file

```sh
appbridge launch word ~/report.docx  # open files; `--backend winapps` to force a route
appbridge launch yabridge            # re-sync Windows audio plugins after installing new ones
appbridge stop photoshop             # close Adobe apps cleanly (adobewine off)
```

### Choose how an app runs

```sh
appbridge prefer word winapps        # always use the VM for Word
appbridge prefer word auto           # back to the best route that works
```

### Add apps to the menu

```sh
appbridge integrate                  # add every ready app to the app menu
appbridge integrate --default-handlers word excel   # ...and make them the default for .docx/.xlsx
appbridge integrate --remove         # take all of appbridge's entries out again
```

### Add your own Windows app

```sh
appbridge add expenses --name "Expense Reports" --exe 'C:\Program Files\Acme\Expenses.exe' \
    --installer ~/Downloads/AcmeSetup.exe --runner umu --mime application/x-acme-expense
appbridge install expenses           # runs the installer in its own prefix
appbridge run expenses regedit       # any program in that prefix
```

### Find out why a Windows app misbehaves

Both commands need [debpak](https://github.com/spaley2011/debpak) installed.

```sh
# which Windows functions is Wine missing for an installed app?
appbridge gap photoshop --index ~/.cache/debpak/wine/11.8_x86_64.json

# what goes wrong when it runs: launches it with Wine's debug logging for 3 minutes
# (use the features you care about), closes it, and reports unimplemented calls,
# stubs, missing DLLs and COM objects, and crashes
appbridge trace word ~/report.docx
appbridge trace photoshop --timeout 600 -- --index ~/.cache/debpak/wine/11.8_x86_64.json -o ps.gap.json
```

### Use the window and tray

`appbridge-gui` (or `appbridge gui`) lists the apps by suite, with their status
and a search box. For the selected app, the buttons are **Open**,
**Open File**, **Install** (**Repair / Update** once it's installed),
**Stop**, **Add to App Menu** and **Use for Its File Types**, and
**Run with** picks how it runs. Drop files onto an app in the list to open
them there. The toolbar has **Add Windows App** for your own programs,
**Add Ready Apps to Menu**, and **System Check**, which shows the same report
as `appbridge doctor`.

Steps that ask questions, such as WinApps setup or the OneDrive sign-in, open in
Konsole (or your desktop's terminal). The tray menu launches any ready app.
`appbridge-gui --tray` starts the tray only, so you can add it to **Autostart**
in System Settings.

Every command has `--help` with the full list of options.

## Troubleshooting

### `launch` says the app isn't ready and exits with status 3

Nothing that can run the app is set up yet, or the app isn't installed in it.
The message says which; `appbridge info APP` lists every route and what each
needs. If you started the app from the menu, the same message appears as a
desktop notification.

### An app doesn't show up in the menu

`appbridge integrate` skips apps that aren't ready, apps whose Flatpak or
native package adds its own entry (Teams, Prospect Mail), and apps that already
have an entry with the same name, for example from `adobewine launchers` or the
flake's `shortcuts`. Pass `--force` to add an appbridge entry anyway.

### The window doesn't match my Plasma theme

The pip wheels of PySide6 and PyQt6 bring their own Qt without Plasma's
platform theme. Install Qt for Python from your distribution instead
(`python3-pyside6`, `pyside6`, `python3-pyqt6`); it uses the system Qt, so you
get the Breeze style and your Plasma colours and fonts.

### `appbridge trace` reports nothing

Some launchers write Wine's output to their own log file instead of the
terminal, which leaves the trace empty. Read that file with
`winegap trace --log`. Routes that run real Windows (WinApps, LinOffice) can't
be traced at all.

## Desktop integration

`appbridge integrate` writes standard freedesktop entries to
`~/.local/share/applications/appbridge-<app>.desktop`. Plasma, GNOME, Xfce,
Cinnamon and others read these:

- The apps appear in the app menu (Kickoff, Activities), in KRunner and GNOME
  search, and in Dolphin's and Nautilus' **Open With** menu for their file types.
- `StartupWMClass` matches the window class Wine gives each app (`winword.exe`),
  so the task manager groups the windows under the right icon and pinned
  launchers work.
- The right-click menu has an **Open with** action for each other ready backend
  (for example **Open with Windows VM (WinApps)**), and **Force close**, or
  **Stop** for a sync service.
- Icons come from the installed app's own `.exe` (extracted from its icon
  resources) or from the WinApps icon, and otherwise from the icon theme.
  No proprietary icons ship with appbridge.
- Afterwards it runs `kbuildsycoca6` (or 5) so Plasma sees the change right
  away, plus `update-desktop-database` and `xdg-desktop-menu forceupdate`.

## Configuration

- `~/.config/appbridge/config.json`: preferred backend per app.
- `~/.config/appbridge/apps.json`: your custom apps.
- Logs of apps launched from the menu or window: `~/.local/state/appbridge/logs/<app>.log`.
- Every backend honours its project's own variables (`MS365_PREFIX`,
  `ADOBEWINE_HOME`, `~/.config/winapps/winapps.conf`, ...).

## The forks

`third_party/` holds each upstream project as a submodule pinned to a tested
commit. Their licenses are GPL, LGPL, AGPL and MIT, and none of their code is
copied into appbridge. [third_party/README.md](third_party/README.md) lists
them, with what appbridge uses each one for.

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
- `appbridge trace` only works for routes that run on Wine, and only sees what
  the traced run did.
- appbridge can't tell which apps a Windows VM has until WinApps setup has
  scanned it, and until then it assumes the app is there.
- The window's tests have only run against a stand-in for Qt so far. With
  PySide6 or PyQt6 installed, `tests/test_appbridge_gui.py` drives the real
  window offscreen.

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
