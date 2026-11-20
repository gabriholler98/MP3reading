const form = document.querySelector("#form");
const audio = document.querySelector("#audio");
const language = document.querySelector("#language");
const transcribe = document.querySelector("#transcribe");
const output = document.querySelector("#output");
const copy = document.querySelector("#copy");
const save = document.querySelector("#save");
const status = document.querySelector("#status");
const exportStatus = document.querySelector("#export-status");
const progress = document.querySelector("#progress");

let worker;
let busy = false;
let resultName = "trascrizione";

function updateButtons() {
  copy.disabled = save.disabled = busy || !output.value.trim();
}

function setBusy(value) {
  busy = value;
  audio.disabled = language.disabled = transcribe.disabled = value;
  output.readOnly = value;
  progress.hidden = !value;
  updateButtons();
}

async function decode(file) {
  // Web Audio ricampiona al ritmo richiesto da Whisper.
  const decoder = new OfflineAudioContext(1, 1, 16000);
  const decoded = await decoder.decodeAudioData(await file.arrayBuffer());
  const mono = new Float32Array(decoded.length);
  for (let i = 0; i < decoded.numberOfChannels; i++) {
    const channel = decoded.getChannelData(i);
    for (let offset = 0; offset < channel.length; offset++) {
      mono[offset] += channel[offset] / decoded.numberOfChannels;
    }
  }
  return mono;
}

function getWorker() {
  if (worker) return worker;
  worker = new Worker(new URL("./whisper-worker.js", import.meta.url), { type: "module" });
  worker.onmessage = ({ data }) => {
    if (data.type === "status") {
      status.textContent = data.message;
      return;
    }
    if (data.type === "result") {
      output.value = data.text;
      resultName = audio.files[0].name.replace(/\.[^.]+$/, "") || "trascrizione";
      status.textContent = data.text ? "Trascrizione completata." : "Nessun parlato rilevato.";
    } else {
      status.textContent = data.message;
    }
    setBusy(false);
  };
  worker.onerror = () => {
    status.textContent = "Impossibile avviare il modello. Aggiorna la pagina o prova un browser recente.";
    worker.terminate();
    worker = undefined;
    setBusy(false);
  };
  return worker;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy || !audio.files.length) return;
  setBusy(true);
  exportStatus.textContent = "";
  status.textContent = "Lettura del file audio…";
  try {
    const samples = await decode(audio.files[0]);
    status.textContent = "Preparazione del modello…";
    getWorker().postMessage({ samples, language: language.value }, [samples.buffer]);
  } catch (error) {
    console.error(error);
    status.textContent = "Impossibile leggere il file. Prova una registrazione MP3 o WAV valida.";
    setBusy(false);
  }
});

output.addEventListener("input", updateButtons);

copy.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(output.value.trim());
    exportStatus.textContent = "Testo copiato.";
  } catch {
    output.select();
    exportStatus.textContent = "Premi Ctrl+C o ⌘C per copiare il testo selezionato.";
  }
});

save.addEventListener("click", () => {
  const file = new Blob([output.value.trim() + "\n"], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(file);
  const link = document.createElement("a");
  link.href = url;
  link.download = resultName + ".txt";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  exportStatus.textContent = "Download del TXT avviato.";
});
