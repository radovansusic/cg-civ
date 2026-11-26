"""Original music: slow epic strategy-game style cue (Dm-Bb-F-C), strings pad, horn line, timpani. Royalty free, made here."""
import numpy as np, wave
SR, DUR = 44100, 13.0
t = np.arange(int(SR * DUR)) / SR
def note(f, start, length, kind='pad', vol=0.2):
    n = int(length * SR); tt = np.arange(n) / SR
    if kind == 'pad':
        w = sum(np.sin(2 * np.pi * f * k * tt + k) / k for k in range(1, 8)) * (1 + 0.003 * np.sin(2 * np.pi * 5 * tt))
        env = np.minimum(1, tt / 0.6) * np.minimum(1, (length - tt) / 0.8)
    elif kind == 'horn':
        w = np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(4 * np.pi * f * tt) + 0.25 * np.sin(6 * np.pi * f * tt)
        w *= 1 + 0.02 * np.sin(2 * np.pi * 5.5 * tt)
        env = np.minimum(1, tt / 0.12) * np.minimum(1, (length - tt) / 0.3)
    else:  # timpani
        w = np.sin(2 * np.pi * f * tt * (1 - 0.08 * tt)) + 0.3 * np.random.randn(n) * np.exp(-tt * 30)
        env = np.exp(-tt * 3.5)
    out = np.zeros_like(t); i = int(start * SR); seg = (w * env * vol)[: len(t) - i]; out[i:i + len(seg)] += seg; return out
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
chords = [[50, 57, 62, 65], [46, 53, 58, 62], [41, 48, 53, 57], [48, 55, 60, 64]]  # Dm Bb F C
mix = np.zeros_like(t)
for i in range(4):
    for m in chords[i]: mix += note(hz(m), i * 3.2, 3.6, 'pad', 0.05)
for st in [0, 3.2, 6.4, 9.6, 11.2]: mix += note(hz(38), st, 2.0, 'timp', 0.35)
mel = [(69, 0.8, 0.8), (72, 1.6, 0.8), (74, 2.4, 1.4), (77, 4.0, 0.8), (76, 4.8, 0.8), (74, 5.6, 1.6), (72, 7.2, 0.8), (74, 8.0, 0.8),
       (77, 8.8, 0.8), (81, 9.6, 1.6), (79, 11.2, 0.6), (77, 11.8, 1.1)]
for m, s0, l in mel: mix += note(hz(m - 12), s0, l, 'horn', 0.09)
# simple reverb
d = int(0.09 * SR); rev = mix.copy()
for k, g in [(1, .35), (2, .2), (3, .12), (5, .07)]: rev[k * d:] += mix[:-k * d] * g
rev *= np.minimum(1, t / 0.3) * np.minimum(1, (DUR - t) / 1.5)
rev = rev / np.max(np.abs(rev)) * 0.8
pcm = (np.repeat(rev[:, None], 2, 1) * 32767).astype(np.int16)
with wave.open('/home/claude/cgciv/video_kratki/muzika.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('ok')
