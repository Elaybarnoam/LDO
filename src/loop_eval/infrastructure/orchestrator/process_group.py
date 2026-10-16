"""Own a native process tree, including descendants left by an adapter."""

import ctypes
import os
import signal
import time
from ctypes import wintypes


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IOCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits),
        ("IoInfo", _IOCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class ProcessGroup:
    def __init__(self, process):
        self.process = process
        self._job = None
        self._closed = False
        if os.name != "nt":
            return
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel = kernel
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": (
                [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
                wintypes.BOOL,
            ),
            "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "QueryInformationJobObject": (
                [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p],
                wintypes.BOOL,
            ),
        }
        for name, (args, result) in signatures.items():
            function = getattr(kernel, name)
            function.argtypes, function.restype = args, result
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            limits = _ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
            if not kernel.SetInformationJobObject(
                job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            handle = kernel.OpenProcess(0x0101, False, process.pid)  # SET_QUOTA | TERMINATE
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if not kernel.AssignProcessToJobObject(job, handle):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                kernel.CloseHandle(handle)
            self._job = job
        except BaseException:
            kernel.CloseHandle(job)
            raise

    def terminate(self) -> None:
        if self._closed:
            return
        if self._job:
            if not self._kernel.TerminateJobObject(self._job, 1):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def close(self) -> int:
        """Release the group, killing remaining descendants; return their count."""
        if self._closed:
            return 0
        self._closed = True
        if self._job:
            try:
                capacity = 64
                while True:

                    class ProcessIDs(ctypes.Structure):
                        _fields_ = [
                            ("assigned", wintypes.DWORD),
                            ("listed", wintypes.DWORD),
                            ("ids", ctypes.c_size_t * capacity),
                        ]

                    members = ProcessIDs()
                    if self._kernel.QueryInformationJobObject(
                        self._job, 3, ctypes.byref(members), ctypes.sizeof(members), None
                    ):
                        # Job membership can briefly retain terminated processes,
                        # including Python's venv launcher/interpreter pair.
                        alive = 0
                        deadline = time.monotonic() + 0.25
                        for pid in members.ids[: members.listed]:
                            if pid == self.process.pid:
                                continue
                            handle = self._kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
                            if not handle:
                                if ctypes.get_last_error() != 87:  # Already gone
                                    alive += 1
                                continue
                            try:
                                # Windows redirectors may expose the exit code
                                # before their interpreter's final teardown signals.
                                grace_ms = max(0, int((deadline - time.monotonic()) * 1000))
                                wait = self._kernel.WaitForSingleObject(handle, grace_ms)
                                if wait == 258:  # WAIT_TIMEOUT: still running
                                    alive += 1
                                elif wait != 0:
                                    raise ctypes.WinError(ctypes.get_last_error())
                            finally:
                                self._kernel.CloseHandle(handle)
                        return alive
                    error = ctypes.get_last_error()
                    if error != 234:  # ERROR_MORE_DATA
                        raise ctypes.WinError(error)
                    capacity = max(capacity * 2, members.assigned)
            finally:
                self._kernel.CloseHandle(self._job)
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
            return 1
        except ProcessLookupError:
            return 0
