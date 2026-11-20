"""Just enough of a PE (Windows .exe) reader to find the resource section:
headers, data directories and RVA-to-file-offset mapping. Taken from debpak's
pe.py (MIT)."""
from __future__ import annotations

import struct


class PeError(Exception):
    pass


class _Image:
    def __init__(self, m):
        self.m = m
        pe = struct.unpack_from("<I", m, 0x3C)[0]
        if m[pe:pe + 4] != b"PE\0\0":
            raise PeError("missing PE signature")
        (self.machine, nsec, _ts, _st, _ns, opt_size, self.characteristics) = struct.unpack_from("<HHIIIHH", m, pe + 4)
        opt = pe + 24
        self.magic = struct.unpack_from("<H", m, opt)[0]
        if self.magic == 0x20B:
            self.image_base = struct.unpack_from("<Q", m, opt + 24)[0]
            self.subsystem = struct.unpack_from("<H", m, opt + 68)[0]
            ndirs = struct.unpack_from("<I", m, opt + 108)[0]
            dirs_off = opt + 112
            self.ptr_size = 8
        elif self.magic == 0x10B:
            self.image_base = struct.unpack_from("<I", m, opt + 28)[0]
            self.subsystem = struct.unpack_from("<H", m, opt + 68)[0]
            ndirs = struct.unpack_from("<I", m, opt + 92)[0]
            dirs_off = opt + 96
            self.ptr_size = 4
        else:
            raise PeError(f"unknown optional header magic {self.magic:#x}")
        self.dirs = [struct.unpack_from("<II", m, dirs_off + 8 * i) for i in range(min(ndirs, 16))]
        self.dirs += [(0, 0)] * (16 - len(self.dirs))
        self.sections = []
        sec = opt + opt_size
        for i in range(nsec):
            _name, vsize, va, rawsize, rawptr = struct.unpack_from("<8sIIII", m, sec + 40 * i)
            self.sections.append((va, max(vsize, rawsize), rawptr, rawsize))

    def off(self, rva: int) -> int:
        for va, size, rawptr, rawsize in self.sections:
            if va <= rva < va + size:
                delta = rva - va
                if delta >= rawsize:
                    raise PeError(f"RVA {rva:#x} is in uninitialized data")
                return rawptr + delta
        # headers are mapped at RVA 0 == file offset 0
        if rva < (self.sections[0][2] if self.sections else len(self.m)):
            return rva
        raise PeError(f"RVA {rva:#x} not in any section")
