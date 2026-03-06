# SmartCleaner 🧹⚡

> ⚠️ **ALERT:** Please check if all the files you delete are no longer required. Even when the app has safety blocks in place, it is still your responsibility to ensure the files are safe to delete!

**SmartCleaner** is a fast, lag-free, and cross-platform system cleaner built entirely in Python with a modern Tkinter interface. It helps you reclaim disk space by safely removing cache files, system junk, and duplicates without freezing your screen or requiring heavy external dependencies.

**Repository:** [Smart_cleaner-for-pc-using-python](https://github.com/Varadkulkarni2002/Smart_cleaner-for-pc-using-python)

---

## ✨ Features

* **🧹 Cache Cleaner:** Scans system and user cache directories (Temp, INetCache, Recent, etc.) to clear out temporary bloat.
* **⚡ System Optimizer:** Identifies the biggest folders, massive files (over 5MB), and application directories to show you exactly what is eating up your storage.
* **🗑️ Junk & Duplicates:** Hunts down useless file extensions (`.tmp`, `.bak`, `.old`, etc.) and uses fast MD5 hashing to locate duplicate files accurately.
* **🛡️ Smart & Safe Deletion:** * **Hard Blocks:** Strictly prevents the deletion of critical OS files and protected directories (e.g., `System32`, `kernel`, `vmlinuz`).
    * **System Warnings:** Prompts for confirmation before touching OS-related files (`.dll`, `.sys`, `.kext`).
    * **In-Use Warnings:** Uses `psutil` to detect if a file is currently open in another running application, preventing app crashes.
* **🎨 Modern UI:** A responsive, dark-themed interface. It uses threaded scan engines and queue-draining to ensure the UI never locks up, even when scanning millions of files.

---



✅ What To Do
Do review the scan results: Always sort and check the files populated in the lists (especially in the "Biggest Files" and "Junk Files" tabs) before hitting delete.

Do use the psutil dependency: It enables the app to read your active disk storage metrics and protects files that are currently open in other applications.

Do pay attention to warnings: If the app prompts you with a system file warning (⚠️) or an in-use warning (🔒), read the file paths carefully before forcing a deletion.

❌ What Not To Do
Do not blindly "Select All" and delete: Especially in the System Optimizer tab! This tab highlights large files which may include important personal media, documents, or virtual machine drives that you actually want to keep.

Do not force-delete in-use files: If an app warns you a file is currently open (🔒), force-deleting it can crash the parent application or corrupt its data.

Do not ignore system warnings: Bypassing the system warning (⚠️) for .dll, .sys, or .kext files can lead to a broken operating system.



⚠️ ALERT: Please double-check if all the files you delete are no longer required. Even when the app has safety blocks in place, careless deletion can cause irreversible data loss. Proceed with caution!


## 🚀 How to Download and Run

### 1. Clone the Repository
Open your terminal or command prompt and run:
```bash
git clone [https://github.com/Varadkulkarni2002/Smart_cleaner-for-pc-using-python.git](https://github.com/Varadkulkarni2002/Smart_cleaner-for-pc-using-python.git)
cd Smart_cleaner-for-pc-using-python



