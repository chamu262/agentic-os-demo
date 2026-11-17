# `demo_data/` — made-up data

Fake inputs so the app runs with no real systems and no credentials. All names are invented
(`DEMO-LT-1001`, `user01@example.com`, `portal.example.test`). Dates are written relative to the
app's demo day, 16 Nov 2026, so the results look the same every time.

| File | Read by | Contents |
|---|---|---|
| `devices.json` | Stale device report | 40 laptops/desktops with an owner, operating system and the date they last checked in. |
| `licences.json` | Licence usage check | 5 software products with seats bought, seats assigned and seats used in the last 30 days. |
| `certificates.json` | Certificate expiry watch | 8 website certificates (the padlock in a browser) and the date each one expires. |

To try your own scenario, edit these files and restart the app.
