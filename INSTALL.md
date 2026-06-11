# GatekeeperAI — Installation Guide

This guide walks you through setting up GatekeeperAI on your own computer or company server. No prior technical experience is required — just follow each step in order.

---

## What you need before starting

- **A Mac, Windows PC, or Linux server** with at least 4 GB of RAM and 10 GB of free disk space.
- **An internet connection** during the setup (to download the required software).
- **An Anthropic API key** — GatekeeperAI uses Claude AI to analyze code. You can get a key at [console.anthropic.com](https://console.anthropic.com). (You will need to create a free account.)

**Time estimate:** 15–30 minutes for a first-time setup.

---

## Step 1 — Install Docker Desktop

Docker is the software that runs GatekeeperAI behind the scenes. Think of it as a self-contained box that holds everything the app needs so you don't have to install dozens of separate programs.

1. Go to **[docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)** and click the download button for your operating system (Mac, Windows, or Linux).
2. Open the downloaded file and follow the on-screen installer instructions.
3. Once installed, open **Docker Desktop** from your Applications or Start Menu.
4. Wait until the Docker whale icon in your taskbar (bottom-right on Windows, top-right on Mac) stops animating — this means Docker is ready.

> If Docker Desktop asks you to create an account, you can skip that step — an account is not required to run GatekeeperAI.

---

## Step 2 — Download GatekeeperAI

1. Go to **[github.com/jacobthomasmichael/GatekeeperAI](https://github.com/jacobthomasmichael/GatekeeperAI)**.
2. Click the green **Code** button, then click **Download ZIP**.
3. Find the downloaded ZIP file (usually in your Downloads folder) and double-click it to unzip it.
4. Move the unzipped folder somewhere easy to find, like your Desktop or Documents folder.

---

## Step 3 — Create your configuration file

GatekeeperAI needs a configuration file with a few secret values before it can start. This file is called `.env` and lives inside the GatekeeperAI folder.

### Open a Terminal (command prompt)

A terminal is a text-based window where you type commands. Don't worry — you only need it for a few steps.

- **Mac:** Press `Command + Space`, type `Terminal`, and press Enter.
- **Windows:** Press the Windows key, type `PowerShell`, and press Enter.
- **Linux:** Press `Ctrl + Alt + T`.

### Navigate to the GatekeeperAI folder

In the terminal, type the following command and press Enter (replace the path with the actual location of your folder):

```
cd /path/to/GatekeeperAI
```

**Example on Mac:** If you moved the folder to your Desktop:
```
cd ~/Desktop/GatekeeperAI-main
```

**Example on Windows:**
```
cd C:\Users\YourName\Desktop\GatekeeperAI-main
```

### Copy the example configuration file

Run this command to create your configuration file:

**Mac / Linux:**
```
cp .env.example .env
```

**Windows (PowerShell):**
```
Copy-Item .env.example .env
```

---

## Step 4 — Fill in your configuration file

Now you need to open the `.env` file and fill in three required values.

### Open the file in a text editor

**Mac:** In the terminal, type:
```
open -e .env
```

**Windows:** In PowerShell, type:
```
notepad .env
```

The file will open and look something like this:

```
SECRET_KEY=
SECRET_ENCRYPTION_KEY=
ANTHROPIC_API_KEY=
...
```

### Generate your SECRET_KEY and SECRET_ENCRYPTION_KEY

These are long random passwords that GatekeeperAI uses to protect your data. You need to generate two separate ones.

In your terminal, run this command **twice** (once for each key) and copy the output each time:

**Mac / Linux:**
```
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Windows:**
```
python -c "import secrets; print(secrets.token_hex(32))"
```

Each time you run it, you'll get a long string of random letters and numbers — for example:
```
a3f9c12de7b84a1e0c9d5f2b8e6a4c7d3f1e9b2a5c8d4f7e0b3a6c9d2f5e8b1
```

Paste the first output after `SECRET_KEY=` and the second output after `SECRET_ENCRYPTION_KEY=` in your `.env` file.

### Add your Anthropic API key

Log in at [console.anthropic.com](https://console.anthropic.com), go to **API Keys**, and create a new key. Copy it and paste it after `ANTHROPIC_API_KEY=` in your `.env` file.

### Save and close the file

Save the file (`Command+S` on Mac, `Ctrl+S` on Windows) and close the text editor.

---

## Step 5 — Start GatekeeperAI

In your terminal (still in the GatekeeperAI folder), run:

```
docker compose -f infra/docker-compose.yml up --build
```

This command downloads all the required components and starts the application. **The first time you run this, it may take 5–15 minutes** depending on your internet speed. You'll see a lot of text scrolling — that's normal.

The app is ready when you see a line that says something like:
```
frontend  | ▲ Next.js ready on http://0.0.0.0:3000
```

> To stop GatekeeperAI at any time, press `Ctrl + C` in the terminal window.

---

## Step 6 — Complete the setup wizard

1. Open your web browser and go to: **http://localhost:3000**
2. You will be taken to the GatekeeperAI setup wizard automatically.
3. Follow the on-screen steps to:
   - Enter your company name and server address
   - Create your administrator account (this is the main login you'll use)
   - Optionally configure email notifications
4. Click **Finish Setup** when done.

You're now logged in as the administrator. Bookmark **http://localhost:3000** for easy access.

---

## Step 7 — Starting GatekeeperAI in the future

You don't need to go through the setup steps again. The next time you want to run GatekeeperAI:

1. Make sure **Docker Desktop** is open and running.
2. Open your terminal, navigate to the GatekeeperAI folder, and run:

```
docker compose -f infra/docker-compose.yml up
```

(Note: no `--build` needed after the first time, unless you've downloaded an update.)

---

## Troubleshooting

**"Docker is not running"**
Open Docker Desktop and wait for it to fully start before running the compose command.

**"Port 3000 is already in use"**
Another application is using the same port. Try closing other apps, or ask your IT team for help.

**The setup wizard doesn't appear / the page won't load**
The app may still be starting up. Wait a minute and refresh the page.

**"python3: command not found" when generating secret keys**
Try `python` instead of `python3`. If neither works, download Python from [python.org](https://python.org) and re-run the command.

**Forgot your admin password**
Contact your system administrator or re-run the setup by stopping Docker (`Ctrl+C`), resetting the database volume, and restarting.

---

## Hosting on a company server (instead of a personal computer)

If you want GatekeeperAI to be accessible to your whole team rather than just on your laptop, follow Steps 1–6 on a dedicated server and replace `localhost` with that server's IP address or domain name in the `.env` file:

```
APP_BASE_URL=https://your-server-address.com
NEXT_PUBLIC_API_URL=https://your-server-address.com/api/v1
```

Ask your IT team to open ports **3000** (web) and **8000** (API) on the server's firewall.

---

*Questions or issues? Open a support ticket at [github.com/jacobthomasmichael/GatekeeperAI/issues](https://github.com/jacobthomasmichael/GatekeeperAI/issues).*
