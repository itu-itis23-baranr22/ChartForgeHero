"""Where a drum stem is hit, and with which part of the kit.

Each part has its own detector on its own band: the kick below 130 Hz, the snare at 150-600 Hz, the
cymbals at 7-11 kHz. A hit may be several parts at once, a kick with a hi-hat for example, so the
detectors run side by side and their hits are merged into positions afterwards.

**Every threshold is relative to the stem's own strong hits** (the project owner's rule). A detector
takes the peaks of its envelope, calls a high percentile of their heights the level of a strong hit,
and keeps the peaks that reach a share of it. So the same pattern played louder or softer gives the
same hits, and nothing fixes how many hits there are: a busy song keeps all of its hits. A threshold
at a percentile of the envelope itself would do that, and is not used.

Cymbals are told apart by how long they ring: a closed hi-hat dies within a few tens of milliseconds,
a ride rings on. A crash is a loud cymbal that rings on together with a kick. Toms are snare-band hits
without the snare's noise. Toms and crash cannot be measured on the one reference song, so builds
mark them as not verified.

All values are in ``drum_hits.toml``. Nothing there can loosen a hard rule: the limits on what a
position may hold live in the code that writes the chart.
"""

from __future__ import annotations

import time
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path

import librosa
import numpy as np
from scipy.ndimage import maximum_filter1d
from scipy.signal import find_peaks

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import HOP_LENGTH
from chartgen.core.drums import GEM_FOR_PIECE, DrumGem, DrumPiece

CONFIG_PATH = Path(__file__).with_name("drum_hits.toml")
_SILENT_RMS = 1e-4
_EPS = 1e-12
_LOW_FFT = 2048
"""The kick's band is narrow and low, so it needs the finer frequency steps."""
_HIGH_FFT = 1024
_LOUDEST_PERCENTILE = 99.9
_CANDIDATE_FLOOR = 0.02
"""Peaks below this share of the envelope's loudest moments are ripple, not candidates."""


@dataclass(frozen=True)
class BandDetector:
    """One part of the kit found by the rise of energy in one band."""

    low_hz: float
    high_hz: float
    strong_percentile: float
    """The level of a strong hit: this percentile of the heights of the band's peaks."""
    ratio: float
    """A hit must reach this share of a strong hit."""
    latency_s: float
    """How far the envelope's peak trails the attack; subtracted from every time."""


@dataclass(frozen=True)
class CymbalKinds:
    ring_probe_s: float
    """How long after the hit the ring is measured, or less if the next cymbal comes sooner."""
    hihat_max_ring: float
    """A cymbal whose high band falls below this share of its peak by the probe is a hi-hat."""
    hihat_with_kick_max_ring: float
    hihat_with_kick_min_strength: float
    """So is one that comes with a kick, is at least this loud against the cymbals' strong hits, and falls
    below ``hihat_with_kick_max_ring``: a hi-hat played with the kick rises over the wash of the kit."""
    crash_probe_s: float
    crash_min_ring: float
    """A crash still rings at this share of its peak this long after the hit..."""
    crash_min_strength: float
    """...is this loud against the cymbals' strong hits, and comes with a kick. The rest are rides."""


@dataclass(frozen=True)
class TomRule:
    noise_low_hz: float
    noise_high_hz: float
    max_noise_ratio: float
    """A snare-band hit whose noise band stays below this share of its body band is a tom."""
    max_low_ratio: float
    """Unless the kick's band holds more than this many times what the body band above it holds:
    then it is a kick's body."""
    body_low_hz: float
    body_high_hz: float
    high_tom_min_hz: float
    """A tom pitched at or above this is the high tom."""
    floor_tom_max_hz: float
    """At or below this, the floor tom. In between, the mid tom."""


