import hashlib
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "Duplicate File Cleaner"
HASH_CHUNK_SIZE = 1024 * 1024


class DuplicateCleanerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x560")
        self.minsize(700, 500)

        self.folder_var = tk.StringVar()
        self.recursive_var = tk.BooleanVar(value=True)
        self.total_files_var = tk.StringVar(value="0")
        self.duplicates_found_var = tk.StringVar(value="0")
        self.duplicates_removed_var = tk.StringVar(value="0")
        self.space_recovered_var = tk.StringVar(value="0 B")
        self.status_var = tk.StringVar(value="Ready")
        self._busy = False

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=14)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Duplicate File Cleaner", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(main, text="Select a folder, scan it, and remove exact duplicate files.").pack(anchor="w", pady=(2, 14))

        folder_frame = ttk.Frame(main)
        folder_frame.pack(fill="x")
        ttk.Label(folder_frame, text="Folder:").pack(side="left")
        ttk.Entry(folder_frame, textvariable=self.folder_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(folder_frame, text="Browse...", command=self.browse_folder).pack(side="left")

        ttk.Checkbutton(main, text="Include subfolders", variable=self.recursive_var).pack(anchor="w", pady=(10, 12))

        button_frame = ttk.Frame(main)
        button_frame.pack(fill="x", pady=(0, 14))

        self.scan_button = ttk.Button(button_frame, text="Scan Only", command=lambda: self.start_scan(False))
        self.scan_button.pack(side="left")

        self.delete_button = ttk.Button(button_frame, text="Scan & Delete Duplicates", command=lambda: self.start_scan(True))
        self.delete_button.pack(side="left", padx=(8, 0))

        stats = ttk.LabelFrame(main, text="Results", padding=12)
        stats.pack(fill="x", pady=(0, 12))

        for row, (label, variable) in enumerate([
            ("Total files scanned", self.total_files_var),
            ("Duplicates found", self.duplicates_found_var),
            ("Duplicates removed", self.duplicates_removed_var),
            ("Space recovered", self.space_recovered_var),
        ]):
            ttk.Label(stats, text=label + ":").grid(row=row, column=0, sticky="w", pady=3)
            ttk.Label(stats, textvariable=variable, font=("Segoe UI", 10, "bold")).grid(row=row, column=1, sticky="w", padx=(12, 0), pady=3)

        log_frame = ttk.LabelFrame(main, text="Activity", padding=8)
        log_frame.pack(fill="both", expand=True)

        self.log = tk.Text(log_frame, wrap="word", height=14, state="disabled", font=("Consolas", 9))
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(10, 0))
        self.progress = ttk.Progressbar(bottom, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True)
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left", padx=(10, 0))

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder to scan")
        if folder:
            self.folder_var.set(folder)

    def set_busy(self, busy):
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.scan_button.configure(state=state)
        self.delete_button.configure(state=state)
        if busy:
            self.progress.start(10)
        else:
            self.progress.stop()

    def append_log(self, text):
        self.after(0, self._append_log_ui, text)

    def _append_log_ui(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def start_scan(self, delete_duplicates):
        if self._busy:
            return

        folder = self.folder_var.get().strip()
        if not folder:
            messagebox.showwarning(APP_TITLE, "Select a folder first.")
            return

        root = Path(folder)
        if not root.exists() or not root.is_dir():
            messagebox.showerror(APP_TITLE, "The selected folder does not exist.")
            return

        if delete_duplicates:
            answer = messagebox.askyesno(
                APP_TITLE,
                "This will permanently delete exact duplicate files.\n\nOne copy of each duplicate set will be kept.\n\nContinue?"
            )
            if not answer:
                return

        self.clear_log()
        self.total_files_var.set("0")
        self.duplicates_found_var.set("0")
        self.duplicates_removed_var.set("0")
        self.space_recovered_var.set("0 B")
        self.status_var.set("Scanning...")
        self.set_busy(True)

        threading.Thread(target=self.scan_worker, args=(root, self.recursive_var.get(), delete_duplicates), daemon=True).start()

    def scan_worker(self, root, recursive, delete_duplicates):
        try:
            files = self.get_files(root, recursive)
            self.after(0, self.total_files_var.set, str(len(files)))
            self.append_log(f"Files discovered: {len(files)}")

            by_size = {}
            for path in files:
                try:
                    by_size.setdefault(path.stat().st_size, []).append(path)
                except (OSError, PermissionError) as exc:
                    self.append_log(f"Skipped: {path} ({exc})")

            by_hash = {}
            for size, paths in by_size.items():
                if len(paths) < 2:
                    continue
                for path in paths:
                    try:
                        digest = self.sha256_file(path)
                        by_hash.setdefault((size, digest), []).append(path)
                    except (OSError, PermissionError) as exc:
                        self.append_log(f"Could not read: {path} ({exc})")

            groups = [sorted(paths, key=lambda p: str(p).lower()) for paths in by_hash.values() if len(paths) > 1]
            duplicates_found = sum(len(group) - 1 for group in groups)
            self.after(0, self.duplicates_found_var.set, str(duplicates_found))

            if duplicates_found == 0:
                self.append_log("No duplicate files found.")
                self.after(0, self.finish_scan, 0, 0, delete_duplicates)
                return

            removed = 0
            recovered = 0

            for group_num, group in enumerate(groups, start=1):
                keeper = group[0]
                self.append_log(f"\nGroup {group_num}:")
                self.append_log(f"  KEEP: {keeper}")

                for duplicate in group[1:]:
                    self.append_log(f"  DUP : {duplicate}")
                    if delete_duplicates:
                        try:
                            size = duplicate.stat().st_size
                            duplicate.unlink()
                            removed += 1
                            recovered += size
                            self.append_log("        -> deleted")
                        except (OSError, PermissionError) as exc:
                            self.append_log(f"        -> delete failed: {exc}")

            self.after(0, self.finish_scan, removed, recovered, delete_duplicates)

        except Exception as exc:
            self.append_log(f"Unexpected error: {exc}")
            self.after(0, self.status_var.set, "Error")
            self.after(0, messagebox.showerror, APP_TITLE, f"Unexpected error:\n{exc}")
            self.after(0, self.set_busy, False)

    @staticmethod
    def get_files(root, recursive):
        files = []
        if recursive:
            for current_root, _, filenames in os.walk(root):
                current = Path(current_root)
                for name in filenames:
                    path = current / name
                    if path.is_file():
                        files.append(path)
        else:
            files = [p for p in root.iterdir() if p.is_file()]
        return sorted(files, key=lambda p: str(p).lower())

    @staticmethod
    def sha256_file(path):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                block = handle.read(HASH_CHUNK_SIZE)
                if not block:
                    break
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def human_size(size):
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{int(value)} {unit}" if unit == "B" else f"{value:.2f} {unit}"
            value /= 1024

    def finish_scan(self, removed, recovered, delete_duplicates):
        self.duplicates_removed_var.set(str(removed))
        self.space_recovered_var.set(self.human_size(recovered))
        self.status_var.set("Complete")
        self.set_busy(False)

        if delete_duplicates:
            messagebox.showinfo(
                APP_TITLE,
                f"Scan complete.\n\nTotal files scanned: {self.total_files_var.get()}\n"
                f"Duplicates found: {self.duplicates_found_var.get()}\n"
                f"Duplicates removed: {removed}\n"
                f"Space recovered: {self.human_size(recovered)}"
            )
        else:
            messagebox.showinfo(
                APP_TITLE,
                f"Scan complete.\n\nTotal files scanned: {self.total_files_var.get()}\n"
                f"Duplicates found: {self.duplicates_found_var.get()}\n\nNo files were deleted."
            )


if __name__ == "__main__":
    DuplicateCleanerApp().mainloop()
