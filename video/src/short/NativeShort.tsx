// A vertical Short (guides/03-on-screen.md). Everything comes from
// work/shorts/NN/timeline-{A,B}.json, passed as props: the face video (crop and
// zoom baked in by tools/shorts.py), word-by-word captions under the chin, the
// hook card at the top for the first 3 s, a follower's question as a comment
// card while it is read out, and the CTA card at the end when there is one.
import React from 'react';
import {AbsoluteFill, Audio, CalculateMetadataFunction, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {loadFont} from '@remotion/google-fonts/FiraSans';
import {C} from '../theme';
import {SLIDE_FRAMES, ramp, settle} from '../anim';

const heavy = loadFont('normal', {weights: ['600', '700', '800'], subsets: ['greek', 'latin']}).fontFamily;

export const W = 1080;
export const H = 1920;
const TOP = 240; // under the platforms' top bar (y < 220)
const CAP_H = 64;
const CAP_W = 820;

type Page = {start: number; end: number; words: {text: string; start: number}[]};
type Question = {label: string; top: number; start: number; end: number; words: {text: string; start: number}[]};
type Cta = {kind: 'bio' | 'comment'; keyword?: string; start: number; end: number; lines: string[]};
export type ShortData = {
  slug: string;
  fps: number;
  durationInFrames: number;
  video: string;
  audio: string;
  capTop: number;
  hook: {text: string; until: number} | null;
  question: Question | null;
  cta: Cta | null;
  captions: Page[];
  sfx: {at: number; sound: string; volume: number}[];
  jumpCuts: number[];
};
export type ShortProps = {data: ShortData; safe?: boolean};

export const EMPTY_SHORT: ShortData = {
  slug: 'empty', fps: 30, durationInFrames: 30, video: '', audio: '', capTop: 1300,
  hook: {text: 'Το kit δουλεύει;', until: 30}, question: null, cta: null,
  captions: [{start: 0, end: 30, words: [{text: 'Ναι,', start: 0}, {text: 'δουλεύει!', start: 12}]}], sfx: [], jumpCuts: [],
};

export const shortMetadata: CalculateMetadataFunction<ShortProps> = ({props}) => ({
  durationInFrames: props.data.durationInFrames,
  fps: props.data.fps,
});

const pop = (f: number, start: number, fps: number) => {
  const s = settle(f, fps, start);
  return {opacity: Math.min(1, s * 1.4), transform: `scale(${0.9 + 0.1 * s})`};
};

// Word-by-word captions: 2-4 words a page, the word being said in yellow, centred, under the chin.
const Caption: React.FC<{page: Page; top: number}> = ({page, top}) => {
  const f = useCurrentFrame() + page.start;
  return (
    <div style={{position: 'absolute', left: (W - CAP_W) / 2, width: CAP_W, top, height: CAP_H, display: 'flex', alignItems: 'center', justifyContent: 'center', whiteSpace: 'nowrap'}}>
      <div style={{fontFamily: heavy, fontWeight: 800, fontSize: 55, lineHeight: 1.08, textAlign: 'center', color: '#FFFFFF', letterSpacing: -0.3}}>
        {page.words.map((w, i) => {
          const live = f >= w.start && f < (page.words[i + 1]?.start ?? page.end);
          return (
            <span
              key={i}
              style={{
                color: live ? C.hot : '#FFFFFF',
                WebkitTextStroke: '8px #0B1220',
                paintOrder: 'stroke fill',
                textShadow: '0 4px 12px rgba(0,0,0,0.55)',
                display: 'inline-block',
                transform: `scale(${live ? 1.04 : 1})`,
                margin: '0 9px', // room for the live word's scale-up, so neighbours never touch
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </div>
  );
};

// QA only (stills): the zones covered by the TikTok / Reels / Shorts / Facebook UI
const SafeMask: React.FC = () => (
  <AbsoluteFill style={{pointerEvents: 'none'}}>
    {[
      {left: 0, top: 0, width: W, height: 220},
      {left: 0, top: 1500, width: W, height: H - 1500},
      {left: 900, top: 700, width: W - 900, height: 740},
    ].map((r, i) => (
      <div key={i} style={{position: 'absolute', ...r, background: 'rgba(255,0,60,0.28)', outline: '2px solid rgba(255,0,60,0.8)'}} />
    ))}
  </AbsoluteFill>
);

const YellowCard: React.FC<{children: React.ReactNode; size?: number}> = ({children, size = 62}) => (
  <div
    style={{
      fontFamily: heavy, fontWeight: 800, fontSize: size, lineHeight: 1.12, color: C.darkInk, background: C.hot, textAlign: 'center',
      padding: '18px 30px 20px', borderRadius: 22, boxShadow: '0 18px 44px -16px rgba(0,0,0,0.6)', maxWidth: 860,
    }}
  >
    {children}
  </div>
);

// first 3 s: the text hook (never the words being said), centred
const Hook: React.FC<{text: string; until: number}> = ({text, until}) => {
  const f = useCurrentFrame();
  const o = 1 - ramp(f, until - SLIDE_FRAMES, SLIDE_FRAMES);
  return (
    <div style={{position: 'absolute', left: 0, width: W, top: TOP, display: 'flex', justifyContent: 'center', opacity: o}}>
      <YellowCard>{text}</YellowCard>
    </div>
  );
};

// a follower's question as a comment card under the chin while it is read out; the word being read darkens.
export const Q_W = 680; // keep in step with tools/shorts.py (card height estimate)
const QuestionCard: React.FC<{q: Question; top: number; fps: number}> = ({q, top, fps}) => {
  const f = useCurrentFrame() + q.start;
  const st = q.start === 0 ? {opacity: 1, transform: 'none'} : pop(f, q.start, fps);
  const out = 1 - ramp(f, q.end - SLIDE_FRAMES, SLIDE_FRAMES);
  return (
    <div style={{position: 'absolute', left: (W - Q_W) / 2, width: Q_W, top, opacity: st.opacity * out, transform: st.transform, transformOrigin: '50% 0'}}>
      <div style={{background: '#FFFFFF', borderRadius: 24, padding: '18px 26px 22px', boxShadow: '0 18px 40px -16px rgba(0,0,0,0.6)'}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8}}>
          <svg width={34} height={34} viewBox="0 0 46 46">
            <circle cx={23} cy={23} r={23} fill="#D9DEE7" />
            <circle cx={23} cy={18} r={8} fill="#8391A8" />
            <path d="M8 39c3-8 9-11 15-11s12 3 15 11" fill="#8391A8" />
          </svg>
          <div style={{fontFamily: heavy, fontWeight: 600, fontSize: 24, color: '#6B7890'}}>{q.label}</div>
        </div>
        <div style={{fontFamily: heavy, fontWeight: 700, fontSize: 34, lineHeight: 1.22, color: C.darkInk}}>
          {q.words.map((w, i) => (
            <span key={i} style={{opacity: f >= w.start ? 1 : 0.38}}>
              {w.text}{' '}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

const LinkIcon: React.FC = () => (
  <svg width={52} height={52} viewBox="0 0 24 24" style={{marginRight: 14, flex: 'none'}}>
    <path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" stroke={C.darkInk} strokeWidth={2.6} fill="none" strokeLinecap="round" />
  </svg>
);

// the CTA card at the top. Texts come from channel.json (cta.bio, cta.comment).
// A = link in bio (TikTok, YouTube), B = comment the keyword (Instagram, Facebook).
const CtaCard: React.FC<{cta: Cta; fps: number}> = ({cta, fps}) => {
  const f = useCurrentFrame() + cta.start;
  const st = pop(f, cta.start, fps);
  return (
    <div style={{position: 'absolute', left: 0, width: W, top: TOP, display: 'flex', justifyContent: 'center', ...st, transformOrigin: '50% 0'}}>
      {cta.kind === 'bio' ? (
        <YellowCard>
          <span style={{display: 'inline-flex', alignItems: 'center'}}>
            <LinkIcon />
            {cta.lines[0]}
          </span>
        </YellowCard>
      ) : (
        <YellowCard size={50}>
          {cta.lines[0]}
          <div style={{marginTop: 10, display: 'inline-block', background: C.darkInk, color: C.hot, borderRadius: 16, padding: '8px 26px 12px', fontSize: 70, letterSpacing: 1}}>
            {cta.keyword}
          </div>
          {cta.lines[1] ? <div style={{fontSize: 38, fontWeight: 700, marginTop: 10}}>{cta.lines[1]}</div> : null}
        </YellowCard>
      )}
    </div>
  );
};

export const NativeShort: React.FC<ShortProps> = ({data, safe}) => {
  const q = data.question;
  return (
    <AbsoluteFill style={{backgroundColor: C.bg}}>
      {data.audio ? (
        <Audio
          src={staticFile(data.audio)}
          volume={(fr) => interpolate(fr, [data.durationInFrames - 4, data.durationInFrames - 1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}
        />
      ) : null}
      {data.video ? <OffthreadVideo src={staticFile(data.video)} muted style={{position: 'absolute', left: 0, top: 0, width: W, height: H}} /> : null}
      {data.captions.map((p, i) => (
        <Sequence key={`cap${i}`} name={`Caption ${i + 1}`} from={p.start} durationInFrames={Math.max(1, p.end - p.start)} layout="none">
          <Caption page={p} top={data.capTop} />
        </Sequence>
      ))}
      {q ? (
        <Sequence name="Question" from={q.start} durationInFrames={Math.max(1, q.end - q.start)} layout="none">
          <QuestionCard q={q} top={q.top} fps={data.fps} />
        </Sequence>
      ) : null}
      {data.hook ? (
        <Sequence name="Hook" from={0} durationInFrames={data.hook.until} layout="none">
          <Hook text={data.hook.text} until={data.hook.until} />
        </Sequence>
      ) : null}
      {data.cta ? (
        <Sequence name={`CTA ${data.cta.kind}`} from={data.cta.start} durationInFrames={Math.max(1, data.cta.end - data.cta.start)} layout="none">
          <CtaCard cta={data.cta} fps={data.fps} />
        </Sequence>
      ) : null}
      {data.sfx.map((s, i) => (
        <Sequence key={`sfx${i}`} name={`SFX ${s.sound}`} from={s.at} durationInFrames={60} layout="none">
          <Audio src={staticFile(`sfx/${s.sound}.wav`)} volume={s.volume} />
        </Sequence>
      ))}
      {safe ? <SafeMask /> : null}
    </AbsoluteFill>
  );
};
