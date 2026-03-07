from pathlib import Path

from acidnet.simulator import EventLogFile


def test_event_log_file_writes_plain_text_lines() -> None:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifact_dir / "event_log_test.log"
    if log_path.exists():
        log_path.unlink()

    writer = EventLogFile(log_path)
    try:
        writer.write(kind="world", message="Mara shares a rumor.", day=1, tick=24, payload={"npc": "mara"})
    finally:
        writer.close()

    content = log_path.read_text(encoding="utf-8")
    assert "world" in content
    assert "Mara shares a rumor." in content
    assert "day=1" in content
    assert '"npc": "mara"' in content


def test_event_log_file_flattens_multiline_messages() -> None:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifact_dir / "event_log_multiline_test.log"
    if log_path.exists():
        log_path.unlink()

    writer = EventLogFile(log_path)
    try:
        writer.write(kind="world", message="line one\nline two", day=1, tick=48)
    finally:
        writer.close()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "line one \\n line two" in lines[0]
