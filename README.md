# SmartCleaner 🧹⚡

A fast, lag-free, and cross-platform system cleaner built with Python and a modern Tkinter interface. SmartCleaner helps you reclaim disk space by safely removing cache files, system junk, and duplicates without freezing your screen.

## Features

* **🧹 Cache Cleaner:** Scans predefined system and user cache directories (Temp, INetCache, Recent, etc.) to clear out temporary bloat.
* **⚡ System Optimizer:** Identifies the biggest folders, biggest files (over 5MB), and application directories so you can see exactly what is eating up your storage.
* **🗑️ Junk & Duplicates:** Hunts down useless file extensions (`.tmp`, `.bak`, `.old`, etc.) and uses fast MD5 hashing to locate duplicate files across your system.
* **🛡️ Smart & Safe Deletion:** * **Hard Blocks:** Strictly prevents the deletion of critical OS files and protected directories (e.g., `System32`, `kernel`, `vmlinuz`).
    * **System Warnings:** Prompts for confirmation before touching OS-related files (`.dll`, `.sys`, `.kext`).
    * **In-Use Warnings:** Uses `psutil` to detect if a file is currently open in another running application, preventing app crashes.
* **🎨 Modern UI:** A responsive, dark-themed interface built natively with Tkinter. It uses threaded scan engines and queue-draining to ensure the UI never locks up, even when scanning millions of files.
* **💻 Cross-Platform:** Configured with native paths and safety rules for Windows, macOS, and Linux.

## Requirements

* **Python 3.6+**
* **`psutil`** (Optional, but highly recommended)
    * *Why?* SmartCleaner uses `psutil` to display real-time disk storage statistics and to detect files currently in use by other applications to prevent unsafe deletions.

## Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/yourusername/SmartCleaner.git](https://github.com/yourusername/SmartCleaner.git)
   cd SmartCleaner
