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

## How To Run

```bash
python run_acidnet_gui.py
```

Or after editable install:

```bash
python -m pip install -e .
acidnet-gui
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
