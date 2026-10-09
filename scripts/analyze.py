#!/usr/bin/env python3
"""Measure the groove of reference tracks so Strudel patterns can be built from numbers.

Per track: bar grid, 2-bar drum templates (kick / snare / hat), hat swing,
spectral balance, energy over time, and the bass line (pitch per 16th).
Assumes a fixed tempo (electronic, quantized) and does not detect it: pass --bpm (default 130).
Writes <track>.analysis.json beside each file.

Usage:
  .venv/bin/python scripts/analyze.py --bpm 128 references/*.aiff
  .venv/bin/python scripts/analyze.py --selftest

Limits, measured on a recording of a Strudel score whose notes were known:
  - snare and hat accent maps: reliable. Swing: +/-3% of a 16th.
  - kick map: a bass note starting after a rest reads as a kick (strength 7-8).
  - bass pitch: right for held or phase-continuous notes; can read an octave low.
    A note retriggered every 16th with a phase reset (superdough does this) truly
    moves its energy to multiples of the 16th rate: E1 reads ~F1.
  - bands leak on full mixes: stems (e.g. Demucs) would separate kick from bass.
  - grid: STFT onsets lead by ~20 ms (harmless); "GRID UNRELIABLE" flags tracks
    whose halves disagree.
"""
import argparse
import json
import pathlib
import subprocess

import librosa
import numpy as np
from scipy.ndimage import maximum_filter1d
from scipy.signal import butter, sosfilt, sosfiltfilt

SR, HOP, NFFT = 22050, 128, 1024
FPS = SR / HOP
BASS_SR, BASS_HOP = 5512, 128
DRUM_BANDS = {"kick": (40, 120), "snare": (1000, 4000), "hat": (7000, 11025)}
SPECTRUM_BANDS = {"sub": (20, 60), "bass": (60, 150), "lowmid": (150, 500),
                  "mid": (500, 2000), "himid": (2000, 6000), "high": (6000, 11025)}
WINDOW = (-0.25, 0.5)  # hit search window around each 16th, in steps; wide on the late side for swing
SPARK = "▁▂▃▄▅▆▇█"


def load(path):
    # ffmpeg decodes every format (aiff, alac m4a, mp3, flac) the same way
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def rows(freqs, lo, hi):
    return (freqs >= lo) & (freqs < hi)


def sample_max(env, times, lo, hi):
    """Peak value of env in [t+lo, t+hi] seconds for each t, and the peak's time (parabolic sub-frame)."""
    vals, at = np.zeros(len(times)), np.full(len(times), np.nan)
    for j, t in enumerate(times):
        a, b = max(int(round((t + lo) * FPS)), 1), min(int(round((t + hi) * FPS)) + 1, len(env) - 1)
        if b <= a:
            continue
        i = a + int(np.argmax(env[a:b]))
        if i in (a, b - 1):  # max on the window edge = tail of a neighbour, not an onset
            continue
        p, q, r = env[i - 1], env[i], env[i + 1]
        d = 0.5 * (p - r) / (p - 2 * q + r) if (p - 2 * q + r) < 0 else 0.0
        vals[j], at[j] = q, (i + d) / FPS
    return vals, at


def beat_phase(pulse, beat, lo, hi):
    seg = pulse[int(lo * FPS):int(hi * FPS)]
    k = np.arange(int(len(seg) / FPS / beat) - 1) * beat
    offsets = np.arange(0, beat, 1 / FPS)
    scores = np.array([seg[np.round((o + k) * FPS).astype(int)].mean() for o in offsets])
    return (lo + offsets[scores.argmax()]) % beat, scores.max() / np.median(scores)


def mode(col):
    vals, counts = np.unique(np.nan_to_num(col, nan=-1), return_counts=True)
    i = counts.argmax()
    return int(vals[i]), counts[i] / len(col)


