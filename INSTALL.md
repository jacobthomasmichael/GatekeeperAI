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

> **Linux server note:** Run the following after copying so GatekeeperAI can save settings during the setup wizard:
> ```
> chmod a+w .env
> ```
> This is only needed on Linux — Mac and Windows users can skip this step.

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

In your terminal (still in the GatekeeperAI folder), run these two commands:

```
docker compose -f infra/docker-compose.yml pull
docker compose -f infra/docker-compose.yml up -d
```

The first command downloads the pre-built GatekeeperAI images from the internet. **This may take 2–5 minutes** depending on your connection speed. The second command starts everything up in the background.

To check that everything started correctly, run:

```
docker compose -f infra/docker-compose.yml ps
```

All services should show **Up** or **healthy** in the Status column.

> To stop GatekeeperAI at any time, run:
> ```
> docker compose -f infra/docker-compose.yml down
> ```

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

## Step 7 — Submit your first app

There are two ways to submit an app to GatekeeperAI. Most users should start with the ZIP upload — it requires no technical setup at all.

---

### Option A — Upload a ZIP file (recommended for most users)

This is the simplest path. No git, no SSH keys, no terminal required.

1. Log in and click **Submit App** in the dashboard.
2. Give your app a name and description, then click **Create**.
3. On the app card, click **Upload ZIP**.
4. Compress your app folder into a `.zip` file:
   - **Mac:** Right-click your folder → **Compress**
   - **Windows:** Right-click your folder → **Send to → Compressed (zipped) folder**
5. Select the ZIP file. GatekeeperAI will upload it and start the scan automatically.

You'll be taken to the scan progress page — the results are usually ready within a minute.

---

### Option B — Push via Git (for developers)

If you prefer to use git, GatekeeperAI includes a built-in Git server. Pushing to main triggers a scan automatically.

