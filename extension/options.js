const DEFAULTS = {
  registeredBase: "dataset/registered",
  testBase: "dataset/test/images",
};

const registeredInput = document.getElementById("registeredBase");
const testInput = document.getElementById("testBase");
const saveButton = document.getElementById("save");

chrome.storage.sync.get(DEFAULTS, (settings) => {
  registeredInput.value = settings.registeredBase || DEFAULTS.registeredBase;
  testInput.value = settings.testBase || DEFAULTS.testBase;
});

saveButton.addEventListener("click", () => {
  const registeredBase = (
    registeredInput.value || DEFAULTS.registeredBase
  ).trim();
  const testBase = (testInput.value || DEFAULTS.testBase).trim();

  chrome.storage.sync.set({
    registeredBase,
    testBase,
  });
});