def analyze(y, bpm):
    beat = 60 / bpm
    step, bar = beat / 4, beat * 4
    D = librosa.stft(y, n_fft=NFFT, hop_length=HOP)
    S = np.abs(D)
    freqs = librosa.fft_frequencies(sr=SR, n_fft=NFFT)
    H, P = librosa.decompose.hpss(D, margin=3)  # margin 3: bass-note onsets and kick/bass beating stay out of P
    L = np.log1p(100 * np.abs(P))
    flux = np.maximum(0, np.diff(L, axis=1, prepend=L[:, :1]))
    env = {k: maximum_filter1d(flux[rows(freqs, *r)].sum(0), 3) for k, r in DRUM_BANDS.items()}
    dur = S.shape[1] / FPS

    # Beat phase from kick+snare onsets; the two halves agreeing means the tempo holds.
    pulse = env["kick"] / env["kick"].mean() + env["snare"] / env["snare"].mean()
    o, contrast = beat_phase(pulse, beat, 0, dur)
    o1, _ = beat_phase(pulse, beat, 0, dur / 2)
    o2, _ = beat_phase(pulse, beat, dur / 2, dur)

    # Bar phase: downbeat = kick strong, snare weak; beats 2 and 4 = snare strong.
    bi = np.round(np.arange(o, dur - beat, beat) * FPS).astype(int)
    K = np.array([env["kick"][bi[p::4]].mean() for p in range(4)])
    N = np.array([env["snare"][bi[p::4]].mean() for p in range(4)])
    K, N = K / K.mean(), N / N.mean()
    score = [K[r] - K[(r + 1) % 4] - K[(r + 3) % 4] + N[(r + 1) % 4] + N[(r + 3) % 4] - N[r] - N[(r + 2) % 4]
             for r in range(4)]
    downbeat = o + int(np.argmax(score)) * beat

    bar_starts = np.arange(downbeat, dur - bar, bar)
    power = S ** 2

    def bar_db(r):
        return np.array([10 * np.log10(power[r, int(t * FPS):int((t + bar) * FPS)].mean() + 1e-12)
                         for t in bar_starts])

    low_db, tot_db, hat_db = bar_db(rows(freqs, 40, 120)), bar_db(slice(None)), bar_db(rows(freqs, 7000, 11025))
    # ponytail: "full" = kick-band within 4 dB of its loud end; misses drops that thin the kick
    full = low_db >= np.percentile(low_db, 90) - 4
    parity = np.arange(len(bar_starts)) % 2

    steps = bar_starts[:, None] + np.arange(16)[None, :] * step
    drums, hit_rate, hits = {}, {}, {}
    for name, e in env.items():
        v, at = sample_max(e, steps.ravel(), WINDOW[0] * step, WINDOW[1] * step)
        v, at = v.reshape(steps.shape), at.reshape(steps.shape)
        p95 = np.percentile(v[full], 95)
        hit = v >= 0.35 * p95
        strength = np.minimum(v / p95, 1)  # accents; hit rate alone saturates on dense mixes
        drums[name] = np.concatenate([strength[full & (parity == p)].mean(0) for p in (0, 1)])
        hit_rate[name] = np.concatenate([hit[full & (parity == p)].mean(0) for p in (0, 1)])
        hits[name] = (hit, at - steps)

    # Swing: late shift of the 2nd/4th 16th of each beat, minus the on-8th shift (removes grid bias).
    hit, dev = hits["hat"]
    pos = np.arange(16) % 4

    def med(ps):
        m = hit & full[:, None] & np.isin(pos, ps)[None, :]
        return (float(np.median(dev[m])) if m.any() else float("nan")), int(m.sum())

    (odd, n_odd), (even, n_even) = med([1, 3]), med([0, 2])
    swing = (odd - even) / step

    fmask = np.zeros(S.shape[1], bool)
    for t in bar_starts[full]:
        fmask[int(t * FPS):int((t + bar) * FPS)] = True
    mp = power[:, fmask].mean(1)
    spectrum = {k: float(mp[rows(freqs, *r)].sum() / mp.sum()) for k, r in SPECTRUM_BANDS.items()}
    centroid = float(np.median(librosa.feature.spectral_centroid(S=S[:, fmask], sr=SR)))

    blocks = [slice(i, i + 8) for i in range(0, len(bar_starts), 8)]
    structure = {k: [float(v[b].mean()) for b in blocks] for k, v in
                 (("loud", tot_db), ("low", low_db), ("hat", hat_db))}

    # Bass: harmonic part, low-passed, pitch-tracked; median MIDI note per 16th.
    yh = librosa.istft(H, hop_length=HOP, length=len(y))
    yb = librosa.resample(sosfiltfilt(butter(4, 250, "low", fs=SR, output="sos"), yh),
                          orig_sr=SR, target_sr=BASS_SR)
    f0, voiced, _ = librosa.pyin(yb, fmin=30, fmax=250, sr=BASS_SR, frame_length=512, hop_length=BASS_HOP)
    ft = librosa.times_like(f0, sr=BASS_SR, hop_length=BASS_HOP)
    midi = librosa.hz_to_midi(f0)
    notes = np.full(steps.shape, np.nan)
    for idx, t in np.ndenumerate(steps):
        a, b = np.searchsorted(ft, [t, t + step])
        m = voiced[a:b]
        if m.sum() >= 2:
            notes[idx] = np.round(np.median(midi[a:b][m]))
    bass = [mode(notes[full & (parity == p), s]) for p in (0, 1) for s in range(16)]
    vm = voiced & np.isin(np.searchsorted(bar_starts, ft) - 1, np.flatnonzero(full))
    pcs = np.bincount(np.round(midi[vm]).astype(int) % 12, minlength=12) / max(vm.sum(), 1)

    return dict(bpm=bpm, duration=dur, downbeat=float(downbeat), grid_contrast=float(contrast),
                phase_halves=[float(o1), float(o2)], bars=len(bar_starts), full_bars=int(full.sum()),
                drums={k: v.tolist() for k, v in drums.items()},
                hit_rate={k: v.tolist() for k, v in hit_rate.items()},
                swing=float(swing), swing_n=[n_odd, n_even], swing_even_ms=even * 1000,
                spectrum=spectrum, centroid=centroid, structure=structure,
                bass=[[n, float(c)] for n, c in bass],
                bass_pitch_classes={librosa.midi_to_note(60 + i, octave=False): float(p) for i, p in enumerate(pcs)})


