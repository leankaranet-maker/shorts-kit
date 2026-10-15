import {Composition} from 'remotion';
import {EMPTY_SHORT, NativeShort, shortMetadata} from './short/NativeShort';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="NativeShort"
      component={NativeShort}
      durationInFrames={30}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{data: EMPTY_SHORT, safe: false}}
      calculateMetadata={shortMetadata}
    />
  </>
);
