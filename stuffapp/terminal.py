"""Terminal capabilities without optional dependencies or side effects on import."""
import sys


def supports_ansi():
    """Enable ANSI on a Windows console, or safely fall back to plain text."""
    try:
        if not sys.stdout.isatty():
            return False
        if sys.platform != "win32":
            return True
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetConsoleMode.restype = wintypes.BOOL
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.SetConsoleMode.restype = wintypes.BOOL
        handle = kernel.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = wintypes.DWORD()
        if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        # Windows requires processed output together with VT processing.
        ansi_mode = 0x0001 | 0x0004
        return bool(mode.value & ansi_mode == ansi_mode or
                    kernel.SetConsoleMode(handle, mode.value | ansi_mode))
    except (AttributeError, OSError, ValueError):
        return False
