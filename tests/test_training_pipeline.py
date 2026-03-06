from pathlib import Path
from dataclasses import asdict

from acidnet.training import (
    baseline_pipeline_artifacts_to_dict,
    build_bootstrap_rejected_outputs,
    build_bootstrap_teacher_outputs,
    build_dialogue_preference_examples,
    build_dpo_run_spec,
    RunPaths,
    build_hf_to_gguf_command,
    build_finetune_manifest,
    build_hf_peft_run_spec,
    build_lora_to_gguf_command,
    build_openai_batch_requests,
    build_quantize_command,
    build_unsloth_run_spec,
    coerce_sft_examples,
    export_dpo_training_script,
    export_prompt_pack_jsonl,
    export_finetune_manifest_json,
    export_hf_peft_training_script,
    export_sft_jsonl,
    export_teacher_output_jsonl,
    export_unsloth_training_script,
    generate_demo_prompt_pack,
    generate_synthetic_prompt_pack,
    merge_prompt_pack_with_teacher_outputs,
    merge_prompt_pack_with_teacher_outputs_runtime_dialogue,
    normalize_openai_batch_output,
    prepare_qwen4b_baseline_artifacts,
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


def test_dialogue_teacher_outputs_can_be_merged_into_runtime_aligned_sft_examples() -> None:
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.hobb",
            "task": "dialogue",
            "system_prompt": "teacher system",
            "user_prompt": """NPC dialogue task.

World sample:
{'world': {'day': 1, 'tick': 0, 'weather': 'dry_wind', 'scarcity_index': 0.9, 'market_prices': {'bread': 4}},
 'location': {'name': 'Warm Crust Bakery'},
 'player': {'hunger': 18.0},
 'npc': {'npc_id': 'npc.hobb', 'name': 'Hobb', 'profession': 'baker', 'traits': ['warm', 'gossipy'], 'hunger': 28.0, 'inventory': {'bread': 3}, 'known_rumors': ['Bread will run short by dusk.']},
 'persona': {'speech_style': ['friendly', 'descriptive'], 'values': ['craft', 'community']},
 'interaction_context': {'player_prompt': 'I need food. What can you sell me right now?', 'player_goal': 'trade_food'},
 'beliefs': ['market:price_rising:0.80'],
 'recent_memories': ['Sold two loaves at dawn.'],
 'visible_rumors': ['Bread will run short by dusk.'],
 'relationship_score': 0.25}
""",
            "metadata": {"npc_id": "npc.hobb", "scenario_id": "scenario_0000"},
        }
    ]
    teacher_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.hobb",
            "assistant_json": {
                "task": "dialogue",
                "npc_id": "npc.hobb",
                "response": "Fresh bread is what I have, and the dry wind is already nudging prices upward.",
            },
        }
    ]

    examples = merge_prompt_pack_with_teacher_outputs_runtime_dialogue(prompt_rows, teacher_rows)

    assert len(examples) == 1
    assert examples[0].task == "dialogue_runtime"
    assert examples[0].messages[-1]["content"].startswith("Fresh bread")
    assert "Output one short in-character reply only." in examples[0].user_prompt


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


def test_bootstrap_teacher_outputs_can_be_generated_from_prompt_rows() -> None:
    prompt_rows = [asdict(row) for row in generate_demo_prompt_pack(num_turns=1) if row.task == "dialogue"][:2]

    rows = build_bootstrap_teacher_outputs(prompt_rows, tasks=("dialogue",))

    assert len(rows) == 2
    assert rows[0].assistant_json["task"] == "dialogue"
    assert rows[0].assistant_json["response"]


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

    assert run_spec.model_name == "Qwen/Qwen3.5-4B"
    assert script_path.exists()
    assert "ROOT = _project_root()" in script_text
    assert 'optim="adamw_8bit"' in script_text
    assert 'load_in_16bit=RUN_SPEC["bf16"]' in script_text


def test_qwen4b_baseline_run_spec_can_render_hf_peft_script() -> None:
    baseline = build_finetune_manifest(vram_gb=24)[0]
    run_spec = build_hf_peft_run_spec(
        baseline,
        RunPaths(
            train_dataset_path="data/sft/train_teacher_sft_dataset.jsonl",
            eval_dataset_path="data/sft/eval_teacher_sft_dataset.jsonl",
            output_dir="data/training/qwen3_5_4b_baseline",
        ),
    )
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    script_path = export_hf_peft_training_script(artifact_dir / "train_qwen3_5_4b_hf_peft_test.py", run_spec)
    script_text = script_path.read_text(encoding="utf-8")

    assert run_spec.model_name == "Qwen/Qwen3.5-4B"
    assert script_path.exists()
    assert "ROOT = _project_root()" in script_text
    assert 'get_peft_model(model, peft_config)' in script_text
    assert 'remove_columns=train_raw.column_names' in script_text


