"""Unicode clipboard transfer for the Windows OpenCV review window."""

import ctypes
import os
import time
from ctypes import wintypes


def copy_text(value):
    if os.name != "nt":
        raise RuntimeError("Clipboard copying is available in the Windows viewer")
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user.OpenClipboard.argtypes, user.OpenClipboard.restype = [wintypes.HWND], wintypes.BOOL
    user.CloseClipboard.argtypes, user.CloseClipboard.restype = [], wintypes.BOOL
    user.EmptyClipboard.argtypes, user.EmptyClipboard.restype = [], wintypes.BOOL
    user.SetClipboardData.argtypes, user.SetClipboardData.restype = (
        [wintypes.UINT, wintypes.HANDLE],
        wintypes.HANDLE,
    )
    user.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        ctypes.c_void_p,
    ]
    user.CreateWindowExW.restype = wintypes.HWND
    user.DestroyWindow.argtypes, user.DestroyWindow.restype = [wintypes.HWND], wintypes.BOOL
    kernel.GlobalAlloc.argtypes, kernel.GlobalAlloc.restype = (
        [wintypes.UINT, ctypes.c_size_t],
        wintypes.HGLOBAL,
    )
    kernel.GlobalLock.argtypes, kernel.GlobalLock.restype = [wintypes.HGLOBAL], ctypes.c_void_p
    kernel.GlobalUnlock.argtypes, kernel.GlobalUnlock.restype = [wintypes.HGLOBAL], wintypes.BOOL
    kernel.GlobalFree.argtypes, kernel.GlobalFree.restype = [wintypes.HGLOBAL], wintypes.HGLOBAL
    data = (value + "\0").encode("utf-16-le")
    # A message-only window gives the clipboard a real owner without showing
    # another window or depending on whichever application has focus.
    owner = user.CreateWindowExW(
        0, "STATIC", "LDO clipboard owner", 0, 0, 0, 0, 0, wintypes.HWND(-3), None, None, None
    )
    if not owner:
        raise ctypes.WinError(ctypes.get_last_error())
    handle = kernel.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    if not handle:
        user.DestroyWindow(owner)
        raise ctypes.WinError(ctypes.get_last_error())
    opened = transferred = False
    try:
        address = kernel.GlobalLock(handle)
        if not address:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            ctypes.memmove(address, data, len(data))
        finally:
            kernel.GlobalUnlock(handle)
        for attempt in range(5):
            if user.OpenClipboard(owner):
                opened = True
                break
            if attempt < 4:
                time.sleep(0.02)
        if not opened or not user.EmptyClipboard():
            raise ctypes.WinError(ctypes.get_last_error())
        if not user.SetClipboardData(13, handle):  # CF_UNICODETEXT
            raise ctypes.WinError(ctypes.get_last_error())
        transferred = True  # Windows owns the allocation after transfer.
    finally:
        if opened:
            user.CloseClipboard()
        if not transferred:
            kernel.GlobalFree(handle)
        user.DestroyWindow(owner)
