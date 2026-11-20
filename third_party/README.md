# third_party

The projects that `appbridge` drives, kept as git submodules pinned to a
commit that was tested with it. None of their code is copied into appbridge's
own (MIT) code, and each project keeps its own license.

```sh
git submodule update --init --depth 1 third_party/office365_flake   # just the ones you need
git submodule update --init --depth 1                               # or all of them (wine-adobe-installers is a full Wine tree)
scripts/fork-upstreams.sh                                           # fork them all into your GitHub account and repoint
scripts/fork-upstreams.sh --sync                                    # later: pull upstream changes into your forks
```

| Submodule | Upstream | License | What appbridge uses it for |
|---|---|---|---|
| `office365_flake` | [Tombert/office365_flake](https://github.com/Tombert/office365_flake) | LGPL-2.1 | Microsoft 365 desktop apps (Word, Excel, PowerPoint, Outlook, OneNote, Access, Publisher) on GE-Proton through umu, no VM. Driven through its `ms365` command or `nix run`. |
| `umu-launcher` | [Open-Wine-Components/umu-launcher](https://github.com/Open-Wine-Components/umu-launcher) | GPL-3.0 | Proton runner for the Microsoft 365 flake, and the `umu` runner for custom apps. |
| `winapps` | [winapps-org/winapps](https://github.com/winapps-org/winapps) | mixed (see its COPYRIGHT.md) | Runs Windows apps from a Windows VM as seamless RemoteApp windows. Fallback for Office and Adobe, and the only route for Visio, Project, Power BI, SSMS and other apps Wine can't run. |
| `linoffice` | [eylenburg/linoffice](https://github.com/eylenburg/linoffice) | AGPL-3.0 | One-step WinApps setup aimed at Office (Word, Excel, PowerPoint, Outlook, OneNote). |
| `LinDobe` | [le-birnes/LinDobe](https://github.com/le-birnes/LinDobe) | LGPL-2.1 | Adobe Creative Cloud apps (Photoshop, Illustrator, Premiere Pro, After Effects, InDesign, Lightroom, Acrobat, ...) on a patched Wine. Driven through its `adobewine` command. |
| `wine-adobe-installers` | [PhialsBasement/wine-adobe-installers](https://github.com/PhialsBasement/wine-adobe-installers) | LGPL-2.1 | The Wine patch set that first made the Creative Cloud installer work. Reference and fallback runtime; LinDobe builds on it. |
| `teams-for-linux` | [IsmaelMartinez/teams-for-linux](https://github.com/IsmaelMartinez/teams-for-linux) | GPL-3.0 | Microsoft Teams (Microsoft dropped its Linux client). |
| `prospect-mail` | [julian-alarcon/prospect-mail](https://github.com/julian-alarcon/prospect-mail) | MIT | Outlook mail and calendar as a desktop app, for machines without the Wine/VM Outlook. |
| `onenote` | [patrikx3/onenote](https://github.com/patrikx3/onenote) | MIT | OneNote as a desktop app. |
| `onedrive` | [abraunegg/onedrive](https://github.com/abraunegg/onedrive) | GPL-3.0 | OneDrive and SharePoint file sync (Microsoft has no Linux client). Run as a user service. |
| `AutoCAD-2027-Wine` | [ExonSounds/AutoCAD-2027-Wine](https://github.com/ExonSounds/AutoCAD-2027-Wine) | GPL-3.0 | AutoCAD 2027 on Wine: installs from Autodesk's installer with fixes for its installer, licensing services and UI. |
| `Autodesk-Inventor-for-Linux` | [Harvi654/Autodesk-Inventor-for-Linux](https://github.com/Harvi654/Autodesk-Inventor-for-Linux) | MIT | Inventor 2026/2027 Professional on a patched Wine, from Autodesk's download. |
| `Autodesk-Fusion-360-for-Linux` | [cryinkfly/Autodesk-Fusion-360-for-Linux](https://github.com/cryinkfly/Autodesk-Fusion-360-for-Linux) | MIT | Fusion on Wine. Archived on GitHub; development continues on [Codeberg](https://codeberg.org/cryinkfly/Autodesk-Fusion-360-on-Linux), where its installer downloads from. |
| `solidworks-wine` | [VV-cephei/solidworks-wine](https://github.com/VV-cephei/solidworks-wine) | MIT (Wine patches LGPL-2.1) | SOLIDWORKS 2026 on a patched Wine 9.22. Experimental. |
| `Linux-Affinity-Installer` | [ryzendew/Linux-Affinity-Installer](https://github.com/ryzendew/Linux-Affinity-Installer) (AffinityOnLinux) | none stated | Affinity (Photo, Designer, Publisher, v3) on ElementalWarrior's Wine. |
| `csp-linux` | [minsiam/csp-linux](https://github.com/minsiam/csp-linux) | MIT | Clip Studio Paint on GE-Proton. |
| `ableton-linux` | [shibco/ableton-linux](https://github.com/shibco/ableton-linux) | LGPL-2.1 | Ableton Live 11/12, Max for Live and Push on a patched Wine. |
| `fl-studio-linux-setup` | [torbuntu/fl-studio-linux-setup](https://github.com/torbuntu/fl-studio-linux-setup) | CC0 | The guide appbridge points to for setting up FL Studio in Bottles. |
| `yabridge` | [robbert-vdh/yabridge](https://github.com/robbert-vdh/yabridge) | GPL-3.0 | Windows VST2/VST3/CLAP plugins in native Linux DAWs. |
| `Bottles` | [bottlesdevs/Bottles](https://github.com/bottlesdevs/Bottles) | GPL-3.0 | Runs apps you set up in Bottles yourself (FL Studio, Clip Studio Paint, Ableton) through `bottles-cli`. |

The CAD, design and audio projects aren't run from these submodules: on first
install appbridge clones your fork into `~/.local/share/appbridge/projects/`
(some keep their Wine prefix inside the project folder).

Considered and left out:

- SketchUp: no installer project found, and users report 2025 and 2026
  crashing under Wine.
- Revit: cryinkfly's project is still marked "in progress".
- `lori28167/autocad-wine-linux`: AutoCAD 2026, replaced by the 2027 project.
- Corbin Davenport's `creative-cloud-linux`: a PlayOnLinux script last changed
  in 2020, replaced by the Wine patches above.
- `office365-pol`: its author says it no longer works with current Microsoft 365.
