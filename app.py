"""Applicazione desktop per trascrivere registrazioni audio."""

import logging
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import NamedTemporaryFile
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


LANGUAGES = {"Italiano": "it", "Inglese": "en", "Automatica": None}
MODELS = {"Base · rapido": "base", "Small · più accurato": "small"}
AUDIO_TYPES = (
    ("File audio", ("*.mp3", "*.wav", "*.m4a", "*.ogg", "*.flac", "*.opus", "*.aac")),
    ("Tutti i file", "*"),
)


class Transcriber:
    def __init__(self):
        self.model_name = None
        self.model = None

    def transcribe(self, source, language, model_name):
        from faster_whisper import WhisperModel

        if self.model_name != model_name:
            self.model_name = None
            self.model = None
            self.model = WhisperModel(model_name, device="cpu", compute_type="int8")
            self.model_name = model_name

        segments, info = self.model.transcribe(
            str(source), language=language, task="transcribe", vad_filter=True
        )
        parts = (segment.text.strip() for segment in segments)
        return " ".join(filter(None, parts)), info.language


def write_text(path, content):
    # Scrivi in un file adiacente prima di sostituire una trascrizione esistente.
    with NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as file:
        staged = Path(file.name)
        try:
            file.write(content + "\n")
            file.close()
            staged.replace(path)
        finally:
            file.close()
            staged.unlink(missing_ok=True)


class App:
    def __init__(self, root):
        self.root = root
        self.source = None
        self.result_source = None
        self.future = None
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.transcriber = Transcriber()
        self.filename = tk.StringVar(value="Nessun file selezionato")
        self.language = tk.StringVar(value="Italiano")
        self.model = tk.StringVar(value="Base · rapido")
        self.status = tk.StringVar(value="Seleziona una registrazione per iniziare.")

        root.title("MP3reading")
        root.geometry("760x550")
        root.minsize(550, 390)
        root.protocol("WM_DELETE_WINDOW", self.close)

        panel = ttk.Frame(root, padding=20)
        panel.pack(fill="both", expand=True)
        logo_path = Path(__file__).resolve().parent / "logo.png"
        logo = tk.PhotoImage(file=str(logo_path), master=root)
        self.logo = logo.subsample(6)
        root.iconphoto(True, logo, logo.subsample(8))

        heading = ttk.Frame(panel)
        heading.pack(fill="x", pady=(0, 14))
        ttk.Label(heading, image=self.logo).pack(side="left", padx=(0, 8))
        ttk.Label(heading, text="Trascrivi audio", font=("Segoe UI", 19, "bold")).pack(side="left")

        picker = ttk.Frame(panel)
        picker.pack(fill="x")
        self.choose_button = ttk.Button(picker, text="Scegli audio…", command=self.choose)
        self.choose_button.pack(side="left")
        ttk.Label(picker, textvariable=self.filename, width=30).pack(
            side="left", padx=10, fill="x", expand=True
        )

        options = ttk.Frame(panel)
        options.pack(fill="x", pady=12)
        ttk.Label(options, text="Lingua").pack(side="left")
        self.language_box = ttk.Combobox(
            options, textvariable=self.language, values=tuple(LANGUAGES),
            width=14, state="readonly",
        )
        self.language_box.pack(side="left", padx=(6, 15))
        ttk.Label(options, text="Modello").pack(side="left")
        self.model_box = ttk.Combobox(
            options, textvariable=self.model, values=tuple(MODELS), width=21, state="readonly",
        )
        self.model_box.pack(side="left", padx=6)

        actions = ttk.Frame(panel)
        actions.pack(fill="x", pady=(0, 12))
        self.start_button = ttk.Button(actions, text="Trascrivi", command=self.start, state="disabled")
        self.start_button.pack(side="left")
        self.copy_button = ttk.Button(actions, text="Copia testo", command=self.copy, state="disabled")
        self.copy_button.pack(side="left", padx=6)
        self.save_button = ttk.Button(actions, text="Salva TXT…", command=self.save, state="disabled")
        self.save_button.pack(side="left")

        self.progress = ttk.Progressbar(panel, mode="indeterminate")
        self.progress.pack(fill="x")
        ttk.Label(panel, textvariable=self.status, wraplength=495).pack(anchor="w", pady=(6, 10))
        self.editor = ScrolledText(panel, wrap="word", undo=True, padx=10, pady=10, state="disabled")
        self.editor.pack(fill="both", expand=True)

    def choose(self):
        filename = filedialog.askopenfilename(parent=self.root, filetypes=AUDIO_TYPES)
        if filename:
            self.source = Path(filename)
            self.filename.set(self.source.name)
            self.status.set("File pronto. Premi Trascrivi.")
            self.start_button.config(state="normal")

    def start(self):
        if self.future is not None or self.source is None:
            return
        if not self.source.is_file():
            messagebox.showerror("File non disponibile", "Seleziona di nuovo l’audio.", parent=self.root)
            return

        self.status.set("Trascrizione in corso. Il primo utilizzo può richiedere il download del modello.")
        self.progress.start()
        self.set_busy(True)
        self.future = self.worker.submit(
            self.transcriber.transcribe, self.source, LANGUAGES[self.language.get()],
            MODELS[self.model.get()],
        )
        self.root.after(100, self.check_result)

    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for button in (self.choose_button, self.start_button):
            button.config(state=state)
        for box in (self.language_box, self.model_box):
            box.config(state="disabled" if busy else "readonly")
        result_state = "normal" if not busy and self.result_source is not None else "disabled"
        for control in (self.copy_button, self.save_button, self.editor):
            control.config(state=result_state)

    def check_result(self):
        if not self.future.done():
            self.root.after(100, self.check_result)
            return

        self.progress.stop()
        try:
            content, language = self.future.result()
            self.editor.config(state="normal")
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", content)
            self.editor.edit_reset()
            self.result_source = self.source if content else None
            if content:
                self.status.set(f"Trascrizione completata · {self.source.name} · {language.upper()}")
            else:
                self.status.set("Nessun parlato rilevato.")
        except Exception as error:
            logging.exception("Trascrizione fallita")
            self.status.set("Errore durante la trascrizione.")
            detail = str(error) or type(error).__name__
            if isinstance(error, ModuleNotFoundError):
                detail = f"{detail}\n\nInstalla le dipendenze seguendo il README."
            messagebox.showerror("Trascrizione fallita", detail, parent=self.root)
        finally:
            self.future = None
            self.set_busy(False)

    def copy(self):
        content = self.editor.get("1.0", "end-1c").strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.status.set("Testo copiato negli appunti.")

    def save(self):
        content = self.editor.get("1.0", "end-1c").strip()
        if not content:
            self.status.set("Il testo è vuoto.")
            return
        filename = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".txt", filetypes=(("File di testo", "*.txt"),),
            initialfile=self.result_source.stem + ".txt",
        )
        if not filename:
            return
        destination = Path(filename)
        try:
            if destination.suffix.lower() != ".txt":
                raise OSError("Scegli un nome con estensione .txt.")
            if destination.resolve() in (self.source.resolve(), self.result_source.resolve()):
                raise OSError("Scegli un nome diverso da quello del file audio.")
            write_text(destination, content)
        except OSError as error:
            messagebox.showerror("Impossibile salvare", str(error), parent=self.root)
            return
        self.status.set(f"Testo salvato in {destination.name}.")

    def close(self):
        if self.future is not None:
            messagebox.showinfo(
                "Trascrizione in corso", "Attendi la fine della trascrizione prima di chiudere.",
                parent=self.root,
            )
            return
        self.worker.shutdown(wait=False)
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    App(window)
    window.mainloop()
