"""Step 4 of the reference tuning: cymbal kinds and lone kicks on lower levels (SPEC 44).

(a) A hi-hat dies quickly, or rises loud over the kit with the kick. The crash stays as it was (loud, with a
    kick, ringing after 0.6 s): a looser rule was right on 55% of train's crashes but 15% of the test set's,
    and the owner chose to keep a wrong green out. The rest is a ride.
(b) A level keeps only a share of the level above's lone kicks, the best by score: a preference.
(c) The lower levels' gem shares come from the train human charts.
"""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from chartgen.audio.drum_hits import CONFIG_PATH as HITS_PATH
from chartgen.audio.drum_hits import _cymbal_kind, _Found, load_config
from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import HOP_LENGTH
from chartgen.chart.drum_difficulty import CONFIG_PATH as LEVELS_PATH
from chartgen.chart.drum_difficulty import _keep_lone_kicks, gems_by_tick, load_drum_config, reduce_drums
from chartgen.core.drums import DrumGem, DrumPiece
from chartgen.core.model import Difficulty, Instrument, Track
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent

FPS = ANALYSIS_SAMPLERATE / HOP_LENGTH
KINDS = load_config().cymbal_kinds
HIT = 10


def air(ring_at_probe: float) -> SimpleNamespace:
    """A high band that peaks at HIT and keeps `ring_at_probe` of its peak ring_probe_s later."""
    probe = int(KINDS.ring_probe_s * FPS)
    tau = probe / -np.log(ring_at_probe)
    frames = np.arange(400, dtype=np.float64)
    level = np.where(frames < HIT, 0.01, np.exp(-(frames - HIT) / tau))
    return SimpleNamespace(air=level)


def kind(ring: float, gap_s: float | None, with_kick: bool = False, strength: float = 0.5) -> DrumPiece:
    following = None if gap_s is None else HIT + int(round(gap_s * FPS))
    return _cymbal_kind(_Found(HIT / FPS, "cymbal", strength, HIT), following, with_kick, KINDS, air(ring))


# ---------------------------------------------------------------- (a) cymbal kinds


def test_the_cymbal_rule_values():
    assert KINDS.ring_probe_s == 0.09 and KINDS.hihat_max_ring == 0.4
    assert KINDS.hihat_with_kick_max_ring == 0.6 and KINDS.hihat_with_kick_min_strength == 0.9
    assert KINDS.crash_probe_s == 0.6 and KINDS.crash_min_ring == 0.3 and KINDS.crash_min_strength == 0.9


@pytest.mark.parametrize(
    "ring,gap_s,with_kick,strength,expected",
    [
        (0.3, 0.25, False, 0.5, DrumPiece.HI_HAT),  # dies quickly
        (0.5, 0.25, True, 0.95, DrumPiece.HI_HAT),  # rises loud with the kick and dies before 0.6
        (0.5, 0.25, True, 0.8, DrumPiece.RIDE),  # with the kick but not loud enough
        (0.5, 0.25, False, 0.95, DrumPiece.RIDE),  # loud but no kick
        (0.9, 0.7, True, 0.95, DrumPiece.CRASH),  # loud, with the kick, still ringing after 0.6 s
        (0.9, 0.7, False, 0.95, DrumPiece.RIDE),  # rings on but no kick
        (0.9, 0.7, True, 0.8, DrumPiece.RIDE),  # with the kick but not loud enough
        (0.75, 0.7, True, 0.95, DrumPiece.RIDE),  # dies away before 0.6 s
    ],
    ids=["hi-hat", "hi-hat with kick", "weak with kick", "loud alone", "crash", "ringing alone", "ringing weak",
         "short ring"],
)
def test_cymbal_kinds(ring, gap_s, with_kick, strength, expected):
    assert kind(ring, gap_s, with_kick, strength) is expected


def test_a_loud_hi_hat_with_the_kick_was_a_ride_before():
    """Before step 4 only the ring decided: this one keeps 0.5 of its peak, so it was a ride."""
    assert kind(0.5, 0.25, with_kick=True, strength=0.95) is DrumPiece.HI_HAT
    before = replace(KINDS, hihat_with_kick_max_ring=0.4)
    found = _Found(HIT / FPS, "cymbal", 0.95, HIT)
    assert _cymbal_kind(found, HIT + 21, True, before, air(0.5)) is DrumPiece.RIDE


