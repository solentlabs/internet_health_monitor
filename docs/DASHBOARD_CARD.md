# Dashboard Card

The Internet Health card: a Lovelace card IHM ships, so a user adds it
from **Add card**, sets it up in a form, and writes no YAML. It follows
Cable Modem Monitor's card pattern, reusing the design, not the code
([ARCHITECTURE_DECISIONS.md § ADR-002](ARCHITECTURE_DECISIONS.md#adr-002-ihm-stays-a-standalone-integration)).

**Rules:**

- **Python decides, the card renders.** One layout builder serves both
  the card and the `generate_dashboard_card` action.
- **Additive.** No card failure, and no missing frontend, stops
  monitoring or setup.
- **Each measurement shown separately** (ADR-004): entity rows and
  graphs, no score.
- **The card's options are a public contract.** Dashboards store them.

## Files

```text
custom_components/internet_health_monitor/
├── dashboard.py      # options schema and build_card_config(hass, options)
├── services.py       # generate_dashboard_card action
├── services.yaml
└── card/
    ├── __init__.py   # async_register_card(hass): the only entry point
    ├── commands.py   # websocket command
    └── frontend/internet-health-card.js   # card and form, no build step
```

`card/` imports `dashboard.py`; nothing imports `card/`. `async_setup`
calls `async_register_card` once. Removing `card/` and that call removes
the card.

## Options

Same names and defaults in the action, the card's form and the card's
YAML. One schema in `dashboard.py` validates all three.

| Option | Default | Shows |
| -------- | --------- | ------- |
| `include_status` | true | Network Status card: gateway and internet reachable, DNS latency, Refresh diagnostics |
| `include_hops` | true | One card per hop (Gateway, ISP, Hop 3), then an Internet reference card: current latency, jitter and packet loss, and the address (the latency sensor's `hop_ip`, or `reference_ip`) |
| `hop_layout` | `cards` | How `include_hops` shows the path: `cards`, one card per point as above; `table`, one markdown card titled Network path with a row per point (Gateway, ISP, Hop 3, Internet), each with its latency sensor's icon, its latency, jitter and packet loss with their units at each sensor's display precision, and its address (a dash until known). A point appears when its latency sensor exists |
| `include_latency` | true | History graphs: latency for the hops and the internet reference (line "Internet"), and DNS latency on its own (its scale would flatten the hops) |
| `include_jitter` | true | History graph: jitter for the hops and the internet reference |
| `include_packet_loss` | true | History graph: packet loss for the hops and the internet reference |
| `include_speed_test` | true | Entities card: each speed test reading except data used (one test's use says little; usage totals keep the running total), then Last test, the date and time the test ran (the first reading's `tested_at`; a dash before the first test); Run speed test as its own button card, which asks before it starts; the bufferbloat grade gauge, full width, above download and upload gauges side by side; history graph: download and upload. Shown only when a speed test service is chosen |
| `graph_hours` | 24 | Hours each graph shows, 1 to 168 |

Renaming or removing an option breaks saved dashboards: the card must
map the old key, and CHANGELOG.md records it.

## Layout

`build_card_config` returns one `vertical-stack` holding the parts
switched on, in the order of the table above. Entity ids come from the entity registry by unique id, so a
renamed device or entity still resolves (ADR-010). Entities that were
not created (internet reference Off) or that the user disabled
are left out, and a part with no entities is left out.

Errors, raised as translated `ServiceValidationError`:

| Key | When |
| ----- | ------ |
| `not_set_up` | No IHM entry exists |
| `nothing_to_show` | Every part is off or has no entities |

A failed poll is not an error: the layout comes from the registry, and
the entities show their own unavailable state.

The bufferbloat gauges are HA gauge cards from 0 to 100 ms, banded at
Waveform's grade bounds (REFERENCES.md § R3, Core `bufferbloat.py`).
Waveform publishes no colors, only that "Anything worse than a B may
affect video calls, gaming, and other real-time applications", so bands
up to B take the theme's success color and those past it the error
color. Up to B is 60% of the arc, so a healthy line reads as healthy. A
larger value pins the needle at the end; HA picks a band's label from
the real value, not the needle's (frontend `src/components/ha-gauge.ts`,
`_getSegmentLabel`, read 2026-11-20), so the D and F bands, which start
past 100, stay, and the letter is still right.

Run speed test is a `button` card, not a row of the entities card,
with a `confirmation` on its `tap_action`: an entities row's button
presses without the row's confirmation when its own Press is clicked
(Cable Modem Monitor found this; its Restart button is built the same
way). The confirmation says the test fills the connection for about 20
seconds and counts toward the data budget.

The first gauge reads the grade sensor's `latency_increase_ms`, the
larger increase, and its bands carry the grades as labels, which HA
shows in place of the value: the letter, as Waveform grades. The
download and upload gauges carry no labels, since a letter there would
grade each direction; they show their increase in ms. The entities card
lists neither the grade nor the increases, since the gauges show them.
Each gauge sits in a `conditional` card that shows it only while its
entity is neither `unknown` nor `unavailable`: HA's gauge shows an error
for a value that is not a number, which every gauge would show before
the first speed test.

## Action

`internet_health_monitor.generate_dashboard_card` takes the options and
returns `{"yaml": <card>}` (response only), for users who paste YAML
into a dashboard instead of using the card. Registered in `async_setup`.
It is also how a user reorders the card's sections: the card's form has
no reordering, since HA's form selectors cannot reorder a list of
options and a custom editor was cut (ARCHITECTURE_DECISIONS.md §
ADR-011). .github/README.md § Your Own Order or Layout gives the steps, and the
README's card section and the action's description point to them.

## Card

- **Backend.** One read-only websocket command,
  `internet_health_monitor/card_config`, with optional `options`
  validated by the shared schema. It returns `{"card": <dict>}`, or the
  error code `card_unavailable` with the builder's message.
- **Registration.** `async_register_card` registers the command, serves
  `card/frontend/` at `/internet_health_monitor/card`, and loads
  `internet-health-card.js?v=<version>` with `add_extra_js_url` (storage
  and YAML dashboards alike; re-added each start, since HA keeps it in
  memory). Serving and loading are skipped when `frontend` or `http` is
  not loaded. `manifest.json` lists `frontend`, `http` and
  `websocket_api` as `after_dependencies`, so a headless HA still loads
  IHM. Any exception is logged as a warning and never reaches
  `async_setup`. HA's frontend, http and websocket modules are imported
  inside that guard, not at module load, so an HA release that moves
  one skips the card instead of stopping IHM from loading.
- **Definition.** The module defines its element and fills
  `window.customCards` before any `await`: HA waits only two seconds
  for an undefined `custom:` element. It re-checks the element registry
  every 100 ms for 15 s, because the frontend can swap in a scoped
  registry after the module runs (seen by Cable Modem Monitor).
- **Rendering.** Fetches `card_config`, builds the stack with
  `loadCardHelpers().createCardElement`, passes `hass` on every update.
  Re-fetches when its config changes. Loading and errors show as a
  message inside `ha-card`; after a failure it retries no sooner than
  30 s. Nothing throws except `setConfig` on an invalid value.
- **Form.** `getConfigForm` lists every option with its default; HA
  renders it. `getStubConfig` returns `{}`, so defaults are the schema's.

## Verification

In the suite (`tests/components/test_dashboard.py`):

- The layout for each option and monitoring combination, disabled
  entities left out, both errors.
- The action's YAML is the builder's dict.
- The websocket command: result, error, invalid options.
- Registration with and without frontend and http; a registration error
  does not stop setup.
- The form's fields and defaults match the schema.

By hand on the local HA (no JS test tooling, and the module holds no
layout): the card appears in Add card, the form saves and redraws, and
the card renders after a cold restart without a browser reload.
