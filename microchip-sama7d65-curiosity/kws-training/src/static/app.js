const audioDeviceEl = document.getElementById("audio-device");
const datasetRootEl = document.getElementById("dataset-root");
const awsRegionEl = document.getElementById("aws-region");
const dataBucketEl = document.getElementById("data-bucket");
const outputBucketEl = document.getElementById("output-bucket");
const uploadModeEl = document.getElementById("upload-mode");
const iotcStatusEl = document.getElementById("iotc-status");
const fileTopicEl = document.getElementById("file-topic");
const trainingModeEl = document.getElementById("training-mode");
const trainingStatusEl = document.getElementById("training-status");
const labelListEl = document.getElementById("label-list");
const eventsEl = document.getElementById("events");
const messageEl = document.getElementById("message");
const existingLabelEl = document.getElementById("existing-label");
const newLabelEl = document.getElementById("new-label");
const smStatusEl = document.getElementById("sm-status");
const recordPhaseEl = document.getElementById("record-phase");
const recordLabelEl = document.getElementById("record-label");
const recordPromptEl = document.getElementById("record-prompt");
const recordFileEl = document.getElementById("record-file");
const startRecordBtn = document.getElementById("start-record-btn");
const stopRecordBtn = document.getElementById("stop-record-btn");
const uploadBtn = document.getElementById("upload-btn");
const trainBtn = document.getElementById("train-btn");
const collectionStatusEl = document.getElementById("collection-status");
const collectionSummaryEl = document.getElementById("collection-summary");
const collectionStatsEl = document.getElementById("collection-stats");
const collectionPrioritiesEl = document.getElementById("collection-priorities");
const collectionSpecialsEl = document.getElementById("collection-specials");
const deployStatusEl = document.getElementById("deploy-status");
const deployTargetEl = document.getElementById("deploy-target");
const installedPackageEl = document.getElementById("installed-package");
const installedLabelsEl = document.getElementById("installed-labels");
const installedSourceEl = document.getElementById("installed-source");
const modelListEl = document.getElementById("model-list");
const refreshModelsBtn = document.getElementById("refresh-models-btn");
const installLatestBtn = document.getElementById("install-latest-btn");
const optimizeBtn = document.getElementById("optimize-btn");

let lastState = null;
let availableModels = [];
let modelOpInProgress = false;
let labelOpInProgress = false;