def spark(v):
    v = np.asarray(v)
    span = max(v.max() - v.min(), 3)  # dB; flatter than 3 dB draws flat
    return "".join(SPARK[int((x - v.min()) / span * 7)] for x in v)


def report(name, r):
    digit = lambda f: "." if f < 0.1 else str(min(9, int(f * 10)))
    grp = lambda s: " ".join(s[i:i + 4] for i in range(0, 16, 4))
    print(f"\n== {name}  ({r['duration']:.0f}s, {r['bpm']} BPM)")
    print(f"grid: downbeat {r['downbeat']:.3f}s  contrast {r['grid_contrast']:.2f}x  "
          f"halves {r['phase_halves'][0]:.3f}/{r['phase_halves'][1]:.3f}s  full bars {r['full_bars']}/{r['bars']}")
    a, b = r["phase_halves"]
    drift = abs((a - b + 30 / r["bpm"]) % (60 / r["bpm"]) - 30 / r["bpm"])
    if drift > 0.02:
        print(f"  !! GRID UNRELIABLE: halves disagree by {drift * 1000:.0f} ms; drum/bass templates are suspect")
    print("drums (mean strength per 16th, 0-9 of the band's loud hits; bar 1 | bar 2):")
    for k, v in r["drums"].items():
        s = "".join(digit(f) for f in v)
        print(f"  {k:<6}{grp(s[:16])} | {grp(s[16:])}")
    print(f"swing: {r['swing'] * 100:+.0f}% of a 16th (n={r['swing_n'][0]} odd / {r['swing_n'][1]} even hats,"
          f" on-8th offset {r['swing_even_ms']:+.1f}ms)  -> .swingBy({max(r['swing'], 0):.2f}, 8)")
    print("spectrum: " + "  ".join(f"{k} {v * 100:.0f}%" for k, v in r["spectrum"].items())
          + f"  centroid {r['centroid']:.0f}Hz")
    print("structure (1 char = 8 bars):")
    for k, v in r["structure"].items():
        print(f"  {k:<5} {spark(v)}  ({min(v):.0f}..{max(v):.0f} dB)")
    cell = lambda n: (librosa.midi_to_note(n, unicode=False) if n >= 0 else "~").ljust(4)
    print("bass (most common note per 16th | agreement across full bars):")
    for half in (r["bass"][:16], r["bass"][16:]):
        print("  " + "".join(cell(n) for n, _ in half))
        print("  " + "".join(digit(c).ljust(4) for _, c in half))
    top = sorted(r["bass_pitch_classes"].items(), key=lambda kv: -kv[1])[:4]
    print("bass pitch classes: " + "  ".join(f"{k} {v * 100:.0f}%" for k, v in top))