@dataclass(frozen=True)
class DrumHitConfig:
    kick: BandDetector
    snare: BandDetector
    cymbal: BandDetector
    cymbal_kinds: CymbalKinds
    tom: TomRule
    gate_db: float
    """Frames this far below the stem's loud level are silence: hits there are bleed."""
    merge_window_s: float
    """Hits of different parts this close together are one position."""
    min_gap_s: float
    """Two hits of one part closer than this are one hit."""
    snare_over_kick: float
    """A snare-band hit counts only if its band rises at least this many times as much as the kick's
    band at that moment, both read from one spectrum: a kick's body leaks into the snare band."""
    kick_over_snare: float
    """A kick counts only if its band rises at least this many times as much as the snare's band: a
    snare's noise reaches down into the kick's band, if less than a kick reaches up."""
    cymbal_min_db: float
    """A cymbal hit's high band must come within this many decibels of the stem's loud level, taken as a
    flat spectrum at the stem's loud RMS: a pure low drum has little spectrum to average, so not its mean."""


def _section(cls: type, values: object, name: str, path: Path) -> object:
    if not isinstance(values, dict):
        raise ValueError(f"{path.name}: [{name}] must be a table")
    expected = {item.name for item in fields(cls)}
    if set(values) != expected:
        raise ValueError(f"{path.name}: [{name}] expects keys {sorted(expected)}, got {sorted(values)}")
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{path.name}: {name}.{key} must be a number")
    return cls(**{key: float(value) for key, value in values.items()})


def load_config(path: Path = CONFIG_PATH) -> DrumHitConfig:
    """Read the settings file.

    Raises:
        ValueError: If a value is missing, unknown or out of range.
    """
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    tables = {"kick": BandDetector, "snare": BandDetector, "cymbal": BandDetector,
              "cymbal_kinds": CymbalKinds, "tom": TomRule}
    plain = {"gate_db", "merge_window_s", "min_gap_s", "snare_over_kick", "kick_over_snare", "cymbal_min_db"}
    if set(values) != set(tables) | plain:
        raise ValueError(f"{path.name}: expected {sorted(set(tables) | plain)}, got {sorted(values)}")
    parts = {name: _section(cls, values[name], name, path) for name, cls in tables.items()}
    for name in plain:
        if isinstance(values[name], bool) or not isinstance(values[name], (int, float)):
            raise ValueError(f"{path.name}: {name} must be a number")
    config = DrumHitConfig(**parts, **{name: float(values[name]) for name in plain})  # type: ignore[arg-type]
    _check_ranges(config, path)
    return config


def _check_ranges(config: DrumHitConfig, path: Path) -> None:
    nyquist = ANALYSIS_SAMPLERATE / 2
    for name in ("kick", "snare", "cymbal"):
        band: BandDetector = getattr(config, name)
        if not 0 < band.low_hz < band.high_hz <= nyquist:
            raise ValueError(f"{path.name}: [{name}] needs 0 < low_hz < high_hz <= {nyquist:g}")
        if not 50 <= band.strong_percentile <= 100:
            raise ValueError(f"{path.name}: {name}.strong_percentile must be 50-100")
        if not 0 < band.ratio <= 1:
            raise ValueError(f"{path.name}: {name}.ratio must be in (0, 1]")
        if not 0 <= band.latency_s < 0.1:
            raise ValueError(f"{path.name}: {name}.latency_s must be 0-0.1 s")
    kinds = config.cymbal_kinds
    if not 0 < kinds.ring_probe_s < kinds.crash_probe_s <= 2.0:
        raise ValueError(f"{path.name}: need 0 < ring_probe_s < crash_probe_s <= 2")
    for key in ("hihat_max_ring", "hihat_with_kick_max_ring", "crash_min_ring", "crash_min_strength"):
        if not 0 < getattr(kinds, key) <= 1:
            raise ValueError(f"{path.name}: cymbal_kinds.{key} must be in (0, 1]")
    if not kinds.hihat_with_kick_min_strength > 0:
        raise ValueError(f"{path.name}: cymbal_kinds.hihat_with_kick_min_strength must be positive")
    tom = config.tom
    if not (0 < tom.body_low_hz < tom.body_high_hz and 0 < tom.noise_low_hz < tom.noise_high_hz <= nyquist):
        raise ValueError(f"{path.name}: [tom] bands are out of order")
    if not tom.floor_tom_max_hz < tom.high_tom_min_hz:
        raise ValueError(f"{path.name}: tom.floor_tom_max_hz must be below tom.high_tom_min_hz")
    if not 0 <= tom.max_noise_ratio <= 1:
        raise ValueError(f"{path.name}: tom.max_noise_ratio must be 0-1")
    if not tom.max_low_ratio > 0:
        raise ValueError(f"{path.name}: tom.max_low_ratio must be positive")
    if not -80 <= config.gate_db < 0:
        raise ValueError(f"{path.name}: gate_db must be -80 to 0")
    if not 0 < config.merge_window_s <= 0.06 or not 0 < config.min_gap_s <= 0.2:
        raise ValueError(f"{path.name}: merge_window_s must be at most 0.06 s, min_gap_s at most 0.2 s")
    if not 0 <= config.snare_over_kick <= 10 or not 0 <= config.kick_over_snare <= 10:
        raise ValueError(f"{path.name}: snare_over_kick and kick_over_snare must be 0-10")
    if not -80 <= config.cymbal_min_db < 0:
        raise ValueError(f"{path.name}: cymbal_min_db must be -80 to 0")


