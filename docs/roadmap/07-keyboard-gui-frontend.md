# Keyboard GUI Frontend

## Current Status

Implemented:

- Tk-based map view
- keyboard movement
- NPC selection list
- talk, rumor, buy, eat, and wait actions
- event log panel
- command entry for raw world commands
- shared SQLite persistence with the terminal runtime

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

```bash
python -m pip install -e .
acidnet-gui
```

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
  -Detached
```

Headless monkey run for regression observation:

```bash
python run_monkey_world.py --steps 240 --dialogue-backend heuristic
```

## Controls

- arrow keys or `WASD`: move
- `T`: talk to selected NPC
- `R`: ask selected NPC for rumors
- `B`: buy bread from the selected NPC
- `E`: eat the best food in inventory
- `Space`: wait one turn
- `L`: refresh the current scene
- `Enter` in the command box: run any raw command

## UI Structure

- left: world map with locations, links, and player marker
- right: status, location text, NPC list, rumors, event log
- bottom-right: raw command entry

## Next Work

- attach the future local persona/dialogue model to talk and rumor responses
- add a proper tile renderer if the current node map stops being enough
- add save/load slot handling on top of the SQLite snapshot log
