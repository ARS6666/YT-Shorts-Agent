# 🚀 TrendHunter AI — YouTube Shorts Automation Studio

<p align="center">
  <strong>Discover. Analyze. Edit. Create.</strong>
  <br />
  An AI-powered workspace for discovering viral content, analyzing streamer clips, and turning videos into short-form content.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-Backend-blue?logo=python" />
  <img src="https://img.shields.io/badge/React-Frontend-61DAFB?logo=react" />
  <img src="https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi" />
  <img src="https://img.shields.io/badge/SQLite-Database-003B57?logo=sqlite" />
  <img src="https://img.shields.io/badge/Status-In%20Development-orange" />
</p>

---

## 📌 Overview

**TrendHunter AI** is a desktop-friendly web application designed to help content creators discover interesting videos, analyze engagement, identify potentially viral moments, and create YouTube Shorts.

Instead of switching between multiple tools, TrendHunter brings several content discovery and editing workflows into one dashboard.

Whether you are a content creator, YouTube automation enthusiast, or developer experimenting with AI-powered media tools, TrendHunter provides a starting point for building a smarter short-form content workflow.

## ✨ Features

### 🔎 Content Discovery
- Collect Twitch clips from registered streamer accounts.
- Collect YouTube channel videos.
- Store discovered content in a centralized database.
- Preview and manage collected clips.
- Filter and sort content by performance.

### 📊 Viral Analysis
- Calculate viral potential scores.
- Track views and engagement metrics.
- Save historical metric snapshots.
- Identify trending clips based on performance changes.
- View analytics and collection statistics.

### 🎬 YouTube Clipper
- Enter a YouTube video URL.
- Retrieve video information.
- Download supported videos.
- Generate word-level transcription.
- Create short-form subtitle content.
- Prepare clips for further editing.

### 📝 AI Subtitles
- Automatic speech transcription.
- Word-level timestamps.
- Animated subtitle generation.
- Customizable subtitle appearance.
- Profanity censorship in subtitle text.

### ⚡ Daily Hunt
- Run a scheduled daily discovery workflow.
- Track the current hunt.
- Review previous hunt sessions.

### 🖥️ Dashboard
- Modern React interface.
- Backend terminal output.
- Clip management.
- Analytics and statistics.
- Integrated editing tools.

> **Note:** Features and platform integrations are actively being developed. Some workflows require API credentials or additional configuration.

---

# 🖥️ Screenshots

Add screenshots of your application here:

| Dashboard | Clip Library |
|---|---|
| `Add dashboard screenshot` | `Add clip library screenshot` |

| YouTube Clipper | Subtitle Editor |
|---|---|
| `Add YouTube clipper screenshot` | `Add editor screenshot` |

---

# 🧰 Requirements

Before installing TrendHunter, make sure you have the following programs.

| Software | Recommended version | Purpose |
|---|---|---|
| Python | 3.12 | Backend |
| Node.js | 22 LTS | Frontend |
| npm | Included with Node.js | Frontend packages |
| FFmpeg | Latest available build | Video and audio processing |
| Git | Latest version | Downloading the project |

You do not need to know Python, React, or backend development to follow the installation instructions.

## 1. Install Python

Download Python:

https://www.python.org/downloads/

During installation on Windows, make sure to enable:

**Add Python to PATH**

After installation, open PowerShell and run:

```powershell
python --version
```

You should see your installed Python version.

## 2. Install Node.js

Download the Node.js LTS version:

https://nodejs.org/

After installation, open PowerShell and run:

```powershell
node --version
npm --version
```

Both commands should display version numbers.

## 3. Install Git

Download Git:

https://git-scm.com/downloads

Verify the installation:

```powershell
git --version
```

## 4. Install FFmpeg

FFmpeg is required for video and audio processing.

Download a Windows build:

https://www.gyan.dev/ffmpeg/builds/

Extract the downloaded archive and add its `bin` folder to your Windows PATH.

For example:

```text
C:\ffmpeg\bin
```

Close and reopen PowerShell, then verify:

```powershell
ffmpeg -version
```

If FFmpeg displays its version information, it is ready.

---

# 🚀 Installation Guide (Windows)

Follow these steps in order.

## Step 1 — Download the project

Open PowerShell.

Navigate to the folder where you want to install TrendHunter:

```powershell
cd $HOME\Desktop
```

Clone the repository:

```powershell
git clone https://github.com/ARS6666/YT-Shorts-Agent.git
```

Enter the project directory:

```powershell
cd YT-Shorts-Agent
```

## Step 2 — Create a Python virtual environment

Run:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate the environment again:

```powershell
.\.venv\Scripts\Activate.ps1
```

You should now see `(.venv)` at the beginning of your terminal line.

## Step 3 — Install backend dependencies

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install the project dependencies:

```powershell
pip install -r requirements.txt
```

Install the additional video downloading and transcription packages:

```powershell
pip install yt-dlp stable-ts
```

Wait until the installation finishes.

## Step 4 — Install frontend dependencies

Open a new PowerShell terminal or use the existing one.

Navigate to the frontend directory:

```powershell
cd frontend
```

Install the required packages:

```powershell
npm install
```

Wait until npm finishes installing the dependencies.

---

# ⚙️ Configuration

TrendHunter can start locally without API credentials, but some external collection features require API keys.

Create a file named `.env` in the main project directory:

