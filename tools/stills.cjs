// Many stills from one bundle with a single browser (much faster than one
// `remotion still` per frame). Used by tools/shorts.py stills.
//   node tools/stills.cjs <bundle> <jobs.json>
// jobs.json: [{"composition": "VisualProbe", "props": {...}, "frame": 40, "out": "/abs/path.png", "scale": 1}, ...]
const {openBrowser, renderStill, selectComposition} = require('../video/node_modules/@remotion/renderer');
const fs = require('fs');

(async () => {
  const [bundle, jobsFile] = process.argv.slice(2);
  const jobs = JSON.parse(fs.readFileSync(jobsFile, 'utf8'));
  const browser = await openBrowser('chrome');
  const comps = new Map();
  for (const j of jobs) {
    const key = j.composition + JSON.stringify(j.props);
    if (!comps.has(key)) {
      comps.set(key, await selectComposition({serveUrl: bundle, id: j.composition, inputProps: j.props, puppeteerInstance: browser, logLevel: 'error'}));
    }
    await renderStill({
      composition: comps.get(key), serveUrl: bundle, output: j.out, frame: j.frame, inputProps: j.props,
      imageFormat: 'png', scale: j.scale ?? 1, puppeteerInstance: browser, logLevel: 'error', overwrite: true,
    });
  }
  await browser.close({silent: true});
  console.log(`${jobs.length} stills`);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
