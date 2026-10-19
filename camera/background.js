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
chrome.runtime.onStartup.addListener(() => chrome.storage.local.set({ on: false }).then(() => paint(false)));
chrome.runtime.onInstalled.addListener(() => chrome.storage.local.get("on").then((s) => paint(!!s.on)));
