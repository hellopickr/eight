# Eight

A free, private budgeting app. Tell Eight your income, savings goal and fixed bills, and it shows what you've spent and what's still free to spend until payday.

- **Use it on the web:** https://hellopickr.github.io/eight/
- Everything is stored on the person's own device. There are no accounts, no servers and no tracking.

## What's in this repository

| Path | What it is |
| --- | --- |
| `docs/` | The app itself. GitHub Pages publishes this folder as the website. |
| `docs/index.html` | The whole app in one file. |
| `docs/sw.js` | Lets the website work offline. |
| `resources/icon.png` | The 1024×1024 app icon (two coins forming an 8). |
| `capacitor.config.json`, `package.json` | Settings that turn the website into an iPhone app. |
| `codemagic.yaml` | Instructions Codemagic follows to build the iPhone app and send it to TestFlight. |

## Back tap

- **Website:** an iOS Shortcut with the action *Open URLs* → `https://hellopickr.github.io/eight/#add`
- **iPhone app:** an iOS Shortcut with the action *Open URLs* → `eight://add`

Assign the shortcut in Settings › Accessibility › Touch › Back Tap.

## Updating the app

1. Edit `docs/index.html` and commit. The website updates within a minute or two.
2. For the App Store version, start a new build of the **Eight iOS release** workflow in Codemagic.
