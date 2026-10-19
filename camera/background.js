const r = (a, b) => a + Math.random() * (b - a);

function randomCfg() {
  const width = Math.round(r(20, 56));
  const smooth = Math.random() < 0.7;
  return {
    width,
    height: Math.round(width * 9 / 16),
    quality: +r(0.3, 0.7).toFixed(2),
    blur: smooth ? Math.round(r(7, 16)) : Math.round(r(0, 3)),
    smooth,
    brightness: +r(0.85, 1.2).toFixed(2),
    saturate: +r(0.9, 1.5).toFixed(2),
    contrast: +r(0.8, 1.25).toFixed(2),
    fps: Math.round(r(2, 6)),
    freezeChance: +r(0.02, 0.1).toFixed(3),
    freezeMs: [Math.round(r(400, 900)), Math.round(r(1500, 4000))],
  };
}

async function loadCfg() {
  try {
    const res = await fetch(chrome.runtime.getURL("profile.json"));
    if (res.ok) return chrome.storage.local.set({ cfg: await res.json() });
  } catch {}
  const { cfg } = await chrome.storage.local.get("cfg");
  if (!cfg) await chrome.storage.local.set({ cfg: randomCfg() });
}

function paint(on) {
  chrome.action.setBadgeBackgroundColor({ color: "#d00" });
  chrome.action.setBadgeText({ text: on ? "ON" : "" });
}

async function toggle() {
  const { on } = await chrome.storage.local.get("on");
  await chrome.storage.local.set({ on: !on });
  paint(!on);
}

chrome.action.onClicked.addListener(toggle);
chrome.commands.onCommand.addListener((command) => command === "toggle" && toggle());
chrome.runtime.onStartup.addListener(() => {
  loadCfg();
  chrome.storage.local.set({ on: false }).then(() => paint(false));
});
chrome.runtime.onInstalled.addListener(() => {
  loadCfg();
  chrome.storage.local.get("on").then((s) => paint(!!s.on));
});
