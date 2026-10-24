<div align="center">
  <img src="custom_components/jules/brand/logo.png" alt="Google Jules" width="280">
  <h1>Google Jules (for Home Assistant) 🤖</h1>
  <p><strong>A secure, production-grade Home Assistant integration that monitors, dispatches, and controls autonomous AI coding sessions with Google Jules directly from your smart home.</strong></p>

  [![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://hacs.xyz)
  [![Downloads (Current release)](https://img.shields.io/github/downloads/FaserF/ha-jules/latest/jules.zip?label=Downloads%20(Current%20release)&style=for-the-badge)](https://github.com/FaserF/ha-jules/releases)
  [![GitHub Release](https://img.shields.io/github/v/release/FaserF/ha-jules?style=for-the-badge)](https://github.com/FaserF/ha-jules/releases)
  [![License](https://img.shields.io/github/license/FaserF/ha-jules?style=for-the-badge)](LICENSE)
</div>

---

## 🧭 Quick Links

| | | | |
| :--- | :--- | :--- | :--- |
| [✨ Features](#-features) | [📦 Installation](#-installation) | [⚙️ Configuration](#️-configuration) | [🛠️ Options](#️-options-flow) |
| [🤖 Services & Automations](#-services--automations) | [🧑‍💻 Architecture](#-codebase-architecture) | [💖 Credits](#-credits--acknowledgements) | [📄 License](#-license) |

### Why use this integration?
Google Jules is Google Labs' autonomous, asynchronous AI coding agent powered by Gemini models. It works on connected GitHub repositories, investigates issues, develops implementation plans, executes code modifications in secure sandboxes, and opens Pull Requests.

With **ha-jules**, you bring your autonomous coding workflow directly into your Home Assistant smart home dashboard:
- Monitor running coding sessions, pending reviews, and success/failure states in real-time.
- Receive mobile push notifications when Jules opens a Pull Request or requests approval on a plan.
- Dispatch new coding tasks straight from Home Assistant dashboards, voice assistants, or automated triggers.
- Connect either directly to Google Jules Cloud API or via your local **OmniRoute** AI Gateway proxy.

---

## ✨ Features

- **📊 Comprehensive Session & Repository Sensors**:
  - **Total Sessions**: Lifetime session count tracked.
  - **Active Sessions**: Currently planning, queued, or executing coding agents.
  - **Awaiting Approval**: Sessions waiting for human review on their proposed plan.
  - **Completed Sessions**: Successfully finished tasks with opened pull requests.
  - **Failed Sessions**: Sessions that encountered an unrecoverable error.
  - **Connected Repositories**: Number of authorized GitHub sources, with full repository names in attributes.
  - **Latest Session**: Live status (`in_progress`, `completed`, `awaiting_approval`, `idle`) with attributes detailing session ID, prompt, branch, pull request URL, and execution plan.

- **🚦 Real-time Binary Sensors**:
  - **Connected (`connectivity`)**: Verifies continuous API access to the Jules endpoint.
  - **Agent Active (`running`)**: Turns on whenever Jules is actively researching or writing code.
  - **Action Required (`problem`)**: Alerts you immediately if a plan requires approval or an action failed.

- **💬 Voice & Chat Assistant (Assist / `conversation`)**:
  - Full Home Assistant Assist integration powered by Jules & OmniRoute models (`coding-cascade`, `chat-cascade`, `fast-cascade`).
  - Supports intent processing and device control via native Home Assistant LLM tools.
  - Can dispatch autonomous GitHub coding sessions directly via voice command or chat dialog.

- **🧠 AI Task Engine (`ai_task`)**:
  - Dedicated AI Task entity providing smart home reasoning, log analysis, and automated code generation.
  - Exposes performance metrics: latency tracking, execution counters, model used, and last execution timestamp.

- **🎚️ Dynamic Select & Switch Entities**:
  - **Active Model / Cascade Select**: Change active LLM models on-the-fly (`coding-cascade`, `fast-cascade`, `chat-cascade`, `gemini-2.5-pro`, `gemini-2.5-flash`).
  - **Active Target Repository Select**: Pick target GitHub repository dynamically from discovered authorized sources.
  - **Default Branch Select**: Switch base working branch (`main`, `master`, `develop`).
  - **Auto-Approve Plans Switch**: Toggle automatic plan approvals from your dashboard.
  - **Token Compression Switch**: Enable/disable prompt token compression for optimized token usage.

- **🧰 Powerful Smart Home AI Services**:
  - `jules.execute_ai_task`: Execute custom reasoning, code generation, or analysis prompts.
  - `jules.analyze_automation`: Inspect existing automations, diagnose race conditions and bugs, and receive optimized YAML.
  - `jules.suggest_automations`: Scan smart devices in your home and generate 3 tailored YAML automations.
  - `jules.diagnose_logs`: Review recent Home Assistant error logs, diagnose root causes, and get step-by-step fix recommendations.
  - `jules.analyze_camera`: Snapshot security cameras and run computer vision scene analysis.

- **🔍 Diagnostic & Privacy Redaction**:
  - Full Home Assistant UI Diagnostic download support with all API keys, bearer tokens, and secrets automatically redacted.

- **🌍 Localization**:
  - Complete, professional translations in both **English** and **German** (`de`).

---

## 📦 Installation

### HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed.
2. In Home Assistant, open **HACS** > **Integrations** > **Custom repositories** (three dots top right).
3. Add repository URL:
   ```text
   https://github.com/FaserF/ha-jules
   ```
4. Category: **Integration**.
5. Click **Add**, find **Google Jules**, and click **Download**.
6. Restart Home Assistant.

### Manual Installation

1. Download the latest `jules.zip` release from [Releases](https://github.com/FaserF/ha-jules/releases).
2. Extract the `custom_components/jules` folder into your Home Assistant `<config_dir>/custom_components/` directory:
   ```text
   <config_dir>/custom_components/jules/
   ```
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Google Jules**.
3. Fill in the configuration fields:
   - **API Key**: Your Jules API key from `jules.google.com/settings` or your OmniRoute proxy token.
   - **API Base URL**: `https://jules.googleapis.com/v1alpha` (default) or your custom OmniRoute gateway address (e.g. `http://omniroute:20128/v1`).
   - **Default Repository** *(Optional)*: Default GitHub source (e.g. `FaserF/ha-jules`).
   - **Auto-Approve Proposed Plans** *(Optional)*: If checked, automatically approve plans to allow fully autonomous execution.

---

## 🛠️ Options Flow

Click **Configure** on the Jules integration card to adjust settings at any time:
- **Polling Interval**: Update frequency (default: 60 seconds).
- **Auto-Approve Plans**: Toggle automatic plan approval.
- **Default Repository**: Change target repository.
- **Default Branch**: Default git branch (`main`).

---

## 🤖 Services & Automations

### `jules.create_session`
Dispatch a coding task directly to Jules:

```yaml
action: jules.create_session
data:
  prompt: "Investigate and fix the intermittent timeout in the sensor coordinator, add tests."
  source: "FaserF/ha-jules"
  title: "Fix coordinator timeout"
  branch: "main"
  auto_approve: false
```

### `jules.approve_plan`
Approve a pending plan:

```yaml
action: jules.approve_plan
data:
  session_id: "sessions/12345" # Optional; defaults to oldest pending session
```

### `jules.send_message`
Send follow-up guidance:

```yaml
action: jules.send_message
data:
  message: "Also verify that all logging output adheres to Home Assistant standards."
```

### Automation Example: Push Notification on PR Created

```yaml
alias: "Jules: Notify when PR is ready"
trigger:
  - platform: event
    event_type: jules_session_completed
action:
  - action: notify.notify
    data:
      title: "🤖 Jules created a PR!"
      message: "Task '{{ trigger.event.data.title }}' is finished. PR: {{ trigger.event.data.pr_url }}"
```

---

## 💖 Support This Project

> I maintain this integration in my **free time alongside my regular job**.
>
> **This project is and will always remain 100% free and open-source.**
>
> Donations are completely voluntary — but they help me stay motivated and dedicate more time to maintaining open-source tools!

<div align="center">

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor%20on-GitHub-%23EA4AAA?style=for-the-badge&logo=github-sponsors&logoColor=white)](https://github.com/sponsors/FaserF)&nbsp;&nbsp;
[![PayPal](https://img.shields.io/badge/Donate%20via-PayPal-%2300457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/FaserF)

</div>

---


## 🔌 Recommended Hardware & Ecosystem Links

| Device / Service | Integration Use Case | Link |
| :--- | :--- | :--- |
| **Home Assistant Green & Offizielle Smart-Home-Hardware** | Empfohlene Hardware-Basis für lokale Home Assistant Integrationen | [Offizielle Geräte-Seite →](https://fabiseitz.de/go/ha-hardware) |
| **Home Assistant Connect ZBT-1 (Zigbee / Thread)** | Lokales Zigbee2MQTT, ZHA & Matter-over-Thread Funknetz | [Offizielle Geräte-Seite →](https://fabiseitz.de/go/ha-zigbee) |

---

## 📄 License

This project is licensed under the Apache-2.0 License - see the [LICENSE](LICENSE) file for details.
