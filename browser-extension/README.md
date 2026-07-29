# GankAIGC Zhuque Browser Agent

Chrome extension for VPS deployments where Zhuque detects/fights server-side headless browsers. Current recommended unpacked-extension version: `0.1.10`. Local desktop/source deployments can keep `ZHUQUE_DETECT_TRANSPORT=auto` or `local_browser` and do not need this extension.

## Purpose

When GankAIGC runs on a VPS, Zhuque detection should execute in the user's local Chrome instead of the VPS Chromium process.

Flow:

```text
GankAIGC VPS creates Zhuque browser-agent job
↓
Chrome extension claims job
↓
Extension opens/reuses https://matrix.tencent.com/ai-detect/
↓
User's local Chrome session/IP/login state performs Zhuque detection
↓
Extension returns result to VPS
```

## Backend configuration

On the VPS, use browser-agent mode and disable server-headless fallback:

```env
ZHUQUE_DETECT_TRANSPORT=browser_agent
ZHUQUE_SERVER_HEADLESS_FALLBACK=false
ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT=900
ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT=120
ZHUQUE_BROWSER_AGENT_PAIRING_TTL_SECONDS=600
ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS=25
INLINE_TASK_WORKER_ENABLED=false
```

The VPS must be reachable by the user's Chrome browser over HTTPS or trusted HTTP during local testing. `.env.docker` is a private runtime file and is not overwritten by `git pull`; after upgrades, verify the heartbeat timeout is still `120` seconds.

## Load unpacked extension

1. Prefer the matching GitHub Release asset: `GankAIGC-Browser-Extension-v0.1.10.zip` plus `GankAIGC-Browser-Extension-v0.1.10.zip.sha256`. Source users may instead use this `browser-extension/` directory.
2. Verify the ZIP (`sha256sum -c GankAIGC-Browser-Extension-v0.1.10.zip.sha256`, or compare Windows `Get-FileHash` output), then extract it. The selected directory must contain `manifest.json` at its root.
3. Open Chrome: `chrome://extensions`.
4. Enable `Developer mode`.
5. Click `Load unpacked` and select the extracted directory.
6. If the extension was already installed, replace the files in its existing directory, click `Reload`, refresh the open Zhuque page, and confirm the version is `0.1.10` or newer. Do not load a duplicate copy.

## Host permissions

MVP manifest includes:

```json
"host_permissions": [
  "https://matrix.tencent.com/*",
  "https://ga.mumubuku.top/*",
  "http://127.0.0.1:9800/*",
  "http://localhost:9800/*"
]
```

For another real VPS domain, add your GankAIGC origin before loading the extension, for example:

```json
"https://gankaigc.example.com/*"
```

Do not add `<all_urls>`. Do not expose Chrome DevTools Protocol to the public internet and do not ask users to run Chrome with `--remote-debugging-port`; the extension communicates with GankAIGC over normal HTTPS API calls.

## Pairing

1. In GankAIGC workspace, generate a browser-agent pairing code.
2. Open the extension popup.
3. Enter:
   - GankAIGC server URL. The popup defaults to `https://ga.mumubuku.top`.
   - Pairing code, e.g. `GANK-7K29`.
   - Device name.
4. Click `配对插件`.

The popup saves the server URL, pairing-code draft, and device name while typing so the values survive closing/reopening the popup. The extension stores only the server URL, agent id, agent token, device name, and pairing draft in `chrome.storage.local`.

`插件在线` only means the extension is paired and heartbeating; it does not guarantee Zhuque is logged in. Use the workspace button to open the local Zhuque page, log in or pass CAPTCHA there, then refresh/sync status in the workspace.

## Runtime

- Keep Chrome open while VPS tasks run.
- The workspace status should show `插件在线` before starting `AI检测 + 降重`.
- The extension heartbeats compact Zhuque page login state back to GankAIGC so the workspace can show `朱雀账号` / `剩余次数` separately from `插件在线`.
- Version `0.1.9` keeps the `0.1.8` guest/single-click safeguards and also parses result pages where Zhuque omits the zero-valued suspicious class and renders only human + AI percentages.
- Version `0.1.10` uses Chrome-supported 30-second MV3 alarms and performs an immediate job claim after install, reload, and browser startup. Earlier sub-30-second alarm values could fail creation, leaving the extension visibly paired but never polling detection jobs.
- The extension opens or reuses one Zhuque tab in the user's local Chrome.
- Log in to Zhuque in the local Chrome tab when prompted.
- If CAPTCHA appears, complete it in the local Zhuque tab; the backend will keep waiting until the job completes or times out.

## Current MVP limitations

- Developer-mode/unpacked extension only.
- One recent online agent is selected by backend.
- DOM/network extraction is best-effort and may need adjustments if Zhuque changes page structure.
- Official Chrome Web Store packaging is out of scope for the MVP.
