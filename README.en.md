# Self-Distill

[中文 README](README.md)

Turn your work traces into a playful, privacy-first self-portrait.

Self-Distill is a Codex skill that reads your own DingTalk workspace signals through `dws`, analyzes expression and collaboration patterns locally, and generates two outputs:

- A long-form self-analysis report with behavioral, expression, SBTI, MBTI, animal, and five-dimension insights.
- A brutalist-anime 4:5 profile card PNG that feels more like a collectible character card than a dashboard.

> Demo cards use fictional English profiles only. They do not contain real user data.

## Example Output

![Four fictional Self-Distill profile cards](examples/cards/demo-grid.png)

Individual examples:

| Figure | Demo profile | When it appears |
|---|---|---|
| Orange Focus | ![Avery North](examples/cards/orange-focus-architect.png) | Long-form thinking, abstract language, work-heavy vocabulary, deep analysis. |
| Green Energy | ![Mira Vale](examples/cards/green-energy-mentor.png) | Positive tone, teaching-style explanations, high-energy group communication. |
| Pink Execution | ![Nova Reed](examples/cards/pink-execution-commander.png) | Daytime execution, clear ownership, core collaboration, project momentum. |
| Blue Scout | ![Kai Signal](examples/cards/blue-scout-signal.png) | Short-loop questions, group-channel scouting, fast response, late incident triage. |

## What It Does

Self-Distill turns ordinary work metadata into an expressive profile:

1. **Collect** your own DingTalk signals through `dws`.
2. **Analyze** expression DNA, active hours, message length, collaboration shape, SBTI style, MBTI dimensions, animal metaphors, and five personality dimensions.
3. **Write** a complete Markdown report.
4. **Render** a 720×900 PNG profile card using HTML/CSS and headless Chrome.
5. **Deliver locally first** to `~/Downloads/`; DingTalk sending is opt-in.

## Privacy Model

Self-Distill is intentionally local-first:

- Raw messages and document text stay in memory and are not written to disk.
- Persistent state is limited to summary data in `data/last_snapshot.json`.
- Reports and PNGs are saved locally by default.
- Sending to DingTalk requires explicit flags and confirmation.
- The distributable package should not include personal `data/last_snapshot.json`.

## Quick Start

Install the folder as a Codex skill:

```bash
mkdir -p ~/.codex/skills
cp -R self-distill-skill ~/.codex/skills/self-distill
```

Restart Codex so the skill is discovered.

Run a local dry run:

```bash
python3 ~/.codex/skills/self-distill/scripts/main.py --days 90 --skip-consent --dry-run
```

Generate a local report and card without sending to DingTalk:

```bash
python3 ~/.codex/skills/self-distill/scripts/main.py --days 90 --skip-consent
```

Optional: send the report document and card back to yourself in DingTalk:

```bash
python3 ~/.codex/skills/self-distill/scripts/main.py --days 90 --skip-consent --send
```

## Natural Language Triggers

Inside Codex, you can ask:

- `自查`
- `蒸馏自己`
- `看看我自己`
- `我是谁`
- `我的野兽派名片`

## Generate the Demo Cards

The demo cards in this README are fictional. Regenerate them with:

```bash
cd ~/.codex/skills/self-distill
python3 scripts/generate_demo_cards.py
```

Outputs:

```text
examples/cards/orange-focus-architect.png
examples/cards/green-energy-mentor.png
examples/cards/pink-execution-commander.png
examples/cards/blue-scout-signal.png
examples/cards/demo-grid.png
```

## 3D Figure Selection

The card does not randomly pick a character. It scores the user's expression and behavior signals against the visual personality of each figure:

| Figure | File | Signal pattern |
|---|---|---|
| Orange Focus | `assets/toonhub-1.png` | Long messages, abstract/system vocabulary, high work-word ratio, deep focus. |
| Green Energy | `assets/toonhub-2.png` | Positive tone, explanatory writing, teaching energy, warm group communication. |
| Pink Execution | `assets/toonhub-3.png` | Stable daytime activity, project ownership, strong core collaboration, launch momentum. |
| Blue Scout | `assets/toonhub-4.png` | Many questions, short replies, group-channel scouting, late rapid-response behavior. |

Implementation lives in:

```text
scripts/render_card.py
  FIGURE_LIBRARY
  select_figure()
```

Tests live in:

```text
scripts/test_render_card_layout.py
```

## Requirements

- macOS with Google Chrome installed at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- Python 3.10+
- `dws` CLI configured for DingTalk collection
- For demo generation only: no DingTalk access is required

## Project Layout

```text
self-distill/
├── SKILL.md
├── README.md
├── README.en.md
├── assets/
│   ├── toonhub-1.png
│   ├── toonhub-2.png
│   ├── toonhub-3.png
│   └── toonhub-4.png
├── examples/
│   └── cards/
├── references/
│   ├── persona-library-spec.md
│   ├── card-style-guide.md
│   └── ...
└── scripts/
    ├── main.py
    ├── analyze.py
    ├── render_card.py
    ├── generate_demo_cards.py
    └── test_render_card_layout.py
```

## Validation

Run the renderer and layout tests:

```bash
cd ~/.codex/skills/self-distill/scripts
python3 -m unittest test_render_card_layout.py -v
python3 -m py_compile render_card.py
```

Expected result:

```text
Ran 10 tests
OK
```

## Design Positioning

Self-Distill is not a personality test and not a corporate KPI dashboard. It is closer to a **work-style mirror**:

- Data-driven enough to feel grounded.
- Visual enough to be shareable.
- Weird enough to be memorable.
- Private enough to be safe by default.
