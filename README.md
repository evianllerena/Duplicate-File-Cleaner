# Duplicate File Cleaner

Small Windows desktop utility for finding and removing exact duplicate files.

## Features

- Browse for a folder
- Optional subfolder scanning
- Scan-only mode
- Scan & Delete Duplicates mode
- Exact duplicate detection using file size plus SHA-256 content hashing
- Keeps one copy from each duplicate group
- Shows total files scanned, duplicates found, duplicates removed, and space recovered
- Activity log of kept and duplicate files

## Windows EXE

GitHub Actions builds a standalone Windows executable automatically on every push to `main`.

To download it:

1. Open the repository's **Actions** tab.
2. Open the latest **Build Windows EXE** run.
3. Download the **Duplicate_File_Cleaner_Windows** artifact.
4. Extract `Duplicate_File_Cleaner.exe` and run it.

## Safety

Use **Scan Only** first if you want to review duplicates before deleting them. The delete mode permanently removes duplicate files after confirmation and keeps one copy of each exact duplicate set.
