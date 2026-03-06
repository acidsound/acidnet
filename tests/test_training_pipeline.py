from pathlib import Path

from acidnet.training import (
    RunPaths,
    build_finetune_manifest,
    build_openai_batch_requests,
    build_unsloth_run_spec,
    coerce_sft_examples,
    export_prompt_pack_jsonl,
    export_finetune_manifest_json,
    export_sft_jsonl,
    export_teacher_output_jsonl,
    export_unsloth_training_script,
    generate_demo_prompt_pack,
    generate_synthetic_prompt_pack,
    merge_prompt_pack_with_teacher_outputs,
    normalize_openai_batch_output,
    recommended_experiment_order,
    split_sft_examples,
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


def test_openai_batch_requests_are_built_from_prompt_rows() -> None:
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.neri",
            "system_prompt": "system",
            "user_prompt": "user",
        }
    ]

    requests = build_openai_batch_requests(prompt_rows, model="gpt-5.3", max_output_tokens=256)

    assert len(requests) == 1
    assert requests[0].url == "/v1/responses"
    assert requests[0].body["model"] == "gpt-5.3"


def test_openai_batch_output_can_be_normalized() -> None:
    batch_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.neri",
            "response": {
                "status_code": 200,
                "body": {
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": '{"task":"dialogue","npc_id":"npc.neri","response":"The wind is making everyone tense."}',
                                }
                            ],
                        }
                    ]
                },
            },
        }
    ]

    rows = normalize_openai_batch_output(batch_rows)
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = export_teacher_output_jsonl(artifact_dir / "teacher_outputs_test.jsonl", rows)

    assert len(rows) == 1
    assert rows[0].assistant_json["npc_id"] == "npc.neri"
    assert output_path.exists()


def test_qwen4b_baseline_run_spec_can_render_unsloth_script() -> None:
    baseline = build_finetune_manifest(vram_gb=24)[0]
    run_spec = build_unsloth_run_spec(
        baseline,
        RunPaths(
            train_dataset_path="data/sft/train_teacher_sft_dataset.jsonl",
            eval_dataset_path="data/sft/eval_teacher_sft_dataset.jsonl",
            output_dir="data/training/qwen3_5_4b_baseline",
        ),
    )
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    script_path = export_unsloth_training_script(artifact_dir / "train_qwen3_5_4b_baseline_test.py", run_spec)
    script_text = script_path.read_text(encoding="utf-8")

    assert run_spec.model_name == "Qwen/Qwen3.5-4B-Base"
    assert script_path.exists()
    assert 'optim="adamw_8bit"' in script_text
    assert 'load_in_16bit=RUN_SPEC["bf16"]' in script_text


def test_sft_examples_can_be_split_deterministically() -> None:
    rows = [
        {
            "custom_id": f"dialogue.demo.{index}.npc.neri",
            "task": "dialogue",
            "npc_id": "npc.neri",
            "scenario_id": f"scenario_{index:04d}",
            "system_prompt": "system",
            "user_prompt": "user",
            "assistant_json": {"task": "dialogue", "npc_id": "npc.neri", "response": f"line {index}"},
            "messages": [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
                {"role": "assistant", "content": f'{{"line": {index}}}'},
            ],
        }
        for index in range(20)
    ]

    examples = coerce_sft_examples(rows)
    train_a, eval_a = split_sft_examples(examples, train_rows_target=12, eval_rows_target=4, seed=7)
    train_b, eval_b = split_sft_examples(examples, train_rows_target=12, eval_rows_target=4, seed=7)

    assert [example.custom_id for example in train_a] == [example.custom_id for example in train_b]
    assert [example.custom_id for example in eval_a] == [example.custom_id for example in eval_b]
    assert len(train_a) == 12
    assert len(eval_a) == 4