**First, add your SSH public key to the server** (run this on the developer's computer):

```
cat ~/.ssh/id_ed25519.pub
```

If the file doesn't exist, generate one first:

```
ssh-keygen -t ed25519 -C "your.email@example.com"
```

Then add the public key to GatekeeperAI (run this on the server, in the GatekeeperAI folder):

```
echo "ssh-ed25519 AAAA...rest-of-key..." >> infra/authorized_keys
```

**Connect your project:**

The exact git commands — with the real repository URL — are shown in the dashboard under the app card. Choose **New project** or **Existing repo** depending on your situation.

---

### What happens after submission

1. The app code is received by GatekeeperAI.
2. An automatic scan starts within seconds — checking for passwords, exposed data, vulnerable packages, and more.
3. The developer can watch scan progress live in the Dashboard.
4. Approvers are notified once the scan completes and a decision is needed.

---

## Step 8 — Starting GatekeeperAI in the future

You don't need to go through the setup steps again. The next time you want to run GatekeeperAI:

1. Make sure **Docker Desktop** is open and running.
2. Open your terminal, navigate to the GatekeeperAI folder, and run:

```
docker compose -f infra/docker-compose.yml up -d
```

**To update to the latest version**, run `pull` first to download any new images, then restart:

```
docker compose -f infra/docker-compose.yml pull
docker compose -f infra/docker-compose.yml up -d
```

Any SSH keys you added to `infra/authorized_keys` are preserved across restarts.

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
```

Ask your IT team to open ports **3000** (web) and **8000** (API) on the server's firewall.

---

## Hosting in the cloud

Running GatekeeperAI on a cloud server means your whole team can access it from anywhere, and you don't have to leave a computer on at your office. The steps below cover the three most common cloud providers. **You will need a credit card on file with the cloud provider** — the server sizes recommended below cost roughly $30–$60 per month.

For all three options, the process is the same high-level flow:
1. Create a virtual server (they each have a different name for it).
2. Connect to it and install Docker.
3. Follow Steps 2–6 from this guide as if it were a regular computer.

---

### Amazon Web Services (AWS)

**What you're creating:** A virtual server called an **EC2 instance**.

1. Log in to the **[AWS Console](https://console.aws.amazon.com)** and search for **EC2** in the top search bar.
2. Click **Launch Instance**.
3. Give it a name (e.g. `GatekeeperAI`).
4. Under **Application and OS Images**, choose **Ubuntu Server 24.04 LTS** (it will say "Free tier eligible" for small sizes, but choose a larger one for real use).
5. Under **Instance type**, choose **t3.medium** (2 CPUs, 4 GB RAM) — this is the minimum recommended size.
6. Under **Key pair**, click **Create new key pair**, give it a name, and download the file. **Keep this file safe** — it is your password to the server.
7. Under **Network settings**, check the boxes to allow **SSH**, **HTTP**, and **HTTPS** traffic.
8. Click **Launch Instance** and wait about 2 minutes for it to start.
9. Click on your new instance, find the **Public IPv4 address**, and copy it.
10. Connect to the server by opening your terminal and running (replace `your-key.pem` and `1.2.3.4` with your actual file name and IP address):
    ```
    ssh -i your-key.pem ubuntu@1.2.3.4
    ```
11. Once connected, install Docker by running these two commands one at a time:
    ```
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker ubuntu
    ```
12. Log out and log back in (`exit`, then reconnect with the same `ssh` command).
13. Now follow **Steps 2–6** from this guide. When you reach Step 6, open your browser to `http://1.2.3.4:3000` (using your server's IP address instead of `localhost`).
14. Update your `.env` file to use your server's address:
    ```
    APP_BASE_URL=http://1.2.3.4
    ```

> **Tip:** For a permanent web address (like `gatekeeper.yourcompany.com`), ask your IT team to point a domain name at the server's IP address and set up an SSL certificate. AWS also offers this through a service called **Route 53**.

---

### Microsoft Azure

**What you're creating:** A virtual server called a **Virtual Machine (VM)**.

1. Log in to the **[Azure Portal](https://portal.azure.com)** and click **Create a resource**.
2. Search for **Virtual Machine** and click **Create**.
3. Fill in the basics:
   - **Resource group:** Click "Create new" and give it a name (e.g. `gatekeeperai-rg`).
   - **Virtual machine name:** `GatekeeperAI`
   - **Region:** Choose the one closest to your office.
   - **Image:** Select **Ubuntu Server 24.04 LTS**.
   - **Size:** Click "See all sizes" and choose **Standard_B2s** (2 CPUs, 4 GB RAM).
4. Under **Administrator account**, choose **SSH public key**. Azure will generate a key for you — click **Download private key** when prompted and save the file.
5. Under **Inbound port rules**, select **Allow selected ports** and check **SSH (22)**, **HTTP (80)**, and **HTTPS (443)**. Also add a custom rule for port **3000** and **8000**.
6. Click **Review + create**, then **Create**. Wait a few minutes for the VM to deploy.
7. Once deployed, click **Go to resource** and find the **Public IP address**.
8. Connect to the server in your terminal (replace `your-key.pem` and `1.2.3.4`):
    ```
    ssh -i your-key.pem azureuser@1.2.3.4
    ```
9. Install Docker:
    ```
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker azureuser
    ```
10. Log out and back in, then follow **Steps 2–6** from this guide, opening your browser to `http://1.2.3.4:3000`.
11. Update your `.env` file:
    ```
    APP_BASE_URL=http://1.2.3.4
    ```

> **Tip:** For a custom domain name, Azure offers **Azure DNS** and **App Service Managed Certificates** for free SSL. Ask your IT team to configure these after the initial setup is working.

---

### Google Cloud Platform (GCP)

**What you're creating:** A virtual server called a **Compute Engine VM instance**.

1. Log in to the **[Google Cloud Console](https://console.cloud.google.com)** and select or create a project from the top dropdown.
2. In the left menu, go to **Compute Engine → VM instances**.
3. Click **Create Instance**.
4. Configure the instance:
   - **Name:** `gatekeeperai`
   - **Region:** Choose the one closest to your office.
   - **Machine type:** Under "General purpose," choose **e2-medium** (2 CPUs, 4 GB RAM).
   - **Boot disk:** Click **Change**, select **Ubuntu 24.04 LTS**, and set the disk size to at least **20 GB**.
5. Under **Firewall**, check both **Allow HTTP traffic** and **Allow HTTPS traffic**.
6. Click **Create** and wait about a minute.
7. On the VM instances page, click the **SSH** button next to your new instance. A browser-based terminal will open — no key file needed.
8. In that terminal, install Docker:
    ```
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    ```
9. Close the browser terminal, re-open it by clicking **SSH** again, then follow **Steps 2–6** from this guide.
10. Find your server's **External IP** on the VM instances page. Open your browser to `http://your-external-ip:3000`.
11. Update your `.env` file:
    ```
    APP_BASE_URL=http://your-external-ip
    ```
12. To allow ports 3000 and 8000 through the firewall, go to **VPC Network → Firewall** in the left menu, click **Create Firewall Rule**, and add rules for TCP ports **3000** and **8000** with source `0.0.0.0/0`.

> **Tip:** Google Cloud offers free managed SSL certificates through **Google-managed certificates** when paired with a load balancer. Ask your IT team about setting this up once the app is confirmed working.

---

## Setting up a custom domain name

A custom domain (like `gatekeeper.yourcompany.com`) makes the app easier to find and looks more professional than an IP address. It also lets you use HTTPS, which encrypts the connection and removes browser security warnings.

This section walks through the full process — from buying a domain to getting the green padlock in the browser. These steps work on AWS, Azure, GCP, or any other server.

**Time estimate:** 20–40 minutes, plus up to 48 hours for the domain name to fully propagate across the internet (usually much faster — often under an hour).

---

### Part 1 — Get a domain name

If your company already has a domain (e.g. `yourcompany.com`), you can create a **subdomain** like `gatekeeper.yourcompany.com` for free — ask your IT team or whoever manages your company's website to add a DNS record (explained in Part 2).

If you need to register a new domain:

1. Go to a domain registrar such as **[Namecheap](https://www.namecheap.com)**, **[Google Domains](https://domains.google)**, or **[GoDaddy](https://www.godaddy.com)**.
2. Search for the domain name you want.
3. Purchase it (most `.com` domains cost $10–$15 per year).

---

### Part 2 — Point the domain at your server

DNS is the internet's address book — it tells browsers which server to go to when someone types your domain name. You need to add one record called an **A record** that links your domain to your server's IP address.

1. Log in to wherever your domain is registered (Namecheap, GoDaddy, or your cloud provider's DNS panel — see below).
2. Find the **DNS settings** or **DNS Management** section for your domain.
3. Add a new record with these values:

   | Field | Value |
   |---|---|
   | Type | **A** |
   | Name / Host | `@` (means the root domain) or `gatekeeper` (for a subdomain) |
   | Value / Points to | Your server's IP address (e.g. `1.2.3.4`) |
   | TTL | 3600 (or leave as default) |

   **Example:** If your domain is `yourcompany.com` and you want `gatekeeper.yourcompany.com`, set **Name** to `gatekeeper` and **Value** to your server's IP.

4. Save the record. Changes can take a few minutes to a few hours to take effect.

**Finding your DNS settings by cloud provider:**
- **AWS:** Use **Route 53** → Hosted zones → your domain → Create record.
- **Azure:** Use **Azure DNS zones** → your zone → + Record set.
- **GCP:** Use **Cloud DNS** → your zone → Add record set.
- **Domain registrar (Namecheap, GoDaddy, etc.):** Log in to the registrar's website → find "DNS" or "Manage Domain" → Advanced DNS.

To check whether the domain is pointing to your server yet, go to **[whatsmydns.net](https://www.whatsmydns.net)**, type your domain, and see if it shows your server's IP address.

---

### Part 3 — Install a reverse proxy (Nginx)

Right now, GatekeeperAI runs on ports 3000 and 8000. A **reverse proxy** is a small piece of software that sits in front of the app and handles incoming web traffic on the standard ports (80 for HTTP, 443 for HTTPS), then forwards it to the right place. Think of it as a receptionist who directs visitors to the correct room.

Connect to your server via SSH and run:

```
sudo apt update && sudo apt install -y nginx
```

---

### Part 4 — Get a free SSL certificate

SSL is what gives you the `https://` prefix and the padlock icon in the browser. It encrypts data between your users and the server. **Let's Encrypt** provides free, automatically renewing SSL certificates.

On your server, run:

```
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d gatekeeper.yourcompany.com
```

Replace `gatekeeper.yourcompany.com` with your actual domain. Certbot will ask for your email address (for renewal reminders) and whether to redirect HTTP to HTTPS — choose **yes** to the redirect.

> Certbot will fail if the domain isn't pointing to your server yet. Make sure Part 2 is done and the DNS has propagated before running this step.

---

### Part 5 — Configure Nginx to route traffic to GatekeeperAI

Now tell Nginx where to send traffic. On your server, run:

```
sudo nano /etc/nginx/sites-available/gatekeeperai
```

This opens a text editor. Paste in the following, replacing `gatekeeper.yourcompany.com` with your actual domain:

```nginx
server {
    listen 80;
    server_name gatekeeper.yourcompany.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name gatekeeper.yourcompany.com;

    ssl_certificate     /etc/letsencrypt/live/gatekeeper.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gatekeeper.yourcompany.com/privkey.pem;

    # Web app
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Save the file by pressing `Ctrl+O`, then Enter, then `Ctrl+X` to exit.

Now activate the configuration and restart Nginx:

```
sudo ln -s /etc/nginx/sites-available/gatekeeperai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

The second command (`nginx -t`) checks for typos — if it says "syntax is ok," you're good to proceed.

---

### Part 6 — Update GatekeeperAI to use your domain

Open your `.env` file on the server and update this line to use your actual domain:

```
APP_BASE_URL=https://gatekeeper.yourcompany.com
```

Then restart GatekeeperAI:

```
docker compose -f infra/docker-compose.yml pull
docker compose -f infra/docker-compose.yml up -d
```

The `-d` flag runs it in the background so it keeps running after you close the terminal.

---

### Part 7 — Verify everything is working

1. Open your browser and go to `https://gatekeeper.yourcompany.com`.
2. You should see the GatekeeperAI login page with a padlock icon in the browser's address bar.
3. If you see a security warning instead, wait a few more minutes for the SSL certificate to activate and try again.

Your SSL certificate will **automatically renew** every 90 days — Certbot handles this for you with no action required.

---

*Questions or issues? Open a support ticket at [github.com/jacobthomasmichael/GatekeeperAI/issues](https://github.com/jacobthomasmichael/GatekeeperAI/issues).*
