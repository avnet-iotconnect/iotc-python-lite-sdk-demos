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

function activeLabel() {
  return newLabelEl.value.trim() || existingLabelEl.value.trim();
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
    row.innerHTML = `
      <div>
        <strong>${label.label}</strong>
        <span>${label.clip_count} clip(s)</span>
      </div>
      <small>${label.latest_capture || "no captures yet"}</small>
    `;
    row.addEventListener("click", () => {
      existingLabelEl.value = label.label;
      newLabelEl.value = "";
      recordLabelEl.textContent = label.label;
      recordPromptEl.textContent = "Press Start Recording, say the command once, then press Stop And Save Clip.";
    });
    labelListEl.appendChild(row);
  }

  if (selectedLabel && labels.some((label) => label.label === selectedLabel)) {
    existingLabelEl.value = selectedLabel;
  }
}

function renderEvents(events) {
  eventsEl.innerHTML = "";
  for (const event of events) {
    const row = document.createElement("article");
    row.className = "event-row";
    row.innerHTML = `<strong>${event.title}</strong><span>${event.detail}</span><small>${event.at}</small>`;
    eventsEl.appendChild(row);
  }
}

function renderState(state) {
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
  smStatusEl.textContent = state.training.in_progress
    ? "workflow running"
    : state.aws.sagemaker_ready
      ? "training ready"
    : state.upload.ready
      ? "upload ready"
      : "needs config";
  smStatusEl.classList.toggle("ready", state.training.ready);

  recordPhaseEl.textContent = state.recording.active ? "Recording" : "Ready";
  recordPhaseEl.classList.toggle("live", state.recording.active);
  recordLabelEl.textContent = state.recording.active ? state.recording.label : activeLabel() || "No folder selected";
  recordPromptEl.textContent = state.recording.active
    ? `Speak now for "${state.recording.label}", then press Stop And Save Clip.`
    : `Choose a label and record one clip at a time. Aim for about ${state.recording.recommended_seconds} second(s) per utterance.`;
  recordFileEl.textContent = state.recording.active
    ? `Saving to ${state.recording.output_file} - ${state.recording.elapsed_seconds.toFixed(1)}s`
    : "Press Start Recording for the next clip.";

  startRecordBtn.disabled = state.recording.active;
  stopRecordBtn.disabled = !state.recording.active;
  newLabelEl.disabled = state.recording.active;
  existingLabelEl.disabled = state.recording.active;
  uploadBtn.disabled = state.recording.active || !state.upload.ready;
  trainBtn.disabled = state.recording.active || !state.training.ready || state.training.in_progress;

  renderLabels(state.labels);
  renderEvents(state.events);
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

startRecordBtn.addEventListener("click", handleStartCapture);
stopRecordBtn.addEventListener("click", handleStopCapture);
uploadBtn.addEventListener("click", () => handleUpload("/api/aws/upload", "Upload"));
trainBtn.addEventListener("click", () => handleUpload("/api/aws/train", "SageMaker submit"));

setInterval(refresh, 1000);
refresh();