@pytest.mark.parametrize(
    "old,new,message",
    [
        ("crash_probe_s = 0.6", "crash_probe_s = 0.05", "crash_probe_s"),
        ("hihat_with_kick_max_ring = 0.6", "hihat_with_kick_max_ring = 0.0", "hihat_with_kick_max_ring"),
        ("hihat_with_kick_min_strength = 0.9", "hihat_with_kick_min_strength = 0.0", "hihat_with_kick_min_strength"),
        ("crash_min_strength = 0.9", "crash_min_strength = 1.5", "crash_min_strength"),
        ("hihat_with_kick_max_ring = 0.6\n", "", "expects keys"),
    ],
)
def test_the_cymbal_settings_are_checked(tmp_path, old, new, message):
    text = HITS_PATH.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "drum_hits.toml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_config(path)


# ---------------------------------------------------------------- (b) lone kicks


def test_each_level_keeps_its_share_of_lone_kicks():
    config = load_drum_config()
    shares = [config.levels[level].lone_kick_share for level in (Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY)]
    assert shares == [0.75, 0.5, 0.75]


def test_the_best_lone_kicks_stay():
    upper = {0: (DrumGem.KICK,), 96: (DrumGem.KICK,), 192: (DrumGem.RED,), 288: (DrumGem.KICK,), 384: (DrumGem.KICK,)}
    ticks = np.array(sorted(upper))
    scores = np.array([1.0, 0.2, 0.8, 0.6, 0.4])
    metric = ["downbeat", "eighth", "beat", "eighth", "strong_beat"]
    kept, kept_scores, kept_metric = _keep_lone_kicks(ticks, scores, metric, upper, 0.5)
    assert kept.tolist() == [0, 192, 288], "half of the four lone kicks, the best two; the snare is no lone kick"
    assert kept_scores.tolist() == [1.0, 0.8, 0.6] and kept_metric == ["downbeat", "beat", "eighth"]
    assert _keep_lone_kicks(ticks, scores, metric, upper, 1.0)[0].tolist() == ticks.tolist()
    assert _keep_lone_kicks(ticks, scores, metric, upper, 0.0)[0].tolist() == [192]


def groove_with_lone_kicks() -> Track:
    """8 bars at 120 BPM: kick + hi-hat on 1, snare + hi-hat on 2 and 4, a lone kick on 3, where it scores
    as high as a downbeat and stays unless the share takes it out."""
    r = 192
    notes = []
    for bar in range(8):
        start = bar * 4 * r
        for beat, gems in enumerate(((DrumGem.KICK, DrumGem.YELLOW_CYMBAL), (DrumGem.RED, DrumGem.YELLOW_CYMBAL),
                                     (DrumGem.KICK,), (DrumGem.RED, DrumGem.YELLOW_CYMBAL))):
            notes += [gem.note(start + beat * r) for gem in gems]
    return Track(Instrument.DRUMS, Difficulty.EXPERT, notes)


def test_medium_keeps_fewer_lone_kicks_with_a_lower_share():
    tempo = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4, 4)], resolution=192)
    expert = groove_with_lone_kicks()
    config = load_drum_config()

    def medium_lone_kicks(share: float) -> int:
        levels = {level: replace(settings, lone_kick_share=share if level is not Difficulty.EASY else 1.0)
                  for level, settings in config.levels.items()}
        reduced = reduce_drums(expert, tempo, None, replace(config, levels=levels))
        upper = gems_by_tick(reduced[Difficulty.HARD].track)
        medium = gems_by_tick(reduced[Difficulty.MEDIUM].track)
        return sum(1 for tick, gems in medium.items() if gems == (DrumGem.KICK,) and upper[tick] == (DrumGem.KICK,))

    assert medium_lone_kicks(1.0) > 0, "the test must show the lone kicks, or it proves nothing"
    assert medium_lone_kicks(0.0) == 0


@pytest.mark.parametrize("value", ["1.5", "-0.1"])
def test_the_lone_kick_share_must_be_a_share(tmp_path, value):
    text = LEVELS_PATH.read_text(encoding="utf-8").replace("lone_kick_share = 0.5", f"lone_kick_share = {value}", 1)
    path = tmp_path / "drum_difficulty.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="lone_kick_share"):
        load_drum_config(path)


# ---------------------------------------------------------------- (c) soft targets from train


def test_the_gem_shares_are_the_train_humans():
    config = load_drum_config()
    easy = config.levels[Difficulty.EASY].soft_targets.gem_shares
    assert easy[DrumGem.KICK] == 0.100 and easy[DrumGem.GREEN_CYMBAL] == 0.183 and easy[DrumGem.BLUE_CYMBAL] == 0.229
    for level in (Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY):
        assert sum(config.levels[level].soft_targets.gem_shares.values()) == pytest.approx(1.0, abs=0.002)
