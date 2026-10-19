const send = (on) => window.postMessage({ camCrush: on }, location.origin);

chrome.storage.local.get("on", (s) => send(!!s.on));
chrome.storage.onChanged.addListener((changes) => {
  if (changes.on) send(!!changes.on.newValue);
});