def test_dialogue_preference_examples_can_be_built_from_bootstrap_rows() -> None:
    prompt_rows = [asdict(row) for row in generate_demo_prompt_pack(num_turns=1) if row.task == "dialogue"][:3]
    chosen_rows = [asdict(row) for row in build_bootstrap_teacher_outputs(prompt_rows, tasks=("dialogue",))]
    rejected_rows = build_bootstrap_rejected_outputs(prompt_rows)

    examples = build_dialogue_preference_examples(prompt_rows, chosen_rows, rejected_rows)

    assert examples
    assert all(example.chosen != example.rejected for example in examples)
    assert all(example.chosen_reward["total_score"] > example.rejected_reward["total_score"] for example in examples)


def test_gguf_export_commands_are_rendered_with_expected_arguments() -> None:
    lora_command = build_lora_to_gguf_command(
        adapter_path="data/adapter",
        output_path="data/gguf/adapter.gguf",
        base_model_id="Qwen/Qwen3.5-4B",
        convert_lora_script="tools/llama.cpp/convert_lora_to_gguf.py",
    )
    hf_command = build_hf_to_gguf_command(
        merged_model_dir="data/merged/model",
        output_path="data/gguf/model-f16.gguf",
        convert_hf_script="tools/llama.cpp/convert_hf_to_gguf.py",
    )
    quantize_command = build_quantize_command(
        quantize_binary="tools/llama.cpp/build/bin/llama-quantize.exe",
        source_path="data/gguf/model-f16.gguf",
        output_path="data/gguf/model-q4.gguf",
        quantization="Q4_K_M",
    )

    assert "--base-model-id" in lora_command
    assert "--outfile" in hf_command
    assert quantize_command[-1] == "Q4_K_M"


def test_qwen4b_dialogue_dpo_run_spec_can_render_training_script() -> None:
    baseline = build_finetune_manifest(vram_gb=24)[0]
    run_spec = build_dpo_run_spec(
        baseline,
        train_dataset_path="data/preferences/bootstrap_dialogue_preferences.jsonl",
        eval_dataset_path="data/preferences/bootstrap_dialogue_preferences.jsonl",
        output_dir="data/training/qwen3_5_4b_dialogue_dpo",
        sft_adapter_path="data/training/qwen3_5_4b_baseline",
    )
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    script_path = export_dpo_training_script(artifact_dir / "train_qwen3_5_4b_dialogue_dpo_test.py", run_spec)
    script_text = script_path.read_text(encoding="utf-8")

    assert run_spec.model_name == "Qwen/Qwen3.5-4B"
    assert "DPOTrainer" in script_text
    assert 'RUN_SPEC["sft_adapter_path"]' in script_text


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


