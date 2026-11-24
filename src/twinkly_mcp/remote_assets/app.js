"use strict";

const statusMessage = document.querySelector("#status");
const presets = document.querySelector("#presets");

function lock() {
  presets.hidden = true;
  presets.replaceChildren();
  statusMessage.textContent = "Scan the QR code to unlock the remote.";
}

async function play(preset, button) {
  button.disabled = true;
  try {
    const response = await fetch("/remote/play", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({preset}),
    });
    if (response.status === 401) {
      lock();
    } else if (response.ok) {
      statusMessage.textContent = `${button.textContent} queued.`;
    } else {
      statusMessage.textContent = "Preset is unavailable.";
    }
  } catch {
    statusMessage.textContent = "Couldn't reach the remote. Try again.";
  } finally {
    button.disabled = false;
  }
}

async function connect() {
  const key = new URLSearchParams(location.hash.slice(1)).get("key");
  if (location.hash) history.replaceState(null, "", location.pathname);
  presets.hidden = true;
  presets.replaceChildren();
  statusMessage.textContent = "Connecting…";
  try {
    if (key) {
      const unlock = await fetch("/remote/unlock", {
        method: "POST",
        headers: {"X-Twinkly-Remote-Key": key},
      });
      if (!unlock.ok) {
        lock();
        return;
      }
    }
    const response = await fetch("/remote/presets");
    if (!response.ok) {
      lock();
      return;
    }

    const {presets: available} = await response.json();
    for (const preset of available) {
      const button = document.createElement("button");
      button.type = "button";
      const words = preset.replace(/[-_]/g, " ");
      button.textContent = preset === "skal" ? "Skål" : words[0].toUpperCase() + words.slice(1);
      button.addEventListener("click", () => play(preset, button));
      presets.append(button);
    }
    presets.hidden = available.length === 0;
    statusMessage.textContent = available.length ? "Choose a preset." : "No approved presets are available.";
  } catch {
    statusMessage.textContent = "Couldn't reach the remote. Scan the QR code again.";
  }
}

window.addEventListener("hashchange", connect);
connect();
