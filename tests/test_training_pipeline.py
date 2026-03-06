from pathlib import Path

from acidnet.training import (
    build_finetune_manifest,
    export_prompt_pack_jsonl,
    export_finetune_manifest_json,
    export_sft_jsonl,
    generate_demo_prompt_pack,
    generate_synthetic_prompt_pack,
    merge_prompt_pack_with_teacher_outputs,
    recommended_experiment_order,
)


def test_24gb_experiment_order_prefers_4b_first() -> None:
    candidates = recommended_experiment_order(24)

    assert candidates[0].key == "qwen3_5_4b"
    assert candidates[1].key == "qwen3_5_9b"


def test_demo_prompt_pack_contains_planner_and_dialogue_rows() -> None:
    rows = generate_demo_prompt_pack(num_turns=1)
    task_names = {row.task for row in rows}

    assert rows
    assert task_names == {"planner", "dialogue"}
    assert all("World sample:" in row.user_prompt for row in rows)


def test_synthetic_prompt_pack_generates_scenario_metadata_and_exports_jsonl() -> None:
    rows = generate_synthetic_prompt_pack(num_scenarios=2, turns_per_scenario=2, seed=11)
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = export_prompt_pack_jsonl(artifact_dir / "teacher_requests_test.jsonl", rows)

    assert rows
    assert all(row.metadata["scenario_id"].startswith("scenario_") for row in rows)
    assert output_path.exists()


def test_finetune_manifest_exports_two_experiments() -> None:
    manifest = build_finetune_manifest(vram_gb=24, train_rows_target=50000, eval_rows_target=4000)
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = export_finetune_manifest_json(artifact_dir / "finetune_manifest_test.json", manifest)

    assert len(manifest) == 2
    assert manifest[0].track == "baseline"
    assert manifest[1].track == "challenger"
    assert output_path.exists()


def test_teacher_outputs_can_be_merged_into_sft_examples() -> None:
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.neri",
            "task": "dialogue",
            "system_prompt": "system",
            "user_prompt": "user",
            "metadata": {"npc_id": "npc.neri", "scenario_id": "scenario_0000"},
        }
    ]
    teacher_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.neri",
            "response_text": '{"task":"dialogue","npc_id":"npc.neri","response":"The wind is making everyone tense."}',
        }
    ]

    examples = merge_prompt_pack_with_teacher_outputs(prompt_rows, teacher_rows)
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = export_sft_jsonl(artifact_dir / "teacher_sft_dataset_test.jsonl", examples)

    assert len(examples) == 1
    assert examples[0].assistant_json["npc_id"] == "npc.neri"
    assert output_path.exists()
