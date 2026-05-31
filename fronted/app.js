const API_BASE = 'http://127.0.0.1:8000';

const elements = {
  recognitionTab: document.getElementById('recognitionTab'),
  evaluationTab: document.getElementById('evaluationTab'),
  recognitionView: document.getElementById('recognitionView'),
  evaluationView: document.getElementById('evaluationView'),
  backendStatus: document.getElementById('backendStatus'),
  datasetSelect: document.getElementById('datasetSelect'),
  reloadButton: document.getElementById('reloadButton'),
  recognizeButton: document.getElementById('recognizeButton'),
  fileInput: document.getElementById('fileInput'),
  folderInput: document.getElementById('folderInput'),
  folderButton: document.getElementById('folderButton'),
  clearButton: document.getElementById('clearButton'),
  fileName: document.getElementById('fileName'),
  dropzone: document.getElementById('dropzone'),
  queueList: document.getElementById('queueList'),
  progressWrap: document.querySelector('.progress-wrap'),
  progressBar: document.getElementById('progressBar'),
  resultsGrid: document.getElementById('resultsGrid'),
  gridModeButton: document.getElementById('gridModeButton'),
  carouselModeButton: document.getElementById('carouselModeButton'),
  carouselView: document.getElementById('carouselView'),
  carouselPrev: document.getElementById('carouselPrev'),
  carouselNext: document.getElementById('carouselNext'),
  carouselStage: document.getElementById('carouselStage'),
  carouselCounter: document.getElementById('carouselCounter'),
  previewModal: document.getElementById('previewModal'),
  previewBackdrop: document.getElementById('previewBackdrop'),
  previewClose: document.getElementById('previewClose'),
  previewImage: document.getElementById('previewImage'),
  previewTitle: document.getElementById('previewTitle'),
  evalDatasetSelect: document.getElementById('evalDatasetSelect'),
  evalRunButton: document.getElementById('evalRunButton'),
  evalImageList: document.getElementById('evalImageList'),
  evalListSummary: document.getElementById('evalListSummary'),
  evalAccuracy: document.getElementById('evalAccuracy'),
  evalPreview: document.getElementById('evalPreview'),
  evalWrongSummary: document.getElementById('evalWrongSummary'),
  evalWrongResults: document.getElementById('evalWrongResults'),
  summaryText: document.getElementById('summaryText'),
  message: document.getElementById('message'),
};

let selectedFiles = [];
let resultRecords = [];
let registryStatus = null;
let isProcessing = false;
let viewMode = 'grid';
let carouselIndex = 0;
let activeTab = 'recognition';
let evalItems = [];
let evalDatasetLoaded = null;
let isEvaluating = false;

init();

function init() {
  elements.recognitionTab.addEventListener('click', () => setMainTab('recognition'));
  elements.evaluationTab.addEventListener('click', () => setMainTab('evaluation'));
  elements.fileInput.addEventListener('change', (event) => {
    addFiles(event.target.files);
    event.target.value = '';
  });

  elements.folderButton.addEventListener('click', () => elements.folderInput.click());
  elements.folderInput.addEventListener('change', (event) => {
    addFiles(event.target.files);
    event.target.value = '';
  });

  elements.clearButton.addEventListener('click', clearFiles);
  elements.queueList.addEventListener('click', handleQueueClick);
  elements.gridModeButton.addEventListener('click', () => setViewMode('grid'));
  elements.carouselModeButton.addEventListener('click', () => setViewMode('carousel'));
  elements.carouselPrev.addEventListener('click', () => moveCarousel(-1));
  elements.carouselNext.addEventListener('click', () => moveCarousel(1));
  elements.resultsGrid.addEventListener('click', handlePreviewClick);
  elements.carouselStage.addEventListener('click', handlePreviewClick);
  elements.resultsGrid.addEventListener('keydown', handlePreviewKeydown);
  elements.carouselStage.addEventListener('keydown', handlePreviewKeydown);
  elements.previewBackdrop.addEventListener('click', closePreview);
  elements.previewClose.addEventListener('click', closePreview);
  elements.evalDatasetSelect.addEventListener('change', loadEvaluationImages);
  elements.evalRunButton.addEventListener('click', runEvaluation);
  elements.evalImageList.addEventListener('click', handleEvalListClick);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closePreview();
  });

  elements.dropzone.addEventListener('dragover', (event) => {
    event.preventDefault();
    elements.dropzone.classList.add('dragover');
  });

  elements.dropzone.addEventListener('dragleave', () => {
    elements.dropzone.classList.remove('dragover');
  });

  elements.dropzone.addEventListener('drop', (event) => {
    event.preventDefault();
    elements.dropzone.classList.remove('dragover');
    addFiles(event.dataTransfer.files);
  });

  elements.datasetSelect.addEventListener('change', handleDatasetChange);
  elements.reloadButton.addEventListener('click', reloadRegistries);
  elements.recognizeButton.addEventListener('click', recognizeSelectedImages);

  checkBackend();
}

