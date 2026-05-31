const DEFAULTS = {
  registeredBase: "dataset/registered",
  testBase: "dataset/test/images",
  currentPerson: "p01",
  currentMode: "registered",
};

const MENU_ID = "dataset-image-saver-save";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_ID,
    title: "保存到当前人物",
    contexts: ["image"],
  });

  chrome.storage.sync.get(DEFAULTS, (items) => {
    chrome.storage.sync.set(items);
  });
});

chrome.contextMenus.onClicked.addListener((info) => {
  if (!info.srcUrl) {
    return;
  }

  if (info.menuItemId === MENU_ID) {
    chrome.storage.sync.get(DEFAULTS, (settings) => {
      const { currentPerson, currentMode } = settings;
      downloadImage(info.srcUrl, currentPerson, currentMode, settings);
    });
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "download-image") {
    chrome.storage.sync.get(DEFAULTS, (settings) => {
      const { currentPerson, currentMode } = settings;
      downloadImage(message.url, currentPerson, currentMode, settings)
        .then(() => sendResponse({ ok: true }))
        .catch((error) => sendResponse({ ok: false, error: String(error) }));
    });
    return true;
  }

  if (message?.type === "reset-counter") {
    const key = getCountKey(message.person, message.mode);
    chrome.storage.sync.remove(key, () => sendResponse({ ok: true }));
    return true;
  }

  if (message?.type === "reset-all-counters") {
    chrome.storage.sync.get(null, (items) => {
      const keys = Object.keys(items).filter((key) => key.startsWith("count_"));
      if (keys.length === 0) {
        sendResponse({ ok: true, cleared: 0 });
        return;
      }
      chrome.storage.sync.remove(keys, () => {
        sendResponse({ ok: true, cleared: keys.length });
      });
    });
    return true;
  }

  return false;
});

function getCountKey(person, mode) {
  return `count_${mode}_${person}`;
}

function getExtensionFromUrl(url) {
  try {
    const parsed = new URL(url);
    const match = parsed.pathname.match(/\.(jpg|jpeg|png|webp|bmp|gif)$/i);
    if (match) {
      return match[0].toLowerCase();
    }
  } catch (_) {
    // ignore
  }
  return ".jpg";
}

async function downloadImage(url, person, mode, settings) {
  const countKey = getCountKey(person, mode);
  const data = await chrome.storage.sync.get({ [countKey]: 0 });
  const nextIndex = (data[countKey] || 0) + 1;
  const indexText = String(nextIndex).padStart(2, "0");
  const ext = getExtensionFromUrl(url);

  const isRegistered = mode === "registered";
  const baseDir = isRegistered ? settings.registeredBase : settings.testBase;
  const suffix = isRegistered ? "r" : "t";

  const fileName = isRegistered
    ? `${baseDir}/${person}/${person}_${suffix}${indexText}${ext}`
    : `${baseDir}/${person}_${suffix}${indexText}${ext}`;

  await chrome.downloads.download({
    url,
    filename: fileName,
    conflictAction: "uniquify",
    saveAs: false,
  });

  await chrome.storage.sync.set({ [countKey]: nextIndex });
}
