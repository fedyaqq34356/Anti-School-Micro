const send = (on, cfg) => window.postMessage({ camCrush: on, cfg }, location.origin);

chrome.storage.local.get(["on", "cfg"], (s) => send(!!s.on, s.cfg));
chrome.storage.onChanged.addListener(() => {
  chrome.storage.local.get(["on", "cfg"], (s) => send(!!s.on, s.cfg));
});