function activeLabel() {
  return newLabelEl.value.trim() || existingLabelEl.value.trim();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function clipSeconds() {
  return lastState?.capture?.clip_seconds || lastState?.recording?.recommended_seconds || 1;
}

function labelGuidance(label) {
  const seconds = clipSeconds();
  if (!label) {
    return {
      prompt: `Choose a label and record one clip at a time. Aim for about ${seconds} second(s) per utterance.`,
      detail: "Press Start Recording for the next clip.",
    };
  }
  if (label === "_unknown_") {
    return {
      prompt: "Record other spoken words or short phrases that are not valid commands.",
      detail: `Say one non-command utterance per ${seconds}-second clip. Avoid the real command words.`,
    };
  }
  if (label === "_background_noise_") {
    return {
      prompt: "Record ambient noise only. Stay quiet while the board captures the clip.",
      detail: `Use room tone, HVAC, keyboard clicks, fan noise, or chair movement in each ${seconds}-second clip.`,
    };
  }
  return {
    prompt: `Press Start Recording, say "${label}" once, then press Stop And Save Clip.`,
    detail: `Aim for about ${seconds} second(s) per clip and vary tone, speed, and microphone distance.`,
  };
}

function syncSelectionPreview() {
  if (lastState?.recording?.active) {
    return;
  }
  const label = activeLabel();
  const guidance = labelGuidance(label);
  recordLabelEl.textContent = label || "No folder selected";
  recordPromptEl.textContent = guidance.prompt;
  recordFileEl.textContent = guidance.detail;
}

function chooseLabel(label) {
  const option = Array.from(existingLabelEl.options).find((item) => item.value === label);
  if (option) {
    existingLabelEl.value = label;
    newLabelEl.value = "";
  } else {
    existingLabelEl.value = "";
    newLabelEl.value = label;
  }
  syncSelectionPreview();
}

function setMessage(text, error = false) {
  messageEl.textContent = text;
  messageEl.classList.toggle("error", error);
}

function renderLabels(labels) {
  const selectedLabel = existingLabelEl.value;
  labelListEl.innerHTML = "";
  existingLabelEl.innerHTML = '<option value="">Choose existing folder</option>';

  if (!labels.length) {
    labelListEl.innerHTML = '<div class="empty">No command folders yet. Type a new label and record the first clips.</div>';
    return;
  }

  for (const label of labels) {
    const option = document.createElement("option");
    option.value = label.label;
    option.textContent = `${label.label} (${label.clip_count})`;
    existingLabelEl.appendChild(option);

    const row = document.createElement("article");
    row.className = "folder-row";
    const canRetire = !["_unknown_", "_background_noise_"].includes(label.label);
    row.innerHTML = `
      <div class="folder-copy">
        <div>
          <strong>${escapeHtml(label.label)}</strong>
          <span>${label.clip_count} clip(s)</span>
        </div>
        <small>${escapeHtml(label.latest_capture || "no captures yet")}</small>
      </div>
      <div class="folder-actions">
        ${canRetire ? `<button class="danger ghost" ${labelOpInProgress ? "disabled" : ""} data-retire-label="${escapeHtml(label.label)}">Retire</button>` : ""}
      </div>
    `;
    row.addEventListener("click", () => chooseLabel(label.label));
    const retireButton = row.querySelector("[data-retire-label]");
    if (retireButton) {
      retireButton.addEventListener("click", (event) => {
        event.stopPropagation();
        handleRetireLabel(label.label);
      });
    }
    labelListEl.appendChild(row);
  }

  if (selectedLabel && labels.some((label) => label.label === selectedLabel)) {
    existingLabelEl.value = selectedLabel;
  }
}

async function handleRetireLabel(label) {
  if (!label) {
    return;
  }
  const confirmed = window.confirm(`Retire "${label}"?\n\nThis moves the folder out of datasets into retired-labels on the board. It does not delete the clips.`);
  if (!confirmed) {
    return;
  }
  labelOpInProgress = true;
  if (lastState) {
    renderState(lastState);
  }
  setMessage(`Retiring ${label}...`);
  try {
    const result = await readJson("/api/labels/retire", { label });
    if (!result.ok) {
      setMessage(result.error || `Unable to retire ${label}.`, true);
      return;
    }
    renderState(result.state);
    if (activeLabel() === label) {
      existingLabelEl.value = "";
      newLabelEl.value = "";
      syncSelectionPreview();
    }
    setMessage(`Retired ${label} to ${result.result.retired_to}.`);
  } catch (error) {
    setMessage(`Unable to retire ${label}: ${error}`, true);
  } finally {
    labelOpInProgress = false;
    await refresh();
  }
}

function isNoisyEvent(event) {
  if (!event) return false;
  if (event.title === "IOTCONNECT" && typeof event.detail === "string" && event.detail.startsWith("Sent periodic telemetry")) {
    return true;
  }
  return false;
}

function renderEvents(events) {
  eventsEl.innerHTML = "";
  const filtered = events.filter((event) => !isNoisyEvent(event));
  if (!filtered.length) {
    eventsEl.innerHTML = '<div class="empty">No recent board or AWS events.</div>';
    return;
  }
  for (const event of filtered) {
    const row = document.createElement("article");
    row.className = "event-row";
    row.innerHTML = `<strong>${escapeHtml(event.title)}</strong><span>${escapeHtml(event.detail)}</span><small>${escapeHtml(event.at)}</small>`;
    eventsEl.appendChild(row);
  }
}

function formatBytes(sizeBytes) {
  if (!sizeBytes) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let size = sizeBytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function renderModels() {
  modelListEl.innerHTML = "";
  const installedPackage = lastState?.deployment?.installed?.package_name || "";
  const installedSource = lastState?.runtime?.last_installed_model_s3_uri || "";

  if (!availableModels.length) {
    modelListEl.innerHTML = '<div class="empty">No converted model packages loaded yet. Press Refresh Model List after conversion completes.</div>';
    return;
  }

  const sameNameCount = installedPackage
    ? availableModels.reduce((acc, m) => acc + (m.package_name === installedPackage ? 1 : 0), 0)
    : 0;

  for (const model of availableModels) {
    const row = document.createElement("article");
    row.className = "model-row";
    let isInstalled = false;
    if (installedSource && installedSource === model.s3_uri) {
      isInstalled = true;
    } else if (!installedSource && installedPackage && installedPackage === model.package_name && sameNameCount === 1) {
      // Fallback only when the name is unambiguous; otherwise we can't tell which one
      isInstalled = true;
    }
    const installDisabled = modelOpInProgress || isInstalled;
    row.innerHTML = `
      <div class="model-copy">
        <strong>${escapeHtml(model.package_name)}</strong>
        <span>${escapeHtml(model.execution_name || "manual package")} - ${formatBytes(model.size_bytes)} - ${escapeHtml(model.last_modified || "unknown time")}</span>
        <small>${escapeHtml(model.s3_uri)}</small>
      </div>
      <div class="model-actions">
        ${isInstalled ? '<span class="model-tag">Installed</span>' : ""}
        <button ${installDisabled ? "disabled" : ""} data-s3-uri="${model.s3_uri}">${isInstalled ? "Installed" : "Install"}</button>
      </div>
    `;
    const button = row.querySelector("button");
    if (button) {
      button.addEventListener("click", () => handleInstallModel(model.s3_uri, model.package_name));
    }
    modelListEl.appendChild(row);
  }
}

function renderCollectionStats(plan) {
  const stats = [
    { label: "Command Labels", value: plan.stats.command_labels },
    { label: "Command Clips", value: plan.stats.command_clips },
    { label: "Below Minimum", value: plan.stats.commands_below_minimum },
    { label: "Below Target", value: plan.stats.commands_below_target },
    { label: "Unknown Clips", value: plan.stats.unknown_clips },
    { label: "Noise Clips", value: plan.stats.background_noise_clips },
  ];
  collectionStatsEl.innerHTML = stats
    .map((item) => `
      <article class="stat-tile">
        <span>${escapeHtml(item.label)}</span>
        <strong>${escapeHtml(item.value)}</strong>
      </article>
    `)
    .join("");
}

function progressPercent(count, target) {
  if (!target) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round((count / target) * 100)));
}

