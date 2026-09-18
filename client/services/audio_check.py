"""
audio_check.py — Diagnóstico de audio para Alfonso (versión mejorada).

Detecta automáticamente el micrófono integrado del Acer Swift 314 (Realtek)
y muestra qué samplerate acepta, el nivel de señal y si Whisper puede usarlo.

Uso:
    python audio_check.py              # diagnóstico completo
    python audio_check.py --device 1   # prueba un índice específico
    python audio_check.py --live       # monitorización en tiempo real (auto-detecta)
    python audio_check.py --live --device 3
"""

from __future__ import annotations

import argparse
import sys
import time

MISSING = []
for pkg in ["sounddevice", "numpy"]:
    try:
        __import__(pkg)
    except ImportError:
        MISSING.append(pkg)

if MISSING:
    pass
    sys.exit(1)

import numpy as np
import sounddevice as sd

# Importamos las utilidades del AudioService nuevo
try:
    from services.audio import auto_select_device, probe_device_samplerate, TARGET_RATE
except ImportError:
    # Fallback si se ejecuta desde fuera del directorio ui/
    TARGET_RATE = 16_000
    def probe_device_samplerate(dev):
        for rate in [16_000, 44_100, 48_000]:
            try:
                sd.check_input_settings(device=dev, samplerate=rate, channels=1)
                return rate
            except Exception:
                continue
        return 44_100
    def auto_select_device():
        _INTEGRATED = [
            "realtek", "array", "intel", "sst", "integrated", "built-in",
            "amic", "dmic", "smart sound", "intel® smart", "tecnología intel",
            "varios micrófonos",
        ]
        _PENALIZE = [
            "usb", "steam", "mezcla estéreo", "altavoz", "output with",
            "speakers", "loopback", "external",
        ]
        try:
            devices = sd.query_devices()
            best, best_score = None, 0
            for i, d in enumerate(devices):
                if d["max_input_channels"] < 1:
                    continue
                name_lower = d["name"].lower()
                score  = sum(1 for kw in _INTEGRATED if kw in name_lower)
                score -= sum(3 for kw in _PENALIZE   if kw in name_lower)
                if score > best_score:
                    best_score, best = score, i
            return best
        except Exception:
            return None

CHANNELS     = 1
TEST_SECONDS = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record(device: int, samplerate: int, duration: int = TEST_SECONDS) -> np.ndarray:
    data = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=CHANNELS,
        dtype="float32",
        device=device,
    )
    sd.wait()
    return data


def _to_int16_scale(data: np.ndarray) -> np.ndarray:
    """float32 [-1,1] → escala int16 con clip para evitar overflow."""
    return np.abs(np.clip(data.flatten(), -1.0, 1.0)) * 32767


def _amplitude(data: np.ndarray) -> int:
    return int(_to_int16_scale(data).mean())


def _peak(data: np.ndarray) -> int:
    return int(_to_int16_scale(data).max())


def _bar(value: int, max_val: int = 3000, width: int = 40) -> str:
    filled = min(int((value / max_val) * width), width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {value:5d}"


# ---------------------------------------------------------------------------
# Diagnóstico completo
# ---------------------------------------------------------------------------

def run_full_test(auto_device: Optional[int] = None) -> None:
    devices     = sd.query_devices()
    input_devs  = [(i, d) for i, d in enumerate(devices) if d["max_input_channels"] > 0]

    pass
    pass
    pass

    if auto_device is not None:
        name = devices[auto_device]["name"] if auto_device < len(devices) else "?"
        pass
    else:
        pass

    pass
    pass
    pass

    results = []
    for idx, device in input_devs:
        name = device["name"][:38]
        rate = probe_device_samplerate(idx)
        try:
            data   = _record(idx, rate, TEST_SECONDS)
            amp    = _amplitude(data)
            pk     = _peak(data)
            signal = "✓ SEÑAL" if amp > 50 else "  silencio"
            pass
            if amp > 50:
                results.append((idx, device["name"], amp, rate))
        except Exception as exc:
            pass

    pass

    if not results:
        pass
        pass
        pass
        pass
        pass
        pass
        if auto_device is not None:
            pass
        else:
            for idx, _ in input_devs[:3]:
                pass
        return

    best_idx, best_name, best_amp, best_rate = max(results, key=lambda x: x[2])
    pass
    for idx, name, amp, rate in sorted(results, key=lambda x: x[2], reverse=True):
        marker = " ← RECOMENDADO" if idx == best_idx else ""
        pass

    threshold = max(80, best_amp // 4)
    pass
    pass
    pass
    pass
    pass

    if best_rate != TARGET_RATE:
        pass
        pass
        pass

    pass


# ---------------------------------------------------------------------------
# Monitorización en tiempo real
# ---------------------------------------------------------------------------

def live_monitor(device: int) -> None:
    devices = sd.query_devices()
    name    = devices[device]["name"] if device < len(devices) else f"device {device}"
    rate    = probe_device_samplerate(device)

    pass
    pass
    pass
    pass

    try:
        while True:
            try:
                data = _record(device, rate, 1)
                amp  = _amplitude(data)
                pk   = _peak(data)
                if amp < 80:
                    status = "SILENCIO"
                elif amp < 500:
                    status = "BAJO"
                else:
                    status = "BIEN ✓"
                pass
            except Exception as exc:
                pass
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Diagnóstico de audio para Alfonso")
    p.add_argument("--device", type=int, default=None, help="Índice del dispositivo a probar")
    p.add_argument("--live",   action="store_true",    help="Monitorización en tiempo real")
    return p.parse_args()


# typing Optional no importado arriba en el fallback
try:
    from typing import Optional
except ImportError:
    pass


if __name__ == "__main__":
    args       = parse_args()
    auto_dev   = auto_select_device()

    device = args.device if args.device is not None else auto_dev

    if args.live:
        if device is None:
            pass
            sys.exit(1)
        live_monitor(device)
    else:
        run_full_test(auto_dev)
