# BitTorrent Download Client in Python

A Python-based BitTorrent download client developed as part of a project by Group 10. This client is capable of downloading both single-file and multi-file torrents using peer-to-peer communication and .torrent metadata files.

## 👥 Contributors

- [Dev-Soni-20](https://github.com/Dev-Soni-20)
- [dp1405](https://github.com/dp1405)

---

## 🚀 Features

- Supports both single-file and multi-file torrents.
- Downloads content using the BitTorrent protocol.
- Automatically resumes incomplete downloads using a progress-tracking `.json` file.
- Terminal-based logging for download status and events.
- Modular and extensible code structure.

---

## 🐍 Prerequisites

- **Python Version:** Python 3.10 or later
- Install dependencies via `requirements.txt`

---

## ⚙️ Run Instructions

### Step 1: Navigate to the source directory

---

### Step 2: Install dependencies
`pip install -r requirements.txt`

---

### Step 3: Run the torrent client
Run master.py with two arguments:
- The path to a .torrent file (from torrent_files/)
- The destination folder where the content should be downloaded.
- Example: `python3 master.py ./torrent_files/sample.torrent ~/ReadyMovies/`

---

### Step 4: Interrupt and Resume
- To stop the download midway: press Ctrl + C twice
- To resume in the future: repeat Step 3 with the same arguments

---

### ⚠️ Important Notes
- Do not edit or delete the .json file automatically generated in the destination folder. This file stores progress and is essential for resuming incomplete downloads.
- This client supports both single-file and multi-file torrents.
- Ensure you have a stable internet connection while using the client.

---