@dataclass(frozen=True)
class DrumHit:
    """One position: the parts of the kit hit together."""

    time_s: float
    pieces: tuple[DrumPiece, ...]
    strength: float
    """The loudest part, as a share of that part's strong hits."""

    @property
    def gems(self) -> tuple[DrumGem, ...]:
        return tuple(sorted({GEM_FOR_PIECE[piece] for piece in self.pieces}, key=_gem_order))


def _gem_order(gem: DrumGem) -> tuple[int, bool]:
    return gem.lane, gem.cymbal


@dataclass(frozen=True)
class DrumAnalysis:
    hits: tuple[DrumHit, ...]
    strong_levels: Mapping[str, float]
    """The level each detector called a strong hit, in its own envelope's units."""
    detector_hits: Mapping[str, int]
    """How many hits each detector found before merging."""
    seconds: float
    """How long the analysis took."""


@dataclass(frozen=True)
class _Found:
    time_s: float
    part: str
    relative: float
    frame: int


def _frames_to_times(frames: np.ndarray, latency_s: float) -> np.ndarray:
    return librosa.frames_to_time(frames, sr=ANALYSIS_SAMPLERATE, hop_length=HOP_LENGTH) - latency_s


@dataclass(frozen=True)
class _Spectrum:
    magnitude: np.ndarray
    freqs: np.ndarray

    def rows(self, low: float, high: float) -> slice:
        start, stop = np.searchsorted(self.freqs, [low, high], side="left")
        return slice(int(start), int(stop))

    def band(self, low: float, high: float) -> np.ndarray:
        """The rows from ``low`` up to ``high``. A view: the frequencies are in order."""
        return self.magnitude[self.rows(low, high)]


def _spectrum(mono: np.ndarray, n_fft: int) -> _Spectrum:
    magnitude = np.abs(librosa.stft(mono, n_fft=n_fft, hop_length=HOP_LENGTH))
    return _Spectrum(magnitude, librosa.fft_frequencies(sr=ANALYSIS_SAMPLERATE, n_fft=n_fft))


def _linear_flux(band: np.ndarray) -> np.ndarray:
    """Spectral flux of one band on linear magnitudes: it grows with the hit, so loud beats quiet."""
    if band.shape[0] == 0:
        return np.zeros(band.shape[1])
    return np.r_[0.0, np.maximum(np.diff(band, axis=1), 0.0).sum(axis=0)]