def selftest():
    bpm, off, sw, bars = 130, 0.2, 0.2, 24
    step = 60 / bpm / 4
    rng = np.random.default_rng(0)
    y = np.zeros(int(SR * (off + bars * 16 * step + 1)))
    t = np.arange(int(0.4 * SR)) / SR
    kick = np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.08) * np.minimum(1, (t[-1] - t) / 0.05)  # faded: no end click
    snare = sosfilt(butter(4, [1000, 4000], "band", fs=SR, output="sos"), rng.standard_normal(len(t))) * np.exp(-t / 0.05)
    hat = sosfilt(butter(8, 7000, "high", fs=SR, output="sos"), rng.standard_normal(len(t))) * np.exp(-t / 0.015)

    def put(sig, at, g=1.0):
        i = int(at * SR)
        y[i:i + len(sig)] += g * sig[:len(y) - i]

    th = np.arange(int(8 * step * SR)) / SR
    for b in range(bars):
        for s in range(16):
            t0 = off + (b * 16 + s) * step
            if s in (0, 10):
                put(kick, t0)
            if s in (4, 12):
                put(snare, t0, 0.5)
            put(hat, t0 + (sw * step if s % 2 else 0), 0.3)
        for half, hz in ((0, 110.0), (1, 98.0)):  # A2 then G2
            put(0.3 * np.sin(2 * np.pi * hz * th) * np.minimum(1, np.minimum(th, th[-1] - th) / 0.01),
                off + (b * 16 + half * 8) * step)

    r = analyze(y.astype(np.float32), bpm)
    report("selftest", r)
    kick_t, snare_t, hat_t = (np.array(r["hit_rate"][k][:16]) for k in ("kick", "snare", "hat"))
    # STFT onsets lead by ~half a window (~20 ms); a wrong beat/bar phase is off by >=115 ms
    assert abs(r["downbeat"] - off) < 0.030, r["downbeat"]
    assert set(np.flatnonzero(kick_t > 0.8)) == {0, 10}, kick_t
    assert set(np.flatnonzero(snare_t > 0.8)) == {4, 12}, snare_t
    assert (hat_t > 0.8).all(), hat_t
    assert abs(r["swing"] - sw) < 0.04, r["swing"]
    names = [librosa.midi_to_note(n, unicode=False) if n >= 0 else "~" for n, _ in r["bass"]]
    assert names[2] == "A2" and names[13] == "G2", names
    print("\nselftest OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", type=pathlib.Path)
    ap.add_argument("--bpm", type=float, default=130)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    for f in args.files:
        res = analyze(load(f), args.bpm)
        report(f.stem, res)
        f.with_suffix(".analysis.json").write_text(json.dumps(res, indent=1))
