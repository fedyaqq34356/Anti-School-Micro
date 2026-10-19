import argparse
import json
import math
import random
import sys
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.signal import lfilter, lfilter_zi

RATE = 48000
BLOCK = 480
HOTKEY = "ctrl+windows+m"
CABLE = "CABLE Input"
PROFILE = Path(__file__).with_name("profile.json")


def load_profile():
    try:
        return json.loads(PROFILE.read_text())
    except (OSError, ValueError):
        pass
    r = random.uniform
    profile = {
        "pre": round(r(150, 500), 1),
        "drive": round(r(1.5, 3), 2),
        "bass_freq": round(r(110, 320), 1),
        "bass_gain": round(r(6, 18), 1),
        "harsh_freq": round(r(1500, 4800), 1),
        "harsh_gain": round(r(8, 18), 1),
        "post": round(r(8, 40), 1),
        "bits": round(r(3, 6), 1),
        "rate": round(r(3500, 11000), 1),
    }
    PROFILE.write_text(json.dumps(profile, indent=2))
    return profile


def shelf_low(freq, gain_db, q):
    a = 10 ** (gain_db / 40)
    w = 2 * math.pi * freq / RATE
    cw, sw = math.cos(w), math.sin(w)
    alpha = sw / (2 * q)
    k = 2 * math.sqrt(a) * alpha
    b = [a * ((a + 1) - (a - 1) * cw + k), 2 * a * ((a - 1) - (a + 1) * cw), a * ((a + 1) - (a - 1) * cw - k)]
    d = [(a + 1) + (a - 1) * cw + k, -2 * ((a - 1) + (a + 1) * cw), (a + 1) + (a - 1) * cw - k]
    return np.array(b) / d[0], np.array(d) / d[0]


def peaking(freq, gain_db, q):
    a = 10 ** (gain_db / 40)
    w = 2 * math.pi * freq / RATE
    cw, sw = math.cos(w), math.sin(w)
    alpha = sw / (2 * q)
    b = [1 + alpha * a, -2 * cw, 1 - alpha * a]
    d = [1 + alpha / a, -2 * cw, 1 - alpha / a]
    return np.array(b) / d[0], np.array(d) / d[0]


class Filter:
    def __init__(self, coeffs):
        self.b, self.a = coeffs
        self.zi = lfilter_zi(self.b, self.a) * 0.0

    def __call__(self, x):
        y, self.zi = lfilter(self.b, self.a, x, zi=self.zi)
        return y


class Boost:
    def __init__(self, p):
        self.on = False
        self.env = 0.0
        self.pre = p["pre"]
        self.drive = p["drive"]
        self.post = p["post"]
        self.bass = Filter(shelf_low(p["bass_freq"], p["bass_gain"], 0.7))
        self.harsh = Filter(peaking(p["harsh_freq"], p["harsh_gain"], 0.7))
        self.hold = 0.0
        self.phase = 0.0
        self.step = p["rate"] / RATE
        self.levels = 2 ** (p["bits"] - 1) - 1

    def compress(self, x):
        rms = float(np.sqrt(np.mean(x * x))) + 1e-9
        coef = 0.5 if rms > self.env else 0.9
        self.env = coef * self.env + (1 - coef) * rms
        level = 20 * math.log10(self.env + 1e-9)
        thr, ratio, makeup = -30.0, 20.0, 24.0
        out = thr + (level - thr) / ratio if level > thr else level
        return x * 10 ** ((out - level + makeup) / 20)

    def crush(self, x):
        y = np.empty_like(x)
        for i in range(len(x)):
            self.phase += self.step
            if self.phase >= 1:
                self.phase -= 1
                self.hold = x[i]
            y[i] = self.hold
        return np.round(y * self.levels) / self.levels

    def process(self, x):
        x = x.astype(np.float64)
        x = self.compress(x)
        x = np.clip(x * self.pre, -1, 1)
        x = np.tanh(x * self.drive) / math.tanh(self.drive)
        x = self.bass(x)
        x = self.harsh(x)
        x = np.clip(x * self.post, -1, 1)
        x = self.crush(x)
        return np.clip(x, -0.99, 0.99).astype(np.float32)


def mme_index():
    for i, api in enumerate(sd.query_hostapis()):
        if api["name"] == "MME":
            return i
    return sd.default.hostapi


def find_devices(input_index):
    api = mme_index()
    devices = sd.query_devices()
    out = next(
        (i for i, d in enumerate(devices)
         if d["hostapi"] == api and d["max_output_channels"] > 0 and CABLE.lower() in d["name"].lower()),
        None,
    )
    if out is None:
        sys.exit("Не найден VB-Audio CABLE Input. Установи VB-CABLE и перезагрузи ПК.")
    if input_index is not None:
        return input_index, out
    default_in = sd.default.device[0]
    if default_in is not None and default_in >= 0 and "cable" not in devices[default_in]["name"].lower():
        return default_in, out
    for i, d in enumerate(devices):
        if d["hostapi"] == api and d["max_input_channels"] > 0 and "cable" not in d["name"].lower() \
                and "mapper" not in d["name"].lower():
            return i, out
    sys.exit("Не найден микрофон.")


def beep(on):
    try:
        import winsound
        winsound.Beep(1400 if on else 600, 120)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Mic BOOST")
    parser.add_argument("--list", action="store_true", help="показать устройства")
    parser.add_argument("--input", type=int, help="номер микрофона из --list")
    parser.add_argument("--on", action="store_true", help="сразу включить BOOST")
    parser.add_argument("--hotkey", default=HOTKEY, help=f"горячая клавиша (по умолчанию {HOTKEY})")
    args = parser.parse_args()

    if args.list:
        api = mme_index()
        for i, d in enumerate(sd.query_devices()):
            if d["hostapi"] == api:
                kind = "in " if d["max_input_channels"] else "out"
                print(f"{i:3}  {kind}  {d['name']}")
        return

    inp, out = find_devices(args.input)
    devices = sd.query_devices()
    boost = Boost(load_profile())
    boost.on = args.on
    lock = threading.Lock()

    def callback(indata, outdata, frames, time, status):
        x = indata[:, 0]
        with lock:
            y = boost.process(x) if boost.on else x
        outdata[:] = np.repeat(y[:, None], outdata.shape[1], axis=1)

    def toggle():
        with lock:
            boost.on = not boost.on
            state = boost.on
        beep(state)
        print("BOOST ON" if state else "BOOST OFF", flush=True)

    try:
        import keyboard
        keyboard.add_hotkey(args.hotkey, toggle)
    except Exception as e:
        print(f"Горячая клавиша не работает: {e}")

    print(f"Микрофон: {devices[inp]['name']}")
    print(f"Выход:    {devices[out]['name']}")
    print(f"{args.hotkey} — вкл/выкл BOOST, Enter — тоже, Ctrl+C — выход")
    print("BOOST ON" if boost.on else "BOOST OFF", flush=True)

    with sd.Stream(device=(inp, out), samplerate=RATE, blocksize=BLOCK,
                   channels=(1, min(2, devices[out]["max_output_channels"])),
                   dtype="float32", callback=callback):
        try:
            if sys.stdin is None or not sys.stdin.isatty():
                threading.Event().wait()
            while True:
                input()
                toggle()
        except (KeyboardInterrupt, EOFError):
            pass


if __name__ == "__main__":
    main()
