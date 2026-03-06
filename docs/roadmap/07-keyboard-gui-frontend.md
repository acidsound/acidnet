# Keyboard GUI Frontend

## Current Status

Status note:

- this document is now historical reference only
- the Tk frontend has been removed from the active runtime surface
- new simulation-facing work should target the terminal/raw-command flow and the shareable web probe first

Implemented:

- Tk-based map view
- keyboard movement
- click-to-move for directly adjacent map nodes
- player work action for earning gold or gathering food
- NPC selection list
- explicit selected-target panel for the NPC list
- talk, inspect, direct-speech, rumor, dynamic trade, eat, and wait actions
- in-GUI monkey toggle for observation runs
- event log panel
- dedicated direct-speech input for the selected NPC
- target-aware raw commands with `focus`, `inspect`, and optional-NPC `trade`
- command entry for raw world commands
- shared SQLite persistence with the terminal runtime
- `Settings` modal for viewing and editing the global dialogue system prompt
- DB-backed prompt storage with a read-only `prompt_presets` table and editable `runtime_settings`

Entry point:

- `run_acidnet_gui.py`
- `run_dev_world.ps1`
- `run_monkey_world.py`
- `run_tail_event_log.ps1`

## How To Run

```bash
python run_acidnet_gui.py
```

Or after editable install:

The old `acidnet-gui` entry point has been removed.

Observation-first development launcher:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 -Detached
```

The dev launcher now enables GUI monkey mode by default, so the world keeps moving even without manual input.

Tail the plain-text event log in a separate window:

```powershell
powershell -ExecutionPolicy Bypass -File run_tail_event_log.ps1 -Path data/logs/dev-world.log
```

Launch GUI and tail together:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 -Detached -TailLog
```

Prompt-only local model observation:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 `
  -DialogueBackend openai_compat `
  -DialogueModel qwen3.5-4b `
  -DialogueEndpoint http://127.0.0.1:8000/v1/chat/completions `
  -RunPromptOnlyEval `
  -RunModelGate `
  -Detached
```

Direct local adapter observation without an HTTP bridge:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 `
  -DialogueBackend local_peft `
  -DialogueModel Qwen/Qwen3.5-4B `
  -DialogueAdapterPath data/training/qwen3_5_4b_runtime_dialogue_full_adapter `
  -RunModelGate `
  -Detached
```

Headless monkey run for regression observation:

```bash
python run_monkey_world.py --steps 240 --dialogue-backend heuristic
```

## Controls

- arrow keys or `WASD`: move
- click an adjacent map node: move directly to that location
- click an NPC in the list: set the current interaction target
- `T`: talk to selected NPC
- `I`: inspect selected NPC
- `Y`: focus the direct-speech box for the selected NPC
- `R`: ask selected NPC for rumors
- `X`: do local work at the current location
- `B`: run the current trade from the trade controls
- `E`: eat the best food in inventory
- `M`: toggle monkey mode on or off
- `Space`: wait one turn
- `L`: refresh the current scene/location text
- `Settings` button in the `Dialogue` panel: open the system-prompt modal
- `Enter` in the direct-speech box: send `say <npc> <message>`
- `Enter` in the command box: run any raw command
- `Run (Enter)` button: submit the raw command entry

## UI Structure

- left: world map with locations, links, player marker, rumors, and event log
- right: status, dialogue state, location text, NPC list, target detail panel, action buttons, trade controls, direct-speech input, raw command input
- dialogue status section includes model readiness plus a `Settings` button for the shared system prompt
- the trade section now switches between `buy` and `sell`, lists only valid items, and shows the current price/quantity summary for the selected target

## Next Work

- expand the dialogue transcript UX once multi-turn conversations need more than the event log
- add save/load slot handling on top of the SQLite snapshot log
- add a proper tile renderer if the current node map stops being enough