async function checkBackend() {
  setStatus('正在检查后端', '');
  try {
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    registryStatus = await response.json();
    setStatus('后端已连接', 'ok');
    applyRegistryStatus();
    setMessage('后端已连接。请选择身份库并上传图片。');
  } catch (error) {
    registryStatus = null;
    setStatus('后端未连接', 'bad');
    setMessage(`无法连接 ${API_BASE}。请先启动后端 API。`);
  }
  updateControls();
}

function applyRegistryStatus() {
  const registries = registryStatus?.registries || {};
  for (const option of elements.datasetSelect.options) {
    const exists = registries[option.value]?.exists;
    option.disabled = exists === false;
    option.textContent = option.value === 'self'
      ? `自采集 20 人${exists === false ? '（缺失）' : ''}`
      : `CelebA 100${exists === false ? '（缺失）' : ''}`;
  }

  for (const option of elements.evalDatasetSelect.options) {
    const exists = registries[option.value]?.exists;
    option.disabled = exists === false;
    option.textContent = option.value === 'self'
      ? `自采集 20 人${exists === false ? '（缺失）' : ''}`
      : `CelebA 100${exists === false ? '（缺失）' : ''}`;
  }

  if (elements.datasetSelect.selectedOptions[0]?.disabled) {
    const firstEnabled = [...elements.datasetSelect.options].find((option) => !option.disabled);
    if (firstEnabled) elements.datasetSelect.value = firstEnabled.value;
  }

  if (elements.evalDatasetSelect.selectedOptions[0]?.disabled) {
    const firstEnabled = [...elements.evalDatasetSelect.options].find((option) => !option.disabled);
    if (firstEnabled) elements.evalDatasetSelect.value = firstEnabled.value;
  }
}

function setMainTab(tab) {
  activeTab = tab;
  elements.recognitionView.hidden = tab !== 'recognition';
  elements.evaluationView.hidden = tab !== 'evaluation';
  elements.recognitionTab.classList.toggle('active', tab === 'recognition');
  elements.evaluationTab.classList.toggle('active', tab === 'evaluation');
  if (tab === 'evaluation' && evalDatasetLoaded !== elements.evalDatasetSelect.value) {
    loadEvaluationImages();
  }
}

function handleDatasetChange() {
  clearResults();
  updateControls();
  setMessage(`当前使用 ${datasetLabel(elements.datasetSelect.value)} 身份库。`);
}

function addFiles(fileList) {
  const incoming = [...fileList].filter((file) => file.type.startsWith('image/'));
  const seen = new Set(selectedFiles.map(fileKey));
  for (const file of incoming) {
    const key = fileKey(file);
    if (!seen.has(key)) {
      selectedFiles.push(file);
      seen.add(key);
    }
  }
  selectedFiles.sort((a, b) => displayName(a).localeCompare(displayName(b), 'zh-Hans-CN'));
  clearResults();
  renderQueue();
  updateControls();
}

function clearFiles() {
  selectedFiles = [];
  renderQueue();
  clearResults();
  updateControls();
  setMessage('已清空选择。');
}

function handleQueueClick(event) {
  const button = event.target.closest('[data-remove-key]');
  if (!button || isProcessing) return;

  const key = button.dataset.removeKey;
  const removed = selectedFiles.find((file) => fileKey(file) === key);
  selectedFiles = selectedFiles.filter((file) => fileKey(file) !== key);
  renderQueue();
  clearResults();
  updateControls();
  setMessage(removed ? `已移除 ${displayName(removed)}。` : '已移除图片。');
}

