// Motion: cards fade in/out over 6 frames, springs are critically damped (no bounce).
import {Easing, interpolate, spring} from 'remotion';

export const SLIDE_FRAMES = 6;
export const easeOut = Easing.out(Easing.cubic);

// 0 -> 1 over `len` frames from `start`, eased out, clamped.
export const ramp = (frame: number, start: number, len: number, easing = easeOut) =>
  interpolate(frame, [start, start + len], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing});

// Critically damped spring (no overshoot), 0 before `delay`.
export const settle = (frame: number, fps: number, delay = 0) =>
  frame < delay ? 0 : spring({frame: frame - delay, fps, config: {damping: 200}});
