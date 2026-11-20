# appbridge

appbridge is a launcher for the Windows apps people need for work on Linux:
Microsoft 365, Adobe Creative Cloud, Autodesk's CAD tools, and so on. Each of
these runs through a different community project. Office works on Proton,
Adobe needs a patched Wine, and Visio only runs in a Windows VM, and every
project has its own commands and its own idea of a shortcut. appbridge knows
those projects, checks which ones you have set up, and runs each app the best
way available. The apps then show up in your app menu, KRunner and the Open
With menu like any other program.

There's a command-line tool (`appbridge`) and a small Qt window with a tray
icon (`appbridge-gui`). On a machine with nothing set up yet, `appbridge list`
looks like this:

```console
$ appbridge list

Microsoft 365
  ○ word              Microsoft Word                 not set up     -
  ○ excel             Microsoft Excel                not set up     -
  ○ powerpoint        Microsoft PowerPoint           not set up     -
  ...

● ready   ◐ set up, app not installed (appbridge install APP)   ○ nothing set up (appbridge info APP)
```

`appbridge info word` shows each way Word could run, best first, and what
each one still needs.

## What it can run

| Apps | How, best option first |
|---|---|
| Word, Excel, PowerPoint, Outlook, OneNote, Access, Publisher | Proton via [office365_flake](https://github.com/Tombert/office365_flake), then a Windows VM via [LinOffice](https://github.com/eylenburg/linoffice), then one via [WinApps](https://github.com/winapps-org/winapps). Outlook and OneNote also fall back to [Prospect Mail](https://github.com/julian-alarcon/prospect-mail) and [P3X OneNote](https://github.com/patrikx3/onenote). |
| Photoshop, Illustrator, Premiere Pro, After Effects, InDesign, InCopy, Animate, Audition, Media Encoder, Bridge, Lightroom (Classic), Acrobat, Creative Cloud | Wine via [LinDobe](https://github.com/le-birnes/LinDobe) (built on [PhialsBasement's patches](https://github.com/PhialsBasement/wine-adobe-installers)), then WinApps |
| Teams, OneDrive | [teams-for-linux](https://github.com/IsmaelMartinez/teams-for-linux) (Flathub or native), and the [onedrive](https://github.com/abraunegg/onedrive) client as a systemd user service |
| AutoCAD, Inventor, Fusion, SOLIDWORKS | Wine via [AutoCAD-2027-Wine](https://github.com/ExonSounds/AutoCAD-2027-Wine), [Autodesk-Inventor-for-Linux](https://github.com/Harvi654/Autodesk-Inventor-for-Linux), [cryinkfly's Fusion installer](https://github.com/cryinkfly/Autodesk-Fusion-360-for-Linux) and [solidworks-wine](https://github.com/VV-cephei/solidworks-wine) (experimental) |
| Affinity, Clip Studio Paint | Wine via [AffinityOnLinux](https://github.com/ryzendew/Linux-Affinity-Installer), then WinApps; Proton via [csp-linux](https://github.com/minsiam/csp-linux), then [Bottles](https://github.com/bottlesdevs/Bottles) |
| Ableton Live, FL Studio, Windows VST/CLAP plugins | Wine via [ableton-linux](https://github.com/shibco/ableton-linux), then Bottles; FL Studio in Bottles ([guide](https://github.com/torbuntu/fl-studio-linux-setup)); [yabridge](https://github.com/robbert-vdh/yabridge) for plugins in Linux DAWs |
| Visio, Project, Power BI, SQL Server Management Studio, Visual Studio, a full Windows desktop | WinApps only, since Wine can't run these |
| Your company's own Windows tools | Wine, or Proton through umu-launcher, in a prefix per app (see `appbridge add` below) |

The CAD, design and audio apps go through Wine on purpose. They need the GPU
or low-latency audio, and a Windows VM has no real 3D acceleration and sends
audio over RDP. Several of those projects are new (the AutoCAD, Inventor and
SOLIDWORKS ones target the 2026 and 2027 releases), so check each app's note
in `appbridge info`. SOLIDWORKS in particular is experimental.

You need your own subscriptions and licenses. appbridge doesn't crack
anything, and the installing is done by each upstream project.

## Installing

```sh
git clone https://github.com/spaley2011/appbridge
cd appbridge
pip install --user .
appbridge doctor
```

doctor tells you what's already on the machine (Nix, Flatpak, FreeRDP, KVM and
so on). appbridge needs Python 3.10 or newer and nothing else. For the window,
install Qt for Python from your distribution (python3-pyside6, pyside6 or
python3-pyqt6), or `pip install --user '.[gui]'`.

The upstream projects live under third_party/ as git submodules. You only need
to check one out to build or run it from source:

```sh
git submodule update --init --depth 1 third_party/office365_flake
```

## Using it

Every command takes `--help` for its options. To install an app and open a
file in it:

```sh
appbridge install word
appbridge launch word ~/report.docx
```

install shows you the commands it's about to run and asks first. For Word
that's office365_flake's own `ms365 install`. Apps that install from something
you download from the vendor (AutoCAD, Inventor, SOLIDWORKS, Ableton) take it
with `--from`, either a file or a folder:

```sh
appbridge install autocad --from ~/Downloads/Autodesk_AutoCAD_2027_2_English_en-US_setup_webinstall.exe
appbridge install solidworks --from "$HOME/Downloads/SOLIDWORKS 2026 SP03.2"
```

Without `--from`, install tells you what to download. The first time you
install one of the CAD, design or audio apps, appbridge clones its project
(your fork of it) into ~/.local/share/appbridge/projects/.

appbridge picks the best route that works, but you can choose:

```sh
appbridge prefer word winapps
appbridge prefer word auto
```

The first makes Word always open in the VM, and the second goes back to the
default. `appbridge launch word --backend winapps` does it for one launch.
`appbridge stop photoshop` closes an app properly (for Adobe that means
shutting down its Wine prefix), and `appbridge launch yabridge` re-syncs your
Windows audio plugins after you install new ones.

To put the apps in your menu:

```sh
appbridge integrate
appbridge integrate --default-handlers word excel
appbridge integrate --remove
```

The first adds every app that's ready. The second also makes Word and Excel
the default for .docx and .xlsx files, and the third takes all of appbridge's
entries out again.

### Your own Windows programs

Company tools and other one-off programs can go in too. Each gets its own Wine
prefix:

```sh
appbridge add expenses --name "Expense Reports" --exe 'C:\Program Files\Acme\Expenses.exe' \
    --installer ~/Downloads/AcmeSetup.exe --runner umu --mime application/x-acme-expense
appbridge install expenses
appbridge run expenses regedit
```

`--runner umu` runs it on Proton instead of plain Wine. run starts any other
program in the same prefix.

### When a Windows app misbehaves

If you have [debpak](https://github.com/spaley2011/debpak) installed, two more
commands help work out why. gap lists the Windows functions Wine is missing
for an installed app. trace opens the app with Wine's debug logging on, closes
it after three minutes, and reports what failed: unimplemented functions it
called, stubs, DLLs and COM objects that didn't load, and crashes.

```sh
appbridge gap photoshop --index ~/.cache/debpak/wine/11.8_x86_64.json
appbridge trace word ~/report.docx
```

Use the app while trace runs, since it only sees what you do. Options after
`--` go to debpak's winegap, so `appbridge trace photoshop --timeout 600 --
--index FILE -o ps.gap.json` saves a report you can compare later.

### The window

`appbridge-gui` lists the apps by suite, with a search box. Select one to see
its status and the ways it can run, and to open it, install or repair it, stop
it, add it to the menu or make it the default for its file types. You can also
drop files on an app in the list. Setup steps that ask questions, like WinApps
setup or the OneDrive sign-in, open in Konsole (or your desktop's terminal).

The tray icon has a menu of every ready app. `appbridge-gui --tray` starts
with just the tray icon, which is handy in Autostart.

## If something's not working

If launch says the app isn't ready and exits with status 3, nothing that can
run it is set up yet, or it isn't installed there. `appbridge info APP` lists
each option and what it needs. When you start an app from the menu, the same
message shows up as a notification.

If an app is missing from your menu after `appbridge integrate`, it was
probably skipped. That happens to apps that aren't ready, to apps whose own
package already adds a menu entry (Teams, Prospect Mail), and to apps that
already have an entry with the same name, for example from LinDobe's
`adobewine launchers` or the flake's shortcuts. `--force` adds them anyway.

If the window doesn't match your Plasma theme, you probably installed Qt from
pip. The pip wheels bring their own copy of Qt, which doesn't load Plasma's
theme. Install python3-pyside6 or python3-pyqt6 from your distribution instead.

If trace reports nothing, the launcher probably wrote Wine's output to its own
log file. Find that file and run `winegap trace --log` on it. Apps running in
a Windows VM can't be traced at all.

## How the menu entries work

`appbridge integrate` writes ordinary .desktop files to
~/.local/share/applications/appbridge-APP.desktop, so Plasma, GNOME, Xfce and
Cinnamon all pick them up. They run `appbridge launch`, which means an entry
keeps working if you switch an app to another route later.

Each entry sets StartupWMClass to the window class Wine gives the app (for
Word, winword.exe), so the task manager groups its windows under the right
icon and pinning works. Right-clicking gives you the app's other routes ("Open
with Windows VM (WinApps)") and Force close, or Stop for a sync service. The
icon comes from the app's own .exe, or from WinApps, or else from your icon
theme, so no Microsoft or Adobe icons are shipped here. Afterwards appbridge
runs kbuildsycoca6 so Plasma notices straight away.

Your settings are in ~/.config/appbridge: config.json holds the route you
picked for each app, and apps.json your own programs. Apps started from the
menu or the window log to ~/.local/state/appbridge/logs/APP.log. Each project's
own settings still apply (`MS365_PREFIX`, `ADOBEWINE_HOME`,
~/.config/winapps/winapps.conf).

## Forks

third_party/ pins each upstream project as a git submodule.
[third_party/README.md](third_party/README.md) lists them and what appbridge
uses each one for. They keep their own licenses (GPL, LGPL, AGPL and MIT),
and none of their code is copied in here.

To fork them all into your GitHub account and point the submodules at the
forks (needs `gh auth login`):

```sh
scripts/fork-upstreams.sh
git commit -am "third_party: use forks"
```

Later, `scripts/fork-upstreams.sh --sync` pulls upstream fixes into your forks.
appbridge then uses the forks too. The Microsoft 365 route runs
`nix run github:YOU/office365_flake#ms365`, or the checked-out submodule if
it's there.

## Limitations

Each app runs only as well as the project behind it. Office on Proton and Adobe
on LinDobe are new and change quickly, so check their READMEs for what works.
The VM routes run real Windows and are the most reliable. appbridge also can't
tell which apps a Windows VM has until WinApps setup has scanned it, so until
then it assumes the app is there. The window has only been tested against a
stand-in for Qt so far.

## Development

```sh
PYTHONPATH=src:tests python3 -m unittest discover -s tests -v
```

The tests build a fake desktop in a temporary directory (a home folder, stub
tools on PATH, Office and Adobe "installed" in fake prefixes), so they don't
need anything installed. With PySide6 or PyQt6 available, the GUI test drives
the real window offscreen.

## License

MIT. The projects under third_party/ keep their own licenses.
