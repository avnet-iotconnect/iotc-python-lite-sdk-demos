const bankrollEl = document.getElementById("bankroll");
const bestBankrollEl = document.getElementById("best-bankroll");
const betEl = document.getElementById("bet");
const handNumberEl = document.getElementById("hand-number");
const modeEl = document.getElementById("mode");
const flashText = document.getElementById("flash-text");
const audioDeviceEl = document.getElementById("audio-device");
const modelNameEl = document.getElementById("model-name");
const modelPackageEl = document.getElementById("model-package");
const cloudStatusEl = document.getElementById("cloud-status");
const dealerTotalEl = document.getElementById("dealer-total");
const playerTotalEl = document.getElementById("player-total");
const dealerCardsEl = document.getElementById("dealer-cards");
const playerCardsEl = document.getElementById("player-cards");
const roundResultEl = document.getElementById("round-result");
const lastCommandEl = document.getElementById("last-command");
const lastConfidenceEl = document.getElementById("last-confidence");
const eventsEl = document.getElementById("events");
const chipBetEl = document.getElementById("chip-bet");
const chipBankrollEl = document.getElementById("chip-bankroll");
const chipBestEl = document.getElementById("chip-best");
const stackBetEl = document.getElementById("stack-bet");
const stackBankrollEl = document.getElementById("stack-bankroll");
const stackBestEl = document.getElementById("stack-best");
let lastDealerSignature = "";
let lastPlayerSignature = "";

function cardSignature(cards) {
  return cards.map((card) => `${card.rank}${card.suit}`).join("|");
}

function renderCards(target, cards, signatureKey) {
  const nextSignature = cardSignature(cards);
  if (signatureKey === "dealer" && nextSignature === lastDealerSignature) {
    return;
  }
  if (signatureKey === "player" && nextSignature === lastPlayerSignature) {
    return;
  }

  target.innerHTML = "";
  for (const card of cards) {
    const node = document.createElement("div");
    node.className = "card";
    const isRed = card.suit === "\u2665" || card.suit === "\u2666";
    node.innerHTML = `<span class="${isRed ? "red" : ""}">${card.rank}</span><small class="${isRed ? "red" : ""}">${card.suit}</small>`;
    target.appendChild(node);
  }

  if (signatureKey === "dealer") {
    lastDealerSignature = nextSignature;
  }
  if (signatureKey === "player") {
    lastPlayerSignature = nextSignature;
  }
}

function renderEvents(events) {
  eventsEl.innerHTML = "";
  for (const event of events) {
    const row = document.createElement("div");
    row.className = "event";
    row.innerHTML = `<strong>${event.title}</strong><span>${event.detail} * ${event.at}</span>`;
    eventsEl.appendChild(row);
  }
}

function updateStack(node, value, maxValue) {
  const ratio = maxValue > 0 ? Math.max(0.15, Math.min(1, value / maxValue)) : 0.15;
  node.style.setProperty("--stack-scale", ratio.toFixed(3));
}

async function sendCommand(command) {
  await fetch("/api/action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  });
}

function renderState(state) {
  document.body.classList.remove("state-win", "state-blackjack", "state-push", "state-lose", "state-bust");
  const resultText = (state.round_result || "").toLowerCase();
  if (resultText.includes("blackjack")) {
    document.body.classList.add("state-blackjack");
  } else if (state.dealer_bust) {
    document.body.classList.add("state-bust");
  } else if (resultText.includes("you win")) {
    document.body.classList.add("state-win");
  } else if (resultText.includes("push")) {
    document.body.classList.add("state-push");
  } else if (resultText.includes("lose")) {
    document.body.classList.add("state-lose");
  }

  bankrollEl.textContent = state.bankroll;
  bestBankrollEl.textContent = state.best_bankroll;
  betEl.textContent = state.bet;
  chipBetEl.textContent = state.bet;
  chipBankrollEl.textContent = state.bankroll;
  chipBestEl.textContent = state.best_bankroll;
  const stackMax = Math.max(state.best_bankroll || 0, state.bankroll || 0, state.bet || 0, 100);
  updateStack(stackBetEl, state.bet, stackMax);
  updateStack(stackBankrollEl, state.bankroll, stackMax);
  updateStack(stackBestEl, state.best_bankroll, stackMax);
  handNumberEl.textContent = state.hand_number;
  modeEl.textContent = state.mode;
  flashText.textContent = state.flash_text || state.round_result;
  audioDeviceEl.textContent = state.audio_device;
  modelNameEl.textContent = state.model_name;
  modelPackageEl.textContent = state.model_package || "package unavailable";
  cloudStatusEl.textContent = state.cloud_connected ? `cloud: ${state.cloud_status}` : `cloud: ${state.cloud_status || "offline"}`;
  dealerTotalEl.textContent = state.dealer_total;
  playerTotalEl.textContent = state.player_total;
  roundResultEl.textContent = state.round_result;
  renderCards(dealerCardsEl, state.dealer_cards, "dealer");
  renderCards(playerCardsEl, state.player_cards, "player");
  renderEvents(state.events);

  if (state.last_result && state.last_result.label) {
    lastCommandEl.textContent = state.last_result.label;
    lastConfidenceEl.textContent = state.last_result.confidence.toFixed(3);
  } else {
    lastCommandEl.textContent = "waiting";
    lastConfidenceEl.textContent = "0.000";
  }
}

async function refresh() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    const state = await response.json();
    renderState(state);
  } catch (error) {
    flashText.textContent = "Waiting for blackjack table";
  }
}

document.querySelectorAll("[data-command]").forEach((button) => {
  button.addEventListener("click", () => sendCommand(button.dataset.command));
});

document.addEventListener("keydown", (event) => {
  const map = {
    Enter: "deal",
    " ": "deal",
    h: "hit",
    s: "stand",
    d: "double",
    f: "safe-bet",
    ArrowUp: "bet-up",
    ArrowDown: "bet-down",
    ArrowRight: "bet-up",
    ArrowLeft: "bet-down",
    Escape: "reset",
  };
  const command = map[event.key];
  if (command) {
    event.preventDefault();
    sendCommand(command);
  }
});

setInterval(refresh, 400);
refresh();