def _log_flux(mono: np.ndarray, low: float, high: float) -> np.ndarray:
    """Spectral flux of one band on decibels. Cymbals span a wide range of loudness, from a closed
    hi-hat to a crash, and on a linear scale the crashes would hide the hi-hats."""
    return librosa.onset.onset_strength(
        y=mono, sr=ANALYSIS_SAMPLERATE, hop_length=HOP_LENGTH, n_fft=_HIGH_FFT,
        fmin=low, fmax=high, n_mels=32,
    )


def _relative_peaks(envelope: np.ndarray, band: BandDetector, min_gap_s: float) -> tuple[np.ndarray, np.ndarray, float]:
    """Return the peaks that reach ``band.ratio`` of a strong hit, their share of it, and that level.

    Only peaks above a tiny floor count towards the strong level, or the ripple between hits, whose
    amount says nothing about the hits, would pull it down.
    """
    distance = max(1, int(round(min_gap_s * ANALYSIS_SAMPLERATE / HOP_LENGTH)))
    loudest = float(np.percentile(envelope, _LOUDEST_PERCENTILE)) if envelope.size else 0.0
    candidates, _ = find_peaks(envelope, distance=distance, height=max(_EPS, _CANDIDATE_FLOOR * loudest))
    if candidates.size == 0:
        return candidates, np.empty(0), 0.0
    strong = float(np.percentile(envelope[candidates], band.strong_percentile))
    if strong <= _EPS:
        return np.empty(0, dtype=np.int64), np.empty(0), 0.0
    peaks = candidates[envelope[candidates] >= band.ratio * strong]
    return peaks, envelope[peaks] / strong, strong


def _ring(level: np.ndarray, frame: int, probe_frames: int) -> float:
    """How much of its peak ``level`` keeps ``probe_frames`` after a hit at ``frame``."""
    if frame >= level.size:
        return 0.0
    peak_at = frame + int(np.argmax(level[frame : frame + 4]))
    peak = float(level[peak_at])
    if peak <= _EPS:
        return 0.0
    return float(level[min(peak_at + max(1, probe_frames), level.size - 1)]) / peak


@dataclass(frozen=True)
class _Bands:
    """What naming the parts needs, cut out of the spectra once."""

    air: np.ndarray
    body: np.ndarray
    noise: np.ndarray
    kick: np.ndarray
    """The kick's band, from the same spectrum as ``above_kick`` so that the two compare."""
    above_kick: np.ndarray
    """The body band above the kick's band."""
    pitch: np.ndarray
    pitch_freqs: np.ndarray
    kick_flux: np.ndarray
    snare_flux: np.ndarray
    """The rise in the kick's and the snare's bands, from one spectrum, so that the two compare."""
    air_floor: float
    """A cymbal's high band must reach this level, on a linear scale."""