def test_qwen4b_baseline_pipeline_prepares_split_and_run_artifacts() -> None:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prompt_pack_path = artifact_dir / "pipeline_teacher_requests.jsonl"
    teacher_output_path = artifact_dir / "pipeline_teacher_outputs.jsonl"

    prompt_pack_path.write_text(
        "\n".join(
            [
                '{"custom_id":"dialogue.demo.0.npc.neri","task":"dialogue","system_prompt":"system","user_prompt":"user","metadata":{"npc_id":"npc.neri","scenario_id":"scenario_0000"}}',
                '{"custom_id":"dialogue.demo.1.npc.mara","task":"dialogue","system_prompt":"system","user_prompt":"user","metadata":{"npc_id":"npc.mara","scenario_id":"scenario_0001"}}',
                '{"custom_id":"planner.demo.2.npc.anik","task":"planner","system_prompt":"system","user_prompt":"user","metadata":{"npc_id":"npc.anik","scenario_id":"scenario_0002"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    teacher_output_path.write_text(
        "\n".join(
            [
                '{"custom_id":"dialogue.demo.0.npc.neri","assistant_json":{"task":"dialogue","npc_id":"npc.neri","response":"line 0"}}',
                '{"custom_id":"dialogue.demo.1.npc.mara","assistant_json":{"task":"dialogue","npc_id":"npc.mara","response":"line 1"}}',
                '{"custom_id":"planner.demo.2.npc.anik","assistant_json":{"task":"planner","npc_id":"npc.anik","intent":"work"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    artifacts = prepare_qwen4b_baseline_artifacts(
        prompt_pack_path=str(prompt_pack_path),
        teacher_output_path=str(teacher_output_path),
        merged_jsonl_path=str(artifact_dir / "pipeline_teacher_sft_dataset.jsonl"),
        merged_parquet_path=str(artifact_dir / "pipeline_teacher_sft_dataset.parquet"),
        train_jsonl_path=str(artifact_dir / "pipeline_train_teacher_sft_dataset.jsonl"),
        train_parquet_path=str(artifact_dir / "pipeline_train_teacher_sft_dataset.parquet"),
        eval_jsonl_path=str(artifact_dir / "pipeline_eval_teacher_sft_dataset.jsonl"),
        eval_parquet_path=str(artifact_dir / "pipeline_eval_teacher_sft_dataset.parquet"),
        training_output_dir=str(artifact_dir / "pipeline_qwen3_5_4b_baseline"),
        run_spec_path=str(artifact_dir / "pipeline_qwen3_5_4b_baseline_run_spec.json"),
        training_script_path=str(artifact_dir / "pipeline_train_qwen3_5_4b_baseline.py"),
        export_format="jsonl",
        trainer_backend="hf_peft",
        train_rows_target=2,
        eval_rows_target=1,
        seed=7,
    )
    artifact_map = baseline_pipeline_artifacts_to_dict(artifacts)

    assert artifacts.train_rows == 2
    assert artifacts.eval_rows == 1
    assert Path(artifacts.merged_jsonl_path).exists()
    assert Path(artifacts.train_jsonl_path).exists()
    assert Path(artifacts.eval_jsonl_path).exists()
    assert Path(artifacts.run_spec_path).exists()
    assert Path(artifacts.training_script_path).exists()
    assert artifact_map["experiment_key"] == "qwen3_5_4b_baseline"
    assert artifact_map["trainer_backend"] == "hf_peft"


def test_qwen4b_baseline_pipeline_supports_runtime_dialogue_variant() -> None:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prompt_pack_path = artifact_dir / "runtime_pipeline_teacher_requests.jsonl"
    teacher_output_path = artifact_dir / "runtime_pipeline_teacher_outputs.jsonl"

    prompt_pack_path.write_text(
        "\n".join(
            [
                """{"custom_id":"dialogue.demo.0.npc.hobb","task":"dialogue","system_prompt":"teacher system","user_prompt":"NPC dialogue task.\\n\\nWorld sample:\\n{'world': {'day': 1, 'tick': 0, 'weather': 'dry_wind', 'scarcity_index': 0.9, 'market_prices': {'bread': 4}}, 'location': {'name': 'Warm Crust Bakery'}, 'player': {'hunger': 18.0}, 'npc': {'npc_id': 'npc.hobb', 'name': 'Hobb', 'profession': 'baker', 'traits': ['warm', 'gossipy'], 'hunger': 28.0, 'inventory': {'bread': 3}, 'known_rumors': ['Bread will run short by dusk.']}, 'persona': {'speech_style': ['friendly', 'descriptive'], 'values': ['craft', 'community']}, 'interaction_context': {'player_prompt': 'I need food. What can you sell me right now?', 'player_goal': 'trade_food'}, 'beliefs': ['market:price_rising:0.80'], 'recent_memories': ['Sold two loaves at dawn.'], 'visible_rumors': ['Bread will run short by dusk.'], 'relationship_score': 0.25}","metadata":{"npc_id":"npc.hobb","scenario_id":"scenario_0000"}}""",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    teacher_output_path.write_text(
        "\n".join(
            [
                '{"custom_id":"dialogue.demo.0.npc.hobb","assistant_json":{"task":"dialogue","npc_id":"npc.hobb","response":"Fresh bread is what I have, and the dry wind is already nudging prices upward."}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    artifacts = prepare_qwen4b_baseline_artifacts(
        prompt_pack_path=str(prompt_pack_path),
        teacher_output_path=str(teacher_output_path),
        merged_jsonl_path=str(artifact_dir / "runtime_pipeline_teacher_sft_dataset.jsonl"),
        merged_parquet_path=str(artifact_dir / "runtime_pipeline_teacher_sft_dataset.parquet"),
        train_jsonl_path=str(artifact_dir / "runtime_pipeline_train_teacher_sft_dataset.jsonl"),
        train_parquet_path=str(artifact_dir / "runtime_pipeline_train_teacher_sft_dataset.parquet"),
        eval_jsonl_path=str(artifact_dir / "runtime_pipeline_eval_teacher_sft_dataset.jsonl"),
        eval_parquet_path=str(artifact_dir / "runtime_pipeline_eval_teacher_sft_dataset.parquet"),
        training_output_dir=str(artifact_dir / "runtime_pipeline_qwen3_5_4b_baseline"),
        run_spec_path=str(artifact_dir / "runtime_pipeline_qwen3_5_4b_baseline_run_spec.json"),
        training_script_path=str(artifact_dir / "runtime_pipeline_train_qwen3_5_4b_baseline.py"),
        export_format="jsonl",
        trainer_backend="hf_peft",
        sft_variant="runtime_dialogue",
        train_rows_target=1,
        eval_rows_target=0,
        seed=7,
    )

    merged_rows = [row for row in (artifact_dir / "runtime_pipeline_teacher_sft_dataset.jsonl").read_text(encoding="utf-8").splitlines() if row]

    assert artifacts.sft_variant == "runtime_dialogue"
    assert artifacts.train_rows == 1
    assert artifacts.eval_rows == 0
    assert len(merged_rows) == 1
    assert '"task": "dialogue_runtime"' in merged_rows[0]
