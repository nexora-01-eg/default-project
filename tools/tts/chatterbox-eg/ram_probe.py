# -*- coding: utf-8 -*-
"""Load base model and report Windows peak working set (stdlib only)."""
import ctypes


def peak_mb():
    k32 = ctypes.windll.kernel32
    h = k32.GetCurrentProcess()

    class MI(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("pf", ctypes.c_ulong),
                    ("ws", ctypes.c_size_t), ("peak", ctypes.c_size_t),
                    ("rest", ctypes.c_size_t * 6)]

    mi = MI()
    mi.cb = ctypes.sizeof(MI)
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(mi), mi.cb)
    err = ctypes.windll.kernel32.GetLastError()
    print("ok=%s err=%s sizeof=%s" % (ok, err, mi.cb))
    return round(mi.peak / 1048576, 1), round(mi.ws / 1048576, 1)


if __name__ == "__main__":
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    ctypes.windll.psapi.GetProcessMemoryInfo.restype = ctypes.c_bool
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    peak, ws = peak_mb()
    print("peakWorkingSet_MB=%s workSet_MB=%s" % (peak, ws))