function renderPlanRow(item, buttonLabel = "Select") {
  const percent = progressPercent(item.clip_count, item.target);
  const examples = item.examples?.length
    ? `<div class="plan-examples">${item.examples.map((example) => `<span>${escapeHtml(example)}</span>`).join("")}</div>`
    : "";
  return `
    <article class="plan-row ${escapeHtml(item.status || "")}">
      <div class="plan-main">
        <div class="plan-head">
          <strong>${escapeHtml(item.title || item.label)}</strong>
          <span>${escapeHtml(item.label)}</span>
        </div>
        <p>${escapeHtml(item.priority_reason || item.guidance || "")}</p>
        <small>${escapeHtml(item.recording_tip || "")}</small>
        ${examples}
      </div>
      <div class="plan-side">
        <div class="plan-metric">${item.clip_count} / ${item.target}</div>
        <div class="plan-progress"><span style="width:${percent}%"></span></div>
        <button data-label="${escapeHtml(item.label)}">${escapeHtml(buttonLabel)}</button>
      </div>
    </article>
  `;
}

function bindPlanButtons(container) {
  container.querySelectorAll("button[data-label]").forEach((button) => {
    button.addEventListener("click", () => chooseLabel(button.dataset.label || ""));
  });
}

function renderCollectionPlan(plan) {
  collectionSummaryEl.textContent = plan.summary;
  collectionStatusEl.textContent = plan.readiness.replaceAll("-", " ");
  collectionStatusEl.classList.toggle("ready", plan.readiness === "ready");
  renderCollectionStats(plan);

  if (!plan.priorities.length) {
    collectionPrioritiesEl.innerHTML = '<div class="empty">No capture priorities yet. Create command folders to start the plan.</div>';
  } else {
    collectionPrioritiesEl.innerHTML = plan.priorities.map((item) => renderPlanRow(item, "Use Label")).join("");
    bindPlanButtons(collectionPrioritiesEl);
  }

  collectionSpecialsEl.innerHTML = plan.special_labels.map((item) => renderPlanRow(item, item.existing ? "Add Clips" : "Create Folder")).join("");
  bindPlanButtons(collectionSpecialsEl);
}

