(() => {
  const CFG = {
    width: 32,
    height: 18,
    quality: 0.4,
    blur: 12,
    fps: 3,
    freezeChance: 0.06,
    freezeMs: [700, 3000],
  };

  let on = false;
  window.addEventListener("message", (e) => {
    if (e.source === window && e.data && typeof e.data.camCrush === "boolean") on = e.data.camCrush;
  });

  const md = navigator.mediaDevices;
  if (!md || !md.getUserMedia || !window.MediaStreamTrackProcessor || !window.MediaStreamTrackGenerator) return;
  const getUserMedia = md.getUserMedia.bind(md);

  function crush(src) {
    const small = new OffscreenCanvas(CFG.width, CFG.height);
    const sctx = small.getContext("2d");
    const big = new OffscreenCanvas(1, 1);
    const bctx = big.getContext("2d");
    let next = 0;

    const gen = new MediaStreamTrackGenerator({ kind: "video" });
    new MediaStreamTrackProcessor({ track: src }).readable
      .pipeThrough(new TransformStream({
        async transform(frame, ctrl) {
          if (!on) return ctrl.enqueue(frame);
          const now = performance.now();
          if (now < next) return frame.close();
          next = now + 1000 / CFG.fps * (0.6 + Math.random() * 0.8);
          if (Math.random() < CFG.freezeChance) {
            next += CFG.freezeMs[0] + Math.random() * (CFG.freezeMs[1] - CFG.freezeMs[0]);
          }

          const { timestamp, displayWidth: w, displayHeight: h } = frame;
          sctx.drawImage(frame, 0, 0, CFG.width, CFG.height);
          frame.close();
          const bmp = await createImageBitmap(await small.convertToBlob({ type: "image/jpeg", quality: CFG.quality }));
          if (big.width !== w || big.height !== h) {
            big.width = w;
            big.height = h;
          }
          bctx.imageSmoothingQuality = "high";
          bctx.filter = `blur(${CFG.blur * w / 640}px)`;
          bctx.drawImage(bmp, -w * 0.05, -h * 0.05, w * 1.1, h * 1.1);
          bmp.close();
          ctrl.enqueue(new VideoFrame(big, { timestamp }));
        },
      }))
      .pipeTo(gen.writable)
      .catch(() => {});

    const stop = gen.stop.bind(gen);
    gen.stop = () => {
      stop();
      src.stop();
    };
    gen.getSettings = () => src.getSettings();
    gen.getCapabilities = () => src.getCapabilities();
    gen.getConstraints = () => src.getConstraints();
    gen.applyConstraints = (c) => src.applyConstraints(c);
    Object.defineProperty(gen, "label", { get: () => src.label });
    src.addEventListener("ended", stop);
    return gen;
  }

  md.getUserMedia = async function (constraints) {
    const stream = await getUserMedia(constraints);
    const video = stream.getVideoTracks();
    if (!video.length) return stream;
    return new MediaStream([...stream.getAudioTracks(), ...video.map(crush)]);
  };
})();
