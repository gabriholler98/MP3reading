let transcriber;

self.onmessage = async ({ data }) => {
  try {
    if (!transcriber) {
      self.postMessage({ type: "status", message: "Caricamento del modello Whisper…" });
      const { env, pipeline } = await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1");
      env.allowLocalModels = false;
      env.backends.onnx.wasm.numThreads = 1;
      transcriber = await pipeline("automatic-speech-recognition", "onnx-community/whisper-base", {
        device: "wasm",
        dtype: "q8",
      });
    }
    self.postMessage({ type: "status", message: "Trascrizione dell’audio in corso…" });
    const options = { task: "transcribe", chunk_length_s: 30, stride_length_s: 5 };
    if (data.language) options.language = data.language;
    const result = await transcriber(data.samples, options);
    self.postMessage({ type: "result", text: result.text.trim() });
  } catch (error) {
    console.error(error);
    self.postMessage({
      type: "error",
      message: "Trascrizione non riuscita. Controlla la connessione e riprova con un browser aggiornato.",
    });
  }
};