function renderState(state) {
  lastState = state;
  audioDeviceEl.textContent = state.audio_device;
  datasetRootEl.textContent = state.dataset_root;
  awsRegionEl.textContent = state.aws.region;
  dataBucketEl.textContent = state.aws.data_bucket || "not set";
  outputBucketEl.textContent = state.aws.output_bucket || "not set";
  trainingModeEl.textContent = state.training.mode;
  trainingStatusEl.textContent = state.training.status;
  uploadModeEl.textContent = state.upload.mode;
  iotcStatusEl.textContent = state.upload.status;
  fileTopicEl.textContent = state.iotconnect.file_topic || "not configured";
  deployTargetEl.textContent = state.deployment.target_models_dir;
  installedPackageEl.textContent = state.deployment.installed.package_name || "none";
  installedLabelsEl.textContent = state.deployment.installed.labels.length
    ? state.deployment.installed.labels.join(", ")
    : "none";
  installedSourceEl.textContent = state.runtime.last_installed_model_s3_uri || "none";
  renderCollectionPlan(state.collection_plan);

  smStatusEl.textContent = state.training.in_progress
    ? "workflow running"
    : state.aws.sagemaker_ready
      ? "training ready"
      : state.upload.ready
        ? "upload ready"
        : "needs config";
  smStatusEl.classList.toggle("ready", state.training.ready);
  deployStatusEl.textContent = state.deployment.ready ? "deploy ready" : "needs config";
  deployStatusEl.classList.toggle("ready", state.deployment.ready);

  recordPhaseEl.textContent = state.recording.active ? "Recording" : "Ready";
  recordPhaseEl.classList.toggle("live", state.recording.active);
  if (state.recording.active) {
    recordLabelEl.textContent = state.recording.label;
    recordPromptEl.textContent = `Speak now for "${state.recording.label}", then press Stop And Save Clip.`;
    recordFileEl.textContent = `Saving to ${state.recording.output_file} - ${state.recording.elapsed_seconds.toFixed(1)}s`;
  } else {
    syncSelectionPreview();
  }

  startRecordBtn.disabled = state.recording.active;
  stopRecordBtn.disabled = !state.recording.active;
  newLabelEl.disabled = state.recording.active;
  existingLabelEl.disabled = state.recording.active;
  uploadBtn.disabled = state.recording.active || !state.upload.ready;
  trainBtn.disabled = state.recording.active || !state.training.ready || state.training.in_progress;
  optimizeBtn.disabled = state.recording.active;
  refreshModelsBtn.disabled = modelOpInProgress || !state.deployment.ready;
  installLatestBtn.disabled = modelOpInProgress || !state.deployment.ready || !availableModels.length;

  renderLabels(state.labels);
  renderEvents(state.events);
  renderModels();
  if (!state.recording.active) {
    syncSelectionPreview();
  }
}

async function readJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  return response.json();
}

async function refresh() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    const state = await response.json();
    renderState(state);
  } catch (error) {
    setMessage(`Unable to load state: ${error}`, true);
  }
}

async function loadModels(showSuccessMessage = false) {
  try {
    const response = await fetch("/api/models", { cache: "no-store" });
    const payload = await response.json();
    if (!payload.ok) {
      availableModels = [];
      if (payload.state) {
        renderState(payload.state);
      } else {
        renderModels();
      }
      setMessage(payload.error || "Unable to load converted models.", true);
      return;
    }
    availableModels = payload.models || [];
    renderState(payload.state);
    if (showSuccessMessage) {
      setMessage(`Loaded ${availableModels.length} converted model package(s).`);
    }
  } catch (error) {
    setMessage(`Unable to load converted models: ${error}`, true);
  }
}

async function handleStartCapture() {
  const label = activeLabel();
  if (!label) {
    setMessage("Type a voice command or choose an existing folder first.", true);
    return;
  }

  startRecordBtn.disabled = true;
  setMessage(`Recording for ${label}. Speak once, then press Stop And Save Clip.`);
  try {
    const result = await readJson("/api/capture/start", { label });
    if (!result.ok) {
      setMessage(result.error, true);
      return;
    }
    renderState(result.state);
    setMessage(`Recording started for ${result.result.label}.`);
  } catch (error) {
    setMessage(`Unable to start recording: ${error}`, true);
  } finally {
    if (stopRecordBtn.disabled) {
      startRecordBtn.disabled = false;
    }
  }
}

