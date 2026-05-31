const DEFAULTS = {
  currentPerson: "p01",
  currentMode: "registered",
};

const personInput = document.getElementById("personInput");
const modeInputs = Array.from(document.querySelectorAll("input[name='mode']"));
const saveButton = document.getElementById("saveSettings");
const resetButton = document.getElementById("resetCounter");
const openOptionsButton = document.getElementById("openOptions");
const currentCount = document.getElementById("currentCount");
const resetAllButton = document.getElementById("resetAllCounters");

chrome.storage.sync.get(DEFAULTS, (settings) => {
  personInput.value = settings.currentPerson || "p01";
  const activeMode = settings.currentMode || "registered";
  modeInputs.forEach((input) => {
    input.checked = input.value === activeMode;
  });
  updateCountDisplay();
});

saveButton.addEventListener("click", () => {
  const person = (personInput.value || "p01").trim();
  const mode = modeInputs.find((input) => input.checked)?.value || "registered";

  chrome.storage.sync.set(
    {
      currentPerson: person,
      currentMode: mode,
    },
    () => {
      updateCountDisplay();
    },
  );
});

resetButton.addEventListener("click", () => {
  const person = (personInput.value || "p01").trim();
  const mode = modeInputs.find((input) => input.checked)?.value || "registered";

  chrome.runtime.sendMessage(
    {
      type: "reset-counter",
      person,
      mode,
    },
    () => {
      updateCountDisplay();
    },
  );
});

resetAllButton.addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "reset-all-counters" }, () => {
    updateCountDisplay();
  });
});

openOptionsButton.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

personInput.addEventListener("input", () => updateCountDisplay());
modeInputs.forEach((input) => {
  input.addEventListener("change", () => updateCountDisplay());
});

function getCountKey(person, mode) {
  return `count_${mode}_${person}`;
}

function getSelectedPersonMode() {
  const person = (personInput.value || "p01").trim();
  const mode = modeInputs.find((input) => input.checked)?.value || "registered";
  return { person, mode };
}

function updateCountDisplay() {
  const { person, mode } = getSelectedPersonMode();
  const countKey = getCountKey(person, mode);
  chrome.storage.sync.get({ [countKey]: 0 }, (data) => {
    const count = data[countKey] || 0;
    const nextIndex = count + 1;
    const suffix = mode === "registered" ? "r" : "t";
    const nextName = `${person}_${suffix}${String(nextIndex).padStart(2, "0")}`;
    currentCount.textContent = `当前计数：${count}，下一张：${nextName}`;
  });
}
