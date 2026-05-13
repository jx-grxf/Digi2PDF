from __future__ import annotations

import ctypes
import os
import platform
import subprocess
from dataclasses import dataclass

MAX_PARALLEL_WORKERS = 4
MEMORY_GIB_PER_WORKER = 2.5


@dataclass(frozen=True)
class WorkerRecommendation:
    selected_books: int
    cpu_count: int
    available_memory_gib: float | None
    max_workers: int
    recommended_workers: int

    @property
    def summary(self) -> str:
        memory = (
            "unknown available memory"
            if self.available_memory_gib is None
            else f"{self.available_memory_gib:.1f} GiB available memory"
        )
        return (
            f"Recommended: {self.recommended_workers} parallel Chrome sessions "
            f"based on {self.cpu_count} CPU cores and {memory}."
        )


def recommend_workers(selected_books: int) -> WorkerRecommendation:
    selected_books = max(0, selected_books)
    cpu_count = max(1, os.cpu_count() or 1)
    max_workers = min(selected_books, MAX_PARALLEL_WORKERS)
    if max_workers <= 1:
        return WorkerRecommendation(
            selected_books=selected_books,
            cpu_count=cpu_count,
            available_memory_gib=_available_memory_gib(),
            max_workers=max_workers,
            recommended_workers=max_workers,
        )

    memory_gib = _available_memory_gib()
    cpu_workers = max(1, cpu_count // 2)
    memory_workers = (
        max(1, int(memory_gib // MEMORY_GIB_PER_WORKER))
        if memory_gib is not None
        else max_workers
    )
    recommended = min(max_workers, cpu_workers, memory_workers)
    if recommended < 2 and (memory_gib is None or memory_gib >= MEMORY_GIB_PER_WORKER * 2):
        recommended = 2
    return WorkerRecommendation(
        selected_books=selected_books,
        cpu_count=cpu_count,
        available_memory_gib=memory_gib,
        max_workers=max_workers,
        recommended_workers=recommended,
    )


def parse_manual_worker_count(value: str, *, selected_books: int) -> int:
    try:
        workers = int(value)
    except ValueError as error:
        raise ValueError("Session count must be a whole number.") from error

    max_workers = min(max(1, selected_books), MAX_PARALLEL_WORKERS)
    if workers < 1:
        raise ValueError("Session count must be at least 1.")
    if workers > selected_books:
        raise ValueError(f"Session count cannot exceed selected books ({selected_books}).")
    if workers > max_workers:
        raise ValueError(f"Session count cannot exceed the safe limit ({max_workers}).")
    return workers


def _available_memory_gib() -> float | None:
    system = platform.system()
    if system == "Darwin":
        return _darwin_memory_gib()
    if system == "Linux":
        return _linux_memory_gib()
    if system == "Windows":
        return _windows_memory_gib()
    return None


def _darwin_memory_gib() -> float | None:
    try:
        output = subprocess.check_output(("sysctl", "-n", "hw.memsize"), text=True).strip()
        return int(output) / 1024**3
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def _linux_memory_gib() -> float | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as meminfo:
            for line in meminfo:
                if line.startswith("MemAvailable:"):
                    kib = int(line.split()[1])
                    return kib / 1024**2
    except (OSError, ValueError, IndexError):
        return None
    return None


def _windows_memory_gib() -> float | None:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    try:
        ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    except AttributeError:
        return None
    if not ok:
        return None
    return status.ullAvailPhys / 1024**3