async function handleStopCapture() {
  stopRecordBtn.disabled = true;
  setMessage("Stopping recording and saving clip...");
  try {
    const result = await readJson("/api/capture/stop", {});
    if (!result.ok) {
      setMessage(result.error, true);
      return;
    }
    renderState(result.state);
    existingLabelEl.value = result.result.label;
    newLabelEl.value = "";
    setMessage(`Saved ${result.result.file_name} to ${result.result.label} (${result.result.duration_seconds}s).`);
  } catch (error) {
    setMessage(`Unable to stop recording: ${error}`, true);
  } finally {
    if (startRecordBtn.disabled) {
      stopRecordBtn.disabled = false;
    }
  }
}

async function handleUpload(url, modeLabel) {
  uploadBtn.disabled = true;
  trainBtn.disabled = true;
  setMessage(`${modeLabel} in progress...`);
  try {
    const result = await readJson(url, {});
    if (!result.ok) {
      setMessage(result.error, true);
      return;
    }
    renderState(result.state);
    const destination = result.training
      ? (result.training.execution_arn || result.training.training_job_name || result.training.output_s3_uri)
      : result.upload.s3_uri;
    const suffix = result.upload.file_event_published ? " and FILE event published." : ".";
    setMessage(`${modeLabel} complete via ${result.upload.mode}: ${destination}${suffix}`);
  } catch (error) {
    setMessage(`${modeLabel} failed: ${error}`, true);
  } finally {
    await refresh();
  }
}

async function handleInstallModel(s3Uri = "", label = "latest model") {
  modelOpInProgress = true;
  if (lastState) {
    renderState(lastState);
  } else {
    refreshModelsBtn.disabled = true;
    installLatestBtn.disabled = true;
  }
  setMessage(`Installing ${label} onto the board...`);
  try {
    const result = await readJson("/api/models/install", s3Uri ? { s3_uri: s3Uri } : {});
    if (!result.ok) {
      setMessage(result.error, true);
      return;
    }
    availableModels = [];
    renderState(result.state);
    await loadModels(false);
    setMessage(`Installed ${result.result.installed.package_name || label} onto ${result.state.deployment.target_models_dir}. Restart the runtime app that uses /opt/demo/models if you want it to pick up the new files immediately.`);
  } catch (error) {
    setMessage(`Unable to install model: ${error}`, true);
  } finally {
    modelOpInProgress = false;
    await refresh();
    renderModels();
  }
}

async function handleOptimize() {
  if (lastState?.recording?.active) {
    setMessage("Stop the active recording before running Optimize Clips.", true);
    return;
  }
  optimizeBtn.disabled = true;
  trainBtn.disabled = true;
  uploadBtn.disabled = true;
  setMessage("Optimizing clips: trimming silence and re-padding to 1 second...");
  try {
    const result = await readJson("/api/dataset/optimize", {});
    if (!result.ok) {
      setMessage(result.error || "Unable to optimize clips.", true);
      return;
    }
    const summary = result.result || {};
    const optimized = summary.optimized_files ?? 0;
    const unchanged = summary.unchanged_files ?? 0;
    const skipped = summary.skipped_files ?? 0;
    const backup = summary.backup_root ? ` Backups: ${summary.backup_root}` : "";
    setMessage(`Optimize complete: ${optimized} changed, ${unchanged} unchanged, ${skipped} skipped.${backup}`);
  } catch (error) {
    setMessage(`Unable to optimize clips: ${error}`, true);
  } finally {
    optimizeBtn.disabled = false;
    await refresh();
  }
}

startRecordBtn.addEventListener("click", handleStartCapture);
stopRecordBtn.addEventListener("click", handleStopCapture);
uploadBtn.addEventListener("click", () => handleUpload("/api/aws/upload", "Upload"));
trainBtn.addEventListener("click", () => handleUpload("/api/aws/train", "SageMaker submit"));
refreshModelsBtn.addEventListener("click", () => loadModels(true));
installLatestBtn.addEventListener("click", () => handleInstallModel("", "latest converted model"));
optimizeBtn.addEventListener("click", handleOptimize);
existingLabelEl.addEventListener("change", syncSelectionPreview);
newLabelEl.addEventListener("input", syncSelectionPreview);

setInterval(refresh, 1000);
refresh();
loadModels(false);
