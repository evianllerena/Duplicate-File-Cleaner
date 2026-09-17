import hashlib
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

APP_TITLE = "Duplicate File Cleaner"
HASH_CHUNK_SIZE = 1024 * 1024


class DuplicateCleanerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x590")
        self.minsize(700, 520)

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
            ttk.Label(stats, textvariable=variable, font=("Segoe UI", 10, "bold")).grid(
                row=row, column=1, sticky="w", padx=(12, 0), pady=3
            )

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
        """Open a folder browser that also displays the files inside each folder."""
        current = self.folder_var.get().strip()
        if current and Path(current).is_dir():
            start = Path(current)
        else:
            documents = Path.home() / "Documents"
            start = documents if documents.is_dir() else Path.home()

        dialog = tk.Toplevel(self)
        dialog.title("Select folder to scan")
        dialog.geometry("820x560")
        dialog.minsize(620, 420)
        dialog.transient(self)
        dialog.grab_set()

        path_var = tk.StringVar(value=str(start))
        current_dir = {"path": start}

        top = ttk.Frame(dialog, padding=(10, 10, 10, 6))
        top.pack(fill="x")

        up_button = ttk.Button(top, text="Up")
        up_button.pack(side="left")

        path_entry = ttk.Entry(top, textvariable=path_var)
        path_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))

        list_frame = ttk.Frame(dialog, padding=(10, 0, 10, 8))
        list_frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(list_frame, columns=("type", "size"), show="tree headings")
        tree.heading("#0", text="Name")
        tree.heading("type", text="Type")
        tree.heading("size", text="Size")
        tree.column("#0", width=470, anchor="w")
        tree.column("type", width=110, anchor="w")
        tree.column("size", width=110, anchor="e")

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        bottom = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        bottom.pack(fill="x")

        selected_label = ttk.Label(bottom, text="Select the folder you want to scan.")
        selected_label.pack(side="left", fill="x", expand=True)

        cancel_button = ttk.Button(bottom, text="Cancel", command=dialog.destroy)
        cancel_button.pack(side="right")

        select_button = ttk.Button(bottom, text="Select Folder")
        select_button.pack(side="right", padx=(0, 8))

        def format_size(size):
            units = ["B", "KB", "MB", "GB", "TB"]
            value = float(size)
            for unit in units:
                if value < 1024 or unit == units[-1]:
                    return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
                value /= 1024

        def load_directory(directory):
            directory = Path(directory)
            if not directory.is_dir():
                return

            current_dir["path"] = directory
            path_var.set(str(directory))
            tree.delete(*tree.get_children())

            try:
                entries = list(os.scandir(directory))
            except OSError as exc:
                messagebox.showerror(APP_TITLE, f"Could not open folder:\n{directory}\n\n{exc}", parent=dialog)
                return

            folders = []
            files = []
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        folders.append(entry)
                    elif entry.is_file(follow_symlinks=True):
                        files.append(entry)
                except OSError:
                    continue

            folders.sort(key=lambda e: e.name.lower())
            files.sort(key=lambda e: e.name.lower())

            for entry in folders:
                tree.insert("", "end", text=entry.name, values=("Folder", ""), tags=("folder",), iid=entry.path)

            for entry in files:
                try:
                    size = format_size(entry.stat(follow_symlinks=True).st_size)
                except OSError:
                    size = ""
                suffix = Path(entry.name).suffix
                file_type = suffix[1:].upper() + " File" if suffix else "File"
                tree.insert("", "end", text=entry.name, values=(file_type, size), tags=("file",), iid=entry.path)

            selected_label.config(text=f"{len(files)} file(s), {len(folders)} folder(s) shown")

        def go_up():
            current = current_dir["path"]
            parent = current.parent
            if parent != current:
                load_directory(parent)

        def open_selected(_event=None):
            selection = tree.selection()
            if not selection:
                return
            selected = Path(selection[0])
            if selected.is_dir():
                load_directory(selected)

        def select_folder():
            selection = tree.selection()
            if selection:
                selected = Path(selection[0])
                chosen = selected if selected.is_dir() else current_dir["path"]
            else:
                chosen = current_dir["path"]

            self.folder_var.set(os.path.normpath(str(chosen)))
            dialog.destroy()

        def path_entered(_event=None):
            entered = Path(path_var.get().strip())
            if entered.is_dir():
                load_directory(entered)

        up_button.config(command=go_up)
        select_button.config(command=select_folder)
        tree.bind("<Double-1>", open_selected)
        path_entry.bind("<Return>", path_entered)

        load_directory(start)
        dialog.wait_window()

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
                "This will permanently delete exact duplicate files.\n\n"
                "One copy of each duplicate set will be kept.\n\nContinue?"
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

        threading.Thread(
            target=self.scan_worker,
            args=(root, self.recursive_var.get(), delete_duplicates),
            daemon=True,
        ).start()

    def scan_worker(self, root, recursive, delete_duplicates):
        try:
            files, scan_errors = self.get_files(root, recursive)
            self.after(0, self.total_files_var.set, str(len(files)))
            self.append_log(f"Files discovered: {len(files)}")

            if scan_errors:
                for item, error in scan_errors[:25]:
                    self.append_log(f"Skipped: {item} ({error})")

            if not files:
                self.append_log("No files were discovered in the selected folder.")
                self.after(0, self.finish_scan, 0, 0, delete_duplicates)
                return

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

            groups = [
                sorted(paths, key=lambda p: str(p).lower())
                for paths in by_hash.values()
                if len(paths) > 1
            ]

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
        """Return every regular file. No file-extension filtering is used."""
        files = []
        errors = []

        def scan_directory(directory):
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        try:
                            if entry.is_file(follow_symlinks=True):
                                files.append(Path(entry.path))
                            elif recursive and entry.is_dir(follow_symlinks=False):
                                scan_directory(Path(entry.path))
                        except (OSError, PermissionError) as exc:
                            errors.append((entry.path, str(exc)))
            except (OSError, PermissionError) as exc:
                errors.append((str(directory), str(exc)))

        scan_directory(root)
        files.sort(key=lambda p: str(p).lower())
        return files, errors

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
                f"Scan complete.\n\n"
                f"Total files scanned: {self.total_files_var.get()}\n"
                f"Duplicates found: {self.duplicates_found_var.get()}\n"
                f"Duplicates removed: {removed}\n"
                f"Space recovered: {self.human_size(recovered)}"
            )
        else:
            messagebox.showinfo(
                APP_TITLE,
                f"Scan complete.\n\n"
                f"Total files scanned: {self.total_files_var.get()}\n"
                f"Duplicates found: {self.duplicates_found_var.get()}\n\n"
                f"No files were deleted."
            )


if __name__ == "__main__":
    DuplicateCleanerApp().mainloop()