```text
YT-Shorts-Agent/
│
├── .env
├── app/
├── assets/
├── frontend/
└── requirements.txt
```

Add the following configuration:

```env
# YouTube Data API
YOUTUBE_API_KEY=

# Twitch Developer Application
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=
```

## YouTube API Setup

To enable YouTube channel collection:

1. Open Google Cloud Console:
   https://console.cloud.google.com/
2. Create or select a Google Cloud project.
3. Enable **YouTube Data API v3**.
4. Create an API key.
5. Copy the key into your `.env` file.

Example:

```env
YOUTUBE_API_KEY=your_youtube_api_key
```

## Twitch API Setup

To enable Twitch clip collection:

1. Visit the Twitch Developer Console:
   https://dev.twitch.tv/console/apps
2. Register an application.
3. Obtain your Client ID and Client Secret.
4. Add them to your `.env` file.

Example:

```env
TWITCH_CLIENT_ID=your_twitch_client_id
TWITCH_CLIENT_SECRET=your_twitch_client_secret
```

**Important:** Never publish your `.env` file or share your API credentials. The repository's `.gitignore` is configured to exclude environment secrets.

---

# ▶️ Running TrendHunter

You need two terminals: one for the backend and one for the frontend.

## Terminal 1 — Start the Backend

Open PowerShell in the main project directory:

```powershell
cd YT-Shorts-Agent
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Start the FastAPI server:

```powershell
uvicorn app.main:app --reload
```

If everything works, the backend will be available at:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

## Terminal 2 — Start the Frontend

Open another PowerShell window:

```powershell
cd YT-Shorts-Agent\frontend
```

Start the React development server:

```powershell
npm run dev
```

You should see a local address similar to:

```text
http://localhost:5173
```

Open that address in your browser.

🎉 **TrendHunter AI is now running!**

---

# 🗂️ Project Structure

```text
YT-Shorts-Agent/
│
├── app/
│   ├── api/
│   │   ├── editor.py
│   │   ├── streamers.py
│   │   └── youtube_clipper.py
│   │
│   ├── collectors/
│   │   ├── twitch.py
│   │   └── youtube.py
│   │
│   ├── models/
│   │
│   ├── services/
│   │   ├── scoring.py
│   │   ├── transcription.py
│   │   ├── subtitles.py
│   │   ├── clip_trends.py
│   │   ├── daily_hunt.py
│   │   └── live_terminal.py
│   │
│   ├── database.py
│   └── main.py
│
├── assets/
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── ...
│   │
│   ├── package.json
│   └── vite.config.js
│
├── data/
│   └── trendhunter.db
│
├── requirements.txt
├── .gitignore
└── README.md
```

The SQLite database is created automatically when the backend starts. You do not need to install or configure a separate database server.

---

# 🛠️ Troubleshooting

### Python is not recognized

Python may not have been added to PATH.

Reinstall Python and enable **Add Python to PATH**, or use the Python Launcher:

```powershell
py -3.12 --version
```

### Cannot activate the virtual environment

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then:

```powershell
.\.venv\Scripts\Activate.ps1
```

### ModuleNotFoundError

Make sure the virtual environment is activated.

Then run:

```powershell
pip install -r requirements.txt
pip install yt-dlp stable-ts
```

### Frontend dependencies are missing

Navigate to the frontend directory:

```powershell
cd frontend
npm install
```

### FFmpeg is not recognized

Make sure the FFmpeg `bin` folder is added to Windows PATH.

Restart PowerShell and check:

```powershell
ffmpeg -version
```

### Port 8000 is already in use

Stop the other process using that port or start the backend on another port:

```powershell
uvicorn app.main:app --reload --port 8001
```

If you change the backend port, update the frontend API configuration accordingly.

### YouTube or Twitch collection is not working

Check the following:

- Your `.env` file is in the project root.
- API credentials are correct.
- The required API is enabled.
- Your internet connection is available.
- Your API quota has not been exceeded.

### First transcription takes a long time

The speech recognition model may need to download its model files the first time it runs. This is normal. Processing time also depends on your CPU and video length.

---

# 🔐 Security

- Never commit API keys or secrets.
- Keep your `.env` file private.
- Do not expose your local backend to public networks without proper security configuration.
- Respect platform terms, copyright rules, and the rights of original content creators.

---

# 🧑‍💻 Contributing

Contributions, suggestions, and bug reports are welcome!

To contribute:

1. Fork this repository.
2. Create a new branch.
3. Make your changes.
4. Test your changes locally.
5. Submit a Pull Request.

---

# 🗺️ Roadmap

Planned improvements include:

- [ ] More advanced viral scoring.
- [ ] Improved trend detection.
- [ ] More content source integrations.
- [ ] Advanced AI-powered clip selection.
- [ ] More subtitle animation presets.
- [ ] Improved automatic short-form editing.
- [ ] Additional export options.
- [ ] More automation workflows.

---

# ⚖️ Disclaimer

TrendHunter AI is a content discovery and editing tool.

Users are responsible for ensuring that they have the necessary rights and permissions to download, edit, publish, or monetize any third-party content.

This project does not guarantee viral performance or monetization.

---

# ⭐ Support the Project

If you find TrendHunter useful, consider giving the repository a star!

**GitHub:** https://github.com/ARS6666/YT-Shorts-Agent

Built with ❤️ by **ARS6666**.