function renderQueue() {
  elements.fileName.textContent = selectedFiles.length
    ? `已选择 ${selectedFiles.length} 张图片`
    : '未选择图片';

  if (!selectedFiles.length) {
    elements.queueList.innerHTML = '<div class="empty-row">已选择的图片会显示在这里</div>';
    return;
  }

  elements.queueList.innerHTML = '';
  for (const [index, file] of selectedFiles.entries()) {
    const row = document.createElement('div');
    row.className = 'queue-row';
    row.innerHTML = `
      <span class="queue-name">${index + 1}. ${escapeHtml(displayName(file))}</span>
      <span class="queue-size">${formatBytes(file.size)}</span>
      <button class="icon-button queue-delete" type="button" data-remove-key="${escapeHtml(fileKey(file))}" aria-label="移除 ${escapeHtml(displayName(file))}" ${isProcessing ? 'disabled' : ''}>×</button>
    `;
    elements.queueList.appendChild(row);
  }
}

async function reloadRegistries() {
  setBusy(true);
  setMessage('正在重新加载身份库缓存...');
  try {
    const response = await fetch(`${API_BASE}/reload-registry`, { method: 'POST' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    await checkBackend();
    setMessage('身份库缓存已重新加载。');
  } catch (error) {
    setMessage(`重新加载失败：${error.message}`);
  } finally {
    setBusy(false);
  }
}

function setViewMode(mode) {
  viewMode = mode;
  elements.resultsGrid.hidden = mode !== 'grid';
  elements.carouselView.hidden = mode !== 'carousel';
  elements.gridModeButton.classList.toggle('active', mode === 'grid');
  elements.carouselModeButton.classList.toggle('active', mode === 'carousel');
  renderResultViews();
}

function moveCarousel(step) {
  if (!resultRecords.length) return;
  carouselIndex = (carouselIndex + step + resultRecords.length) % resultRecords.length;
  renderCarouselView();
}

function handlePreviewClick(event) {
  const image = event.target.closest('[data-preview-index]');
  if (!image) return;
  openPreview(Number(image.dataset.previewIndex));
}

function handlePreviewKeydown(event) {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const image = event.target.closest('[data-preview-index]');
  if (!image) return;
  event.preventDefault();
  openPreview(Number(image.dataset.previewIndex));
}

function openPreview(index) {
  const record = resultRecords[index];
  const image = record?.result?.annotated_image;
  if (!image) return;

  elements.previewImage.src = image;
  elements.previewTitle.textContent = displayName(record.file);
  elements.previewModal.hidden = false;
}

function closePreview() {
  if (elements.previewModal.hidden) return;
  elements.previewModal.hidden = true;
  elements.previewImage.removeAttribute('src');
}

async function loadEvaluationImages() {
  const dataset = elements.evalDatasetSelect.value;
  evalDatasetLoaded = dataset;
  evalItems = [];
  elements.evalImageList.innerHTML = '<div class="empty-row">正在加载测试图片...</div>';
  elements.evalListSummary.textContent = '加载中';
  elements.evalAccuracy.textContent = '等待评测';
  elements.evalPreview.innerHTML = '<div class="empty-row">点击图片或运行评测后查看结果</div>';
  elements.evalWrongResults.innerHTML = '<div class="empty-row">评测完成后，错误样例会显示在这里</div>';
  elements.evalWrongSummary.textContent = '未加载';

  try {
    const response = await fetch(`${API_BASE}/evaluation/images?dataset=${encodeURIComponent(dataset)}`);
    if (!response.ok) throw new Error(await response.text() || `HTTP ${response.status}`);
    const payload = await response.json();
    evalItems = payload.images || [];
    renderEvalList();
    setMessage(`已加载 ${evalItems.length} 张评测图片。`);
  } catch (error) {
    elements.evalImageList.innerHTML = `<div class="empty-row">${escapeHtml(error.message)}</div>`;
    elements.evalListSummary.textContent = '加载失败';
  }
  updateControls();
}

async function runEvaluation() {
  if (isEvaluating) return;

  const dataset = elements.evalDatasetSelect.value;
  isEvaluating = true;
  elements.evalRunButton.disabled = true;
  elements.evalDatasetSelect.disabled = true;
  elements.evalAccuracy.textContent = '正在评测...';
  elements.evalWrongResults.innerHTML = '<div class="empty-row">正在等待错误样例...</div>';
  elements.evalWrongSummary.textContent = '评测中';
  setMessage(`正在评测 ${datasetLabel(dataset)} 身份库...`);

  try {
    const formData = new FormData();
    formData.append('dataset', dataset);
    const response = await fetch(`${API_BASE}/evaluation/run`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) throw new Error(await response.text() || `HTTP ${response.status}`);
    const result = await response.json();
    evalItems = result.items || [];
    renderEvalList();
    elements.evalAccuracy.textContent = `按人脸 ${formatPercent(result.accuracy)} · ${result.correct}/${result.total} 张脸正确 · 按图片 ${formatPercent(result.image_accuracy)} · ${result.image_correct}/${result.image_total} 张图片正确 · ${result.no_face} 张脸未检测`;

    const wrongItems = evalItems.filter((item) => !item.ok);
    elements.evalWrongSummary.textContent = `${wrongItems.length} 个错误`;
    await renderWrongEvaluations(wrongItems, dataset);
    setMessage(`评测完成：按人脸准确率 ${formatPercent(result.accuracy)}。`);
  } catch (error) {
    elements.evalAccuracy.textContent = '评测失败';
    elements.evalWrongResults.innerHTML = `<div class="empty-row">${escapeHtml(error.message)}</div>`;
    setMessage(`评测失败：${error.message}`);
  } finally {
    isEvaluating = false;
    elements.evalRunButton.disabled = false;
    elements.evalDatasetSelect.disabled = false;
    updateControls();
  }
}

function renderEvalList() {
  elements.evalListSummary.textContent = `${evalItems.length} 张图片`;
  if (!evalItems.length) {
    elements.evalImageList.innerHTML = '<div class="empty-row">未找到测试图片</div>';
    return;
  }

  elements.evalImageList.innerHTML = evalItems.map((item, index) => `
    <button class="eval-row ${item.ok === true ? 'ok' : item.ok === false ? 'bad' : ''}" type="button" data-eval-index="${index}">
      <span class="eval-row-name">${escapeHtml(item.name || item.image)}</span>
      <span class="eval-row-meta">真实 ${escapeHtml(item.expected || '-')}</span>
      ${item.predicted ? `<span class="eval-row-meta">预测 ${escapeHtml(item.predicted)} · 分数 ${Number(item.score || 0).toFixed(3)}</span>` : ''}
    </button>
  `).join('');
}

async function handleEvalListClick(event) {
  const row = event.target.closest('[data-eval-index]');
  if (!row || isEvaluating) return;
  const item = evalItems[Number(row.dataset.evalIndex)];
  if (!item) return;
  await renderEvaluationPreview(item, elements.evalDatasetSelect.value, item.ok === false);
}

async function renderWrongEvaluations(items, dataset) {
  if (!items.length) {
    elements.evalWrongResults.innerHTML = '<div class="empty-row">没有错误样例。</div>';
    return;
  }

  elements.evalWrongResults.innerHTML = '';
  for (const [index, item] of items.entries()) {
    const result = await recognizePath(item.image, dataset, true);
    const card = document.createElement('article');
    card.className = 'eval-detection-card';
    card.innerHTML = renderEvalDetection(result, item);
    elements.evalWrongResults.appendChild(card);
    elements.evalWrongSummary.textContent = `已加载 ${index + 1}/${items.length} 个错误`;
  }
  elements.evalWrongSummary.textContent = `${items.length} 个错误`;
}

async function renderEvaluationPreview(item, dataset, highlightErrors = false) {
  elements.evalPreview.innerHTML = '<div class="empty-row">正在识别所选图片...</div>';
  try {
    const result = await recognizePath(item.image, dataset, highlightErrors);
    elements.evalPreview.innerHTML = renderEvalDetection(result, item);
  } catch (error) {
    elements.evalPreview.innerHTML = `<div class="empty-row">${escapeHtml(error.message)}</div>`;
  }
}

async function recognizePath(image, dataset, highlightErrors = false) {
  const formData = new FormData();
  formData.append('image', image);
  formData.append('dataset', dataset);
  formData.append('highlight_errors', highlightErrors ? 'true' : 'false');
  const response = await fetch(`${API_BASE}/recognize-path`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) throw new Error(await response.text() || `HTTP ${response.status}`);
  return response.json();
}

function renderEvalDetection(result, item) {
  const faces = result.faces || [];
  return `
    <div class="eval-detection-image">
      ${result.annotated_image ? `<div class="result-image" style="background-image: url(${result.annotated_image})"></div>` : '<span>无图片</span>'}
    </div>
    <div class="eval-detection-body">
      <div class="result-title">${escapeHtml(item.name || item.image)}</div>
      <div class="face-meta">真实 ${escapeHtml(item.expected || '-')} · 预测 ${escapeHtml(item.predicted || faces[0]?.identity_id || '-')}</div>
      <div class="faces compact">
        ${faces.length ? faces.map((face, index) => renderFace(face, index)).join('') : '<div class="face-row"><span>未检测到人脸</span><span class="face-meta">空</span></div>'}
      </div>
    </div>
  `;
}

async function recognizeSelectedImages() {
  if (!selectedFiles.length || isProcessing) return;

  const dataset = elements.datasetSelect.value;
  setBusy(true);
  elements.progressWrap.hidden = false;
  clearResults();
  elements.progressWrap.hidden = false;
  setMessage(`正在使用 ${datasetLabel(dataset)} 身份库识别 ${selectedFiles.length} 张图片...`);

  let completed = 0;
  let failed = 0;
  for (const [index, file] of selectedFiles.entries()) {
    updateProgress(completed, selectedFiles.length);
    appendPendingResult(file, index);
    try {
      const result = await recognizeOne(file, dataset);
      completed += 1;
      renderResultCard(result, file, index);
      setMessage(`已处理 ${completed}/${selectedFiles.length}。`);
    } catch (error) {
      completed += 1;
      failed += 1;
      renderErrorCard(file, index, error);
      setMessage(`已处理 ${completed}/${selectedFiles.length}，失败 ${failed} 张。`);
    }
  }

  updateProgress(completed, selectedFiles.length);
  elements.summaryText.textContent = `完成 ${completed} 张 · 失败 ${failed} 张 · ${datasetLabel(dataset)}`;
  elements.progressWrap.hidden = true;
  setBusy(false);
}

async function recognizeOne(file, dataset) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('dataset', dataset);

  const response = await fetch(`${API_BASE}/recognize`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }

  return response.json();
}

function appendPendingResult(file, index) {
  if (index === 0) {
    resultRecords = [];
    carouselIndex = 0;
  }
  resultRecords[index] = { status: 'pending', file, index };
  renderResultViews();
}

function renderResultCard(result, file, index) {
  resultRecords[index] = { status: 'done', file, index, result };
  renderResultViews();
}

function renderErrorCard(file, index, error) {
  resultRecords[index] = { status: 'error', file, index, error };
  renderResultViews();
}

function renderResultViews() {
  renderGridView();
  renderCarouselView();
}

function renderGridView() {
  const records = resultRecords.filter(Boolean);
  if (!records.length) {
    elements.resultsGrid.innerHTML = '<div class="empty-row">标注结果会逐张显示在这里</div>';
    return;
  }

  elements.resultsGrid.innerHTML = records.map((record) => renderResultRecord(record)).join('');
}

function renderCarouselView() {
  const records = resultRecords.filter(Boolean);
  const total = records.length;
  if (!total) {
    carouselIndex = 0;
    elements.carouselView.classList.add('empty');
    elements.carouselStage.innerHTML = '<div class="empty-row">标注结果会逐张显示在这里</div>';
    elements.carouselCounter.textContent = '0 / 0';
    elements.carouselPrev.disabled = true;
    elements.carouselNext.disabled = true;
    return;
  }

  elements.carouselView.classList.remove('empty');
  carouselIndex = Math.min(carouselIndex, total - 1);
  elements.carouselStage.innerHTML = renderResultRecord(records[carouselIndex], 'carousel-card');
  elements.carouselCounter.textContent = `${carouselIndex + 1} / ${total}`;
  elements.carouselPrev.disabled = false;
  elements.carouselNext.disabled = false;
}

function renderResultRecord(record, extraClass = '') {
  const classes = ['result-card', extraClass];
  if (record.status === 'pending') classes.push('pending');
  if (record.status === 'error') classes.push('error');

  if (record.status === 'pending') {
    return `
      <article class="${classes.filter(Boolean).join(' ')}" id="${resultId(record.index)}">
        <div class="result-thumb"><span>处理中</span></div>
        <div class="result-body">
          <div class="result-title">${escapeHtml(displayName(record.file))}</div>
          <div class="face-meta">等待后端返回结果...</div>
        </div>
      </article>
    `;
  }

  if (record.status === 'error') {
    return `
      <article class="${classes.filter(Boolean).join(' ')}" id="${resultId(record.index)}">
        <div class="result-thumb"><span>失败</span></div>
        <div class="result-body">
          <div class="result-title">${escapeHtml(displayName(record.file))}</div>
          <div class="face-meta">${escapeHtml(record.error.message)}</div>
        </div>
      </article>
    `;
  }

  const result = record.result;
  const faceCount = result.face_count ?? 0;
  const faces = result.faces || [];
  return `
    <article class="${classes.filter(Boolean).join(' ')}" id="${resultId(record.index)}">
      <div class="result-thumb ${result.annotated_image ? 'has-image' : ''}">
        ${result.annotated_image ? `<div class="result-image" role="button" tabindex="0" data-preview-index="${record.index}" aria-label="预览 ${escapeHtml(displayName(record.file))}" style="background-image: url(${result.annotated_image})"></div>` : '<span>无图片</span>'}
      </div>
      <div class="result-body">
        <div class="result-title">${escapeHtml(displayName(record.file))}</div>
        <div class="face-meta">检测到 ${faceCount} 张人脸 · ${escapeHtml(datasetLabel(result.dataset))}</div>
        <div class="faces compact">
          ${faces.length ? faces.map((face, i) => renderFace(face, i)).join('') : '<div class="face-row"><span>未检测到人脸</span><span class="face-meta">空</span></div>'}
        </div>
      </div>
    </article>
  `;
}

function renderFace(face, index) {
  const label = face.identity_id === face.name ? face.identity_id : `${face.identity_id} · ${face.name}`;
  return `
    <div class="face-row">
      <div>
        <div class="face-name">${index + 1}. ${escapeHtml(label)}</div>
        <div class="face-meta">位置 [${face.bbox.join(', ')}]</div>
      </div>
      <div class="face-meta">分数 ${Number(face.score).toFixed(3)}</div>
    </div>
  `;
}

function clearResults() {
  resultRecords = [];
  carouselIndex = 0;
  renderResultViews();
  elements.summaryText.textContent = '等待识别';
  updateProgress(0, selectedFiles.length || 1);
  elements.progressWrap.hidden = true;
}

function updateProgress(done, total) {
  const percent = total ? Math.round((done / total) * 100) : 0;
  elements.progressBar.style.width = `${percent}%`;
  if (done === 0) {
    elements.summaryText.textContent = selectedFiles.length ? `已处理 0/${selectedFiles.length}` : '等待识别';
  } else {
    elements.summaryText.textContent = `已处理 ${done}/${total}`;
  }
}

function updateControls() {
  const dataset = elements.datasetSelect.value;
  const exists = registryStatus?.registries?.[dataset]?.exists;
  const offline = elements.backendStatus.classList.contains('bad');
  const evalDataset = elements.evalDatasetSelect.value;
  const evalExists = registryStatus?.registries?.[evalDataset]?.exists;
  elements.recognizeButton.disabled = !selectedFiles.length || exists === false || offline || isProcessing;
  elements.reloadButton.disabled = offline || isProcessing;
  elements.clearButton.disabled = isProcessing || !selectedFiles.length;
  elements.folderButton.disabled = isProcessing;
  elements.evalRunButton.disabled = offline || evalExists === false || isEvaluating;
}

function setBusy(busy) {
  isProcessing = busy;
  elements.datasetSelect.disabled = busy;
  elements.fileInput.disabled = busy;
  elements.folderInput.disabled = busy;
  for (const button of elements.queueList.querySelectorAll('.queue-delete')) {
    button.disabled = busy;
  }
  updateControls();
}

function setStatus(text, kind) {
  elements.backendStatus.textContent = text;
  elements.backendStatus.className = `status ${kind}`.trim();
}

function setMessage(text) {
  elements.message.textContent = text;
}

function fileKey(file) {
  return `${displayName(file)}-${file.size}-${file.lastModified}`;
}

function displayName(file) {
  return file.webkitRelativePath || file.name;
}

function resultId(index) {
  return `result-${index}`;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`;
}

function datasetLabel(dataset) {
  return dataset === 'self' ? '自采集 20 人' : 'CelebA 100';
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
