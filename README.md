# 🌌 Antigravity OpenAI API Gateway

A legitimate, high-performance OpenAI-compatible API Gateway that bridges **Google Antigravity** (`agy` CLI) into standard OpenAI v1 endpoints (`/v1/chat/completions`, `/v1/models`).

Designed specifically for users with an active **Google Antigravity Pro** subscription, enabling native use across **Eridanus**, **NextChat**, **Chatbox**, **SillyTavern**, **LibreChat**, **Cline**, and any standard OpenAI SDK client without requiring paid Gemini API keys.

---

## 🛡️ Architecture & Safety: Why Legitimate Subprocess?

Many third-party reverse proxies (such as web token scrapers) attempt to intercept OAuth sessions and make spoofed HTTP requests to Google's internal private backend endpoints (`daily-cloudcode-pa.googleapis.com`). This approach frequently triggers Google's anti-abuse systems due to anomalous TLS/JA3/JA4 fingerprints and missing binary telemetry, putting accounts at risk of bans.

**`antigravity-openai-gateway` takes the legitimate path:**
- **Zero Token Replay / Scraping**: Directly invokes the official Google-signed `agy.exe` executable.
- **Genuine Client Telemetry**: Every request is executed via the authentic Google binary with valid cryptographic signatures and official local credential storage.
- **Zero Account Risk**: Operates fully within Google's supported developer workflow.

---

## ✨ Features

- **OpenAI v1 Protocol Compliance**:
  - `POST /v1/chat/completions` (Non-streaming & Real-time Server-Sent Events / SSE Streaming).
  - `GET /v1/models` and `GET /v1/models/{model_id}`.
  - `GET /health` service monitoring.
- **Model Alias Mapping**:
  - Transparently maps common model names (`gpt-4o`, `gpt-3.5-turbo`, `claude-3-5-sonnet`) to official Antigravity models (`gemini-3.8-flash-low`, `gemini-3.8-flash-medium`, `claude-sonnet-4-6`, `claude-opus-4-6-thinking`).
- **Concurrency & State Protection**:
  - Async semaphore throttling prevents local CLI database lock contention.
  - Automatic retry on transient network EOF or connection drops.
- **Multi-turn Context Preservation**:
  - Automatically reconstructs structured dialogue history and system prompts.

---

## 🚀 Quick Start

### 1. Requirements

- Python 3.10+
- Google Antigravity CLI (`agy.exe`) installed and authenticated (`agy` logged in with your Google Antigravity Pro account).

### 2. Installation

```bash
git clone https://github.com/avilliai/antigravity-openai-gateway.git
cd antigravity-openai-gateway
pip install -r requirements.txt
```

### 3. Launch the Gateway

```bash
# Basic launch
python start_gateway.py --port 8045

# With outbound proxy (e.g. Clash Verge / v2rayN on port 10809)
python start_gateway.py --port 8045 --proxy http://127.0.0.1:10809
```

Terminal output:
```text
==============================================================
   🌌 Antigravity OpenAI API Gateway (Google Antigravity Pro)
==============================================================
 • API Base URL   : http://127.0.0.1:8045/v1
 • Endpoints      : http://127.0.0.1:8045/v1/chat/completions
                    http://127.0.0.1:8045/v1/models
 • Default Model  : gemini-3.8-flash-low
 • Antigravity CLI: C:\Users\Administrator\AppData\Local\agy\bin\agy.exe
 • Outbound Proxy : http://127.0.0.1:10809
 • Max Concurrency: 4
 • Auth Key       : (None / Open)
==============================================================
```

---

## 🌐 Proxy Configuration (Clash Verge / Local Proxy)

`agy` is built as a native Go binary and natively adheres to standard proxy environment variables. You can route its outbound Google API traffic through a local proxy (e.g. Clash Verge, v2rayN on port `10809` or `7890`) in three ways:

### Method 1: Gateway Proxy Option (Recommended)
Set `proxy` in `config.yaml` or launch with `--proxy`:
```bash
python start_gateway.py --proxy http://127.0.0.1:10809
```
The gateway automatically injects `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` into all spawned `agy` subprocesses.

### Method 2: Clash Verge TUN Mode (Zero Configuration)
Open **Clash Verge** -> Enable **TUN 模式 (TUN Mode)**.
TUN Mode captures and routes all Windows system traffic (including CLI subprocesses) through Clash automatically without needing any port or environment variables.

### Method 3: Clash Verge Process & Domain Rules
If you prefer rule-based routing, add the following to your Clash Verge rules:
```yaml
rules:
  # Route agy CLI process directly through proxy
  - PROCESS-NAME,agy.exe,PROXY
  # Route Google Antigravity backend domains
  - DOMAIN-SUFFIX,googleapis.com,PROXY
  - DOMAIN-SUFFIX,google.com,PROXY
  - DOMAIN-SUFFIX,gstatic.com,PROXY
  - DOMAIN-KEYWORD,cloudcode,PROXY
```
*(Replace `PROXY` with your Clash proxy group name, such as `节点选择`)*

### Method 4: System Environment Variables
In PowerShell:
```powershell
$env:HTTP_PROXY = "http://127.0.0.1:10809"
$env:HTTPS_PROXY = "http://127.0.0.1:10809"
```
Or set them permanently in Windows User environment variables:
```powershell
[System.Environment]::SetEnvironmentVariable("HTTP_PROXY", "http://127.0.0.1:10809", "User")
[System.Environment]::SetEnvironmentVariable("HTTPS_PROXY", "http://127.0.0.1:10809", "User")
```

---

## 🔌 Client Integration Examples

### Python (`openai` official SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8045/v1",
    api_key="sk-antigravity-local"  # Any string when gateway auth is open
)

# 1. Non-streaming completion
response = client.chat.completions.create(
    model="gpt-4o",  # Automatically mapped to gemini-3.8-flash-medium
    messages=[
        {"role": "system", "content": "You are a concise AI assistant."},
        {"role": "user", "content": "Explain quantum tunneling in one sentence."}
    ],
    stream=False
)
print("Response:", response.choices[0].message.content)

# 2. Real-time streaming
stream = client.chat.completions.create(
    model="claude-3-5-sonnet",  # Automatically mapped to claude-sonnet-4-6
    messages=[{"role": "user", "content": "Write a haiku about stars."}],
    stream=True
)
for chunk in stream:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)
```

### cURL

```bash
curl http://127.0.0.1:8045/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Eridanus Configuration

In Eridanus config:
```yaml
llm:
  provider: "openai"
  base_url: "http://127.0.0.1:8045/v1"
  api_key: "sk-antigravity-local"
  model: "gpt-4o"
```

---

## ⚙️ Configuration Reference

You can customize runtime settings via `config.yaml` or command line flags:

| Option | Flag | Default | Description |
| :--- | :--- | :--- | :--- |
| `host` | `--host` | `127.0.0.1` | Bind interface |
| `port` | `--port` | `8045` | Bind port |
| `api_key` | `--api-key` | `""` (empty) | Require Bearer auth token if set |
| `cli_command`| `--cli-path` | Auto-detect | Path to `agy.exe` |
| `default_model` | `--model` | `gemini-3.8-flash-low` | Default model |
| `max_concurrency`| - | `2` | Max concurrent CLI turns |
| `timeout` | - | `120.0` | Subprocess timeout (seconds) |

---

## 🧪 Testing

Run unit tests:
```bash
python -m unittest tests/test_gateway.py
```

Run live integration test with installed `agy.exe`:
```bash
python -m unittest tests/test_live_agy.py
```

---

## 📄 License

MIT License.