def detect_drum_hits(
    mono: np.ndarray,
    config: DrumHitConfig | None = None,
) -> DrumAnalysis:
    """Find the hits of a mono drum stem at :data:`ANALYSIS_SAMPLERATE`. Silence gives none."""
    started = time.perf_counter()
    cfg = config or load_config()
    empty = DrumAnalysis((), {}, {}, 0.0)
    if mono.size < _LOW_FFT:
        return empty
    rms = librosa.feature.rms(y=mono, frame_length=_HIGH_FFT, hop_length=HOP_LENGTH)[0]
    loud = float(np.percentile(rms, 95))
    if loud < _SILENT_RMS:
        return empty
    # Look a few frames ahead so the gate does not cut off the attack itself.
    gate = maximum_filter1d(rms, size=5, origin=-2) >= loud * 10.0 ** (cfg.gate_db / 20.0)

    low = _spectrum(mono, _LOW_FFT)
    high = _spectrum(mono, _HIGH_FFT)
    envelopes = {
        "kick": _linear_flux(low.band(cfg.kick.low_hz, cfg.kick.high_hz)),
        "snare": _linear_flux(high.band(cfg.snare.low_hz, cfg.snare.high_hz)),
        "cymbal": _log_flux(mono, cfg.cymbal.low_hz, cfg.cymbal.high_hz),
    }
    frames = min(gate.size, *(envelope.size for envelope in envelopes.values()))
    found: list[_Found] = []
    strong_levels: dict[str, float] = {}
    counts: dict[str, int] = {}
    for part, envelope in envelopes.items():
        band: BandDetector = getattr(cfg, part)
        gated = np.where(gate[:frames], envelope[:frames], 0.0)
        peaks, relative, strong = _relative_peaks(gated, band, cfg.min_gap_s)
        strong_levels[part] = strong
        counts[part] = int(peaks.size)
        times = _frames_to_times(peaks, band.latency_s)
        found.extend(
            _Found(float(t), part, float(r), int(f)) for t, r, f in zip(times, relative, peaks) if t >= 0
        )

    tom = cfg.tom
    pitch_rows = low.rows(tom.body_low_hz, tom.body_high_hz)
    air = high.band(cfg.cymbal.low_hz, ANALYSIS_SAMPLERATE / 2 + 1).mean(axis=0)
    bands = _Bands(
        air=air,
        body=high.band(tom.body_low_hz, tom.body_high_hz).sum(axis=0),
        noise=high.band(tom.noise_low_hz, tom.noise_high_hz).sum(axis=0),
        kick=high.band(cfg.kick.low_hz, cfg.kick.high_hz).sum(axis=0),
        above_kick=high.band(cfg.kick.high_hz, max(tom.body_high_hz, cfg.kick.high_hz + 1)).sum(axis=0),
        pitch=low.magnitude[pitch_rows],
        pitch_freqs=low.freqs[pitch_rows],
        kick_flux=_linear_flux(high.band(cfg.kick.low_hz, cfg.kick.high_hz)),
        snare_flux=envelopes["snare"],
        # A flat spectrum at the stem's loud level would show this magnitude in every bin of a Hann STFT.
        air_floor=loud * np.sqrt(3 * _HIGH_FFT / 8) * 10.0 ** (cfg.cymbal_min_db / 20.0),
    )
    hits = _merge(found, cfg, bands)
    return DrumAnalysis(tuple(hits), strong_levels, counts, time.perf_counter() - started)


def _merge(found: list[_Found], cfg: DrumHitConfig, bands: _Bands) -> list[DrumHit]:
    """Group the detectors' hits into positions and name each part."""
    found.sort(key=lambda item: (item.time_s, item.part))
    groups: list[dict[str, _Found]] = []
    starts: list[float] = []
    for item in found:
        if groups and item.time_s - starts[-1] <= cfg.merge_window_s:
            current = groups[-1]
            if item.part not in current or item.relative > current[item.part].relative:
                current[item.part] = item
            continue
        groups.append({item.part: item})
        starts.append(item.time_s)

    for group in groups:
        _drop_leaks(group, cfg, bands)
    cymbal_frames = [group["cymbal"].frame for group in groups if "cymbal" in group]
    next_cymbal = dict(zip(cymbal_frames, [*cymbal_frames[1:], None]))
    hits: list[DrumHit] = []
    for group in groups:
        pieces: list[DrumPiece] = []
        if "kick" in group:
            pieces.append(DrumPiece.KICK)
        if "snare" in group:
            piece = _snare_or_tom(group["snare"].frame, cfg.tom, bands, "kick" in group)
            if piece is None:
                del group["snare"]
            else:
                pieces.append(piece)
        if "cymbal" in group:
            hit = group["cymbal"]
            pieces.append(_cymbal_kind(hit, next_cymbal[hit.frame], "kick" in group, cfg.cymbal_kinds, bands))
        if not group:
            continue
        time_s = next(group[part].time_s for part in _TIMING_ORDER if part in group)
        strength = max(item.relative for item in group.values())
        hits.append(DrumHit(time_s, tuple(pieces), strength))
    return hits


_TIMING_ORDER = ("snare", "cymbal", "kick")
"""Whose time a position takes. The kick's detector reads a longer window, so it places a hit less exactly."""


def _drop_leaks(group: dict[str, _Found], cfg: DrumHitConfig, bands: _Bands) -> None:
    """Remove the parts that are another drum heard in the wrong band."""
    # A snare's noise reaches down into the kick's band, if less than a kick reaches up into the snare's.
    if "kick" in group:
        frame = group["kick"].frame
        if _around(bands.kick_flux, frame) < cfg.kick_over_snare * _around(bands.snare_flux, frame):
            del group["kick"]
    if "snare" in group:
        frame = group["snare"].frame
        if _around(bands.snare_flux, frame) < cfg.snare_over_kick * _around(bands.kick_flux, frame):
            del group["snare"]
    # On a log scale another drum's click can look like a cymbal in a quiet high band.
    if "cymbal" in group and _top(bands.air, group["cymbal"].frame) < bands.air_floor:
        del group["cymbal"]


def _cymbal_kind(
    hit: _Found, following: int | None, with_kick: bool, kinds: CymbalKinds, bands: _Bands
) -> DrumPiece:
    """A hi-hat dies quickly, or rises loud over the kit with the kick (reference tuning step 4, SPEC 44); a
    crash is loud, rings on and comes with a kick; the rest is a ride."""
    fps = ANALYSIS_SAMPLERATE / HOP_LENGTH
    probe = int(kinds.ring_probe_s * fps)
    if following is not None:
        probe = max(1, min(probe, following - hit.frame - 1))
    ring = _ring(bands.air, hit.frame, probe)
    if ring < kinds.hihat_max_ring or (
        with_kick
        and hit.relative >= kinds.hihat_with_kick_min_strength
        and ring < kinds.hihat_with_kick_max_ring
    ):
        return DrumPiece.HI_HAT
    if (
        with_kick
        and hit.relative >= kinds.crash_min_strength
        and _ring(bands.air, hit.frame, int(kinds.crash_probe_s * fps)) >= kinds.crash_min_ring
    ):
        return DrumPiece.CRASH
    return DrumPiece.RIDE


def _top(level: np.ndarray, frame: int) -> float:
    return float(level[frame : frame + 3].max()) if frame < level.size else 0.0


def _around(level: np.ndarray, frame: int) -> float:
    """The top of ``level`` near ``frame``: the bands' peaks need not fall on the same frame."""
    return float(level[max(0, frame - 2) : frame + 4].max()) if frame < level.size else 0.0


def _snare_or_tom(frame: int, rule: TomRule, bands: _Bands, with_kick: bool) -> DrumPiece | None:
    """A snare-band hit is a snare unless it has next to no noise: then it is a tom, or nothing.

    The snare's wires make noise well above its body. A tom is almost a pitched tone. Measured as levels,
    not rises: a ride ringing over the hit would hide a rise of the noise band. A noiseless hit together
    with a kick, or one whose energy lies mostly below the tom's band, is a kick's own body, as with an
    808, and no drum of its own.
    """
    body = _top(bands.body, frame)
    if body <= _EPS or _top(bands.noise, frame) >= rule.max_noise_ratio * body:
        return DrumPiece.SNARE
    if with_kick or _top(bands.kick, frame) > rule.max_low_ratio * _top(bands.above_kick, frame):
        return None
    span = bands.pitch[:, frame : frame + 4]
    pitch = float(bands.pitch_freqs[int(np.argmax(span.sum(axis=1)))]) if span.size else 0.0
    if pitch >= rule.high_tom_min_hz:
        return DrumPiece.HIGH_TOM
    if pitch <= rule.floor_tom_max_hz:
        return DrumPiece.FLOOR_TOM
    return DrumPiece.MID_TOM
