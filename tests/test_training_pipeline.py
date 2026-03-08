from pathlib import Path
from dataclasses import asdict
from types import SimpleNamespace

from run_qwen4b_baseline_train import (
    _apply_hf_peft_overrides,
    _apply_unsloth_overrides,
    _assert_training_dependencies,
    build_parser as build_train_parser,
)
from run_qwen4b_baseline_prep import build_parser as build_prep_parser
from run_qwen4b_baseline_pipeline import build_parser as build_pipeline_parser
from run_teacher_sft_split import build_parser as build_split_parser

from acidnet.training.teacher_prompts import TeacherConfig, dialogue_user_prompt, teacher_system_prompt
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


def test_demo_prompt_pack_contains_hard_direct_say_rows() -> None:
    rows = generate_demo_prompt_pack(num_turns=1)
    dialogue_rows = [row for row in rows if row.task == "dialogue"]

    assert any(row.metadata.get("interaction_case") == "base" for row in dialogue_rows)
    assert any(row.metadata.get("interaction_case") != "base" for row in dialogue_rows)
    assert any(row.metadata.get("interaction_mode") == "direct_say" for row in dialogue_rows)


def test_demo_prompt_pack_rotates_vendor_price_direct_rows() -> None:
    rows = generate_demo_prompt_pack(num_turns=6)
    dialogue_rows = [row for row in rows if row.task == "dialogue"]

    assert any(row.metadata.get("interaction_case") == "vendor_price_direct" for row in dialogue_rows)


def test_demo_prompt_pack_rotates_fact_grounded_vendor_trade_rows() -> None:
    rows = generate_demo_prompt_pack(num_turns=20)
    dialogue_rows = [row for row in rows if row.task == "dialogue"]
    cases = {row.metadata.get("interaction_case") for row in dialogue_rows}

    assert "vendor_stock_direct" in cases
    assert "vendor_offer_accept_direct" in cases
    assert "vendor_offer_counter_direct" in cases
    assert "vendor_negative_offer_direct" in cases
    assert "vendor_debt_direct" in cases
    assert "vendor_free_food_direct" in cases
    assert any("'trade_fact': {'kind': 'trade_offer'" in row.user_prompt for row in dialogue_rows)
    assert any("'trade_parse_target': {'kind': 'trade_offer'" in row.user_prompt for row in dialogue_rows)


def test_demo_prompt_pack_always_includes_hunger_direct_rows() -> None:
    rows = generate_demo_prompt_pack(num_turns=1)
    dialogue_rows = [row for row in rows if row.task == "dialogue"]

    assert any(row.metadata.get("interaction_case") == "hunger_direct" for row in dialogue_rows)


def test_demo_prompt_pack_includes_extra_no_food_hunger_rows_for_no_food_vendor() -> None:
    rows = generate_demo_prompt_pack(num_turns=1)
    doran_rows = [row for row in rows if row.task == "dialogue" and row.metadata.get("npc_id") == "npc.doran"]
    interaction_cases = {row.metadata.get("interaction_case") for row in doran_rows}

    assert "hunger_direct" in interaction_cases
    assert "no_food_hunger_spare_direct" in interaction_cases
    assert "no_food_hunger_redirect_direct" in interaction_cases


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


def test_finetune_manifest_uses_bootstrap_teacher_runtime_dialogue_artifacts() -> None:
    dataset = build_finetune_manifest(vram_gb=24)[0].dataset

    assert dataset.prompt_format == "bootstrap_teacher_prompt_pack_v1"
    assert dataset.train_jsonl_path == "data/prompt_packs/bootstrap_teacher_requests.jsonl"
    assert dataset.train_parquet_path == "data/prompt_packs/bootstrap_teacher_requests.parquet"
    assert dataset.merged_sft_jsonl_path == "data/sft/bootstrap_teacher_sft_dataset.jsonl"
    assert dataset.train_sft_jsonl_path == "data/sft/train_bootstrap_teacher_sft_dataset.jsonl"
    assert dataset.eval_sft_jsonl_path == "data/sft/eval_bootstrap_teacher_sft_dataset.jsonl"


def test_baseline_cli_defaults_point_to_bootstrap_teacher_artifacts() -> None:
    train_args = build_train_parser().parse_args([])
    prep_args = build_prep_parser().parse_args([])
    pipeline_args = build_pipeline_parser().parse_args(["--teacher-output", "data/prompt_packs/bootstrap_teacher_outputs.jsonl"])
    split_args = build_split_parser().parse_args([])

    assert Path(train_args.train_dataset).as_posix() == "data/sft/train_bootstrap_teacher_sft_dataset.jsonl"
    assert Path(train_args.eval_dataset).as_posix() == "data/sft/eval_bootstrap_teacher_sft_dataset.jsonl"
    assert Path(prep_args.train_dataset).as_posix() == "data/sft/train_bootstrap_teacher_sft_dataset.jsonl"
    assert Path(prep_args.eval_dataset).as_posix() == "data/sft/eval_bootstrap_teacher_sft_dataset.jsonl"
    assert Path(pipeline_args.prompt_pack).as_posix() == "data/prompt_packs/bootstrap_teacher_requests.jsonl"
    assert Path(pipeline_args.merged_jsonl_output).as_posix() == "data/sft/bootstrap_teacher_sft_dataset.jsonl"
    assert Path(pipeline_args.train_jsonl_output).as_posix() == "data/sft/train_bootstrap_teacher_sft_dataset.jsonl"
    assert Path(pipeline_args.eval_jsonl_output).as_posix() == "data/sft/eval_bootstrap_teacher_sft_dataset.jsonl"
    assert Path(split_args.input).as_posix() == "data/sft/bootstrap_teacher_sft_dataset.jsonl"
    assert Path(split_args.train_output).as_posix() == "data/sft/train_bootstrap_teacher_sft_dataset.jsonl"
    assert Path(split_args.eval_output).as_posix() == "data/sft/eval_bootstrap_teacher_sft_dataset.jsonl"


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
    assert "- mode: trade_request" in examples[0].user_prompt


def test_runtime_dialogue_merge_carries_trade_fact_into_prompt() -> None:
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.mara.vendor_offer_counter_direct",
            "task": "dialogue",
            "system_prompt": "teacher system",
            "user_prompt": """NPC dialogue task.

World sample:
{'world': {'day': 1, 'tick': 0, 'weather': 'clear', 'scarcity_index': 0.4, 'market_prices': {'bread': 5}},
 'location': {'name': 'Market Square'},
 'player': {'hunger': 22.0},
 'npc': {'npc_id': 'npc.mara', 'name': 'Mara', 'profession': 'merchant', 'traits': ['quick'], 'hunger': 18.0,
         'inventory': {'bread': 6, 'fish': 2},
         'buy_options': [{'item': 'bread', 'quantity': 6, 'price': 6}],
         'sell_options': [], 'ask_options': [{'item': 'bread', 'quantity': 1, 'price': None}],
         'give_options': [], 'debt_options': [{'item': 'bread', 'quantity': 3, 'price': 6}],
         'trade_fact': {'kind': 'trade_offer', 'item': 'bread', 'quantity': 1, 'available_quantity': 6,
                        'listed_unit_price': 6, 'debt_unit_price': None, 'offered_total_gold': 3,
                        'minimum_total_gold': 4, 'accepted_total_gold': None, 'counter_total_gold': 4,
                        'error_code': None, 'stock': []},
         'known_rumors': [], 'is_vendor': True},
 'persona': {'speech_style': ['plain'], 'values': ['trade']},
 'interaction_context': {'player_prompt': 'Would you take 3 gold for one bread?', 'player_goal': 'direct_say',
                         'trade_parse_target': {'kind': 'trade_offer', 'item': 'bread', 'quantity': 1, 'offered_total_gold': 3}},
 'beliefs': [], 'recent_memories': [], 'visible_rumors': [], 'relationship_score': 0.0}
""",
            "metadata": {"npc_id": "npc.mara", "scenario_id": "scenario_0000"},
        }
    ]
    teacher_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.mara.vendor_offer_counter_direct",
            "assistant_json": {
                "task": "dialogue",
                "npc_id": "npc.mara",
                "response": "That is too low. For bread x1, I would need 4 gold.",
            },
        }
    ]

    examples = merge_prompt_pack_with_teacher_outputs_runtime_dialogue(prompt_rows, teacher_rows)

    assert len(examples) == 2
    runtime_example = next(example for example in examples if example.task == "dialogue_runtime")
    parser_example = next(example for example in examples if example.task == "trade_parser_runtime")
    assert "Trade Fact Summary:" in runtime_example.user_prompt
    assert "counter_total_gold: 4" in runtime_example.user_prompt
    assert "hidden during exact trade adjudication" in runtime_example.user_prompt
    assert parser_example.messages[-1]["content"] == '{"kind": "trade_offer", "item": "bread", "quantity": 1, "offered_total_gold": 3}'
    assert "strict trade-intent parser" in parser_example.system_prompt
    assert "- buy_options: bread x6 @ 6 gold" in parser_example.user_prompt


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


def test_bootstrap_teacher_answers_origin_question_directly() -> None:
    sample = {
        "world": {"day": 1, "tick": 0, "weather": "clear", "scarcity_index": 0.4, "market_prices": {"bread": 4}},
        "location": {"name": "Warm Crust Bakery"},
        "player": {"hunger": 12.0},
        "npc": {
            "npc_id": "npc.hobb",
            "name": "Hobb",
            "profession": "baker",
            "traits": ["warm"],
            "hunger": 20.0,
            "inventory": {"bread": 3},
            "known_rumors": [],
            "is_vendor": True,
        },
        "persona": {"speech_style": ["plain"], "values": ["craft"]},
        "interaction_context": {
            "player_prompt": "Where did you come from?",
            "player_goal": "direct_say",
            "expected_focus": "Answer directly.",
        },
        "beliefs": [],
        "recent_memories": [],
        "visible_rumors": [],
        "relationship_score": 0.0,
    }
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.hobb.origin_direct",
            "task": "dialogue",
            "system_prompt": teacher_system_prompt(TeacherConfig()),
            "user_prompt": dialogue_user_prompt(sample),
            "metadata": {"npc_id": "npc.hobb", "scenario_id": "scenario_0000"},
        }
    ]

    rows = build_bootstrap_teacher_outputs(prompt_rows, tasks=("dialogue",))

    assert len(rows) == 1
    response = rows[0].assistant_json["response"].lower()
    assert "warm crust bakery" in response or "keep close" in response or "nothing farther" in response


def test_bootstrap_teacher_redirects_hunger_when_npc_has_no_food() -> None:
    sample = {
        "world": {"day": 1, "tick": 0, "weather": "clear", "scarcity_index": 0.4, "market_prices": {"bread": 4, "tool": 15}},
        "location": {"name": "Red Anvil Smithy"},
        "player": {"hunger": 68.0},
        "npc": {
            "npc_id": "npc.doran",
            "name": "Doran",
            "profession": "blacksmith",
            "traits": ["gruff"],
            "hunger": 20.0,
            "inventory": {"tool": 2},
            "known_rumors": ["Bread is getting harder to find by dusk."],
            "is_vendor": True,
        },
        "persona": {"speech_style": ["plain"], "values": ["work"]},
        "interaction_context": {
            "player_prompt": "I am hungry.",
            "player_goal": "direct_say",
            "expected_focus": "Answer directly.",
        },
        "beliefs": [],
        "recent_memories": [],
        "visible_rumors": ["Bread is getting harder to find by dusk."],
        "relationship_score": 0.0,
    }
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.doran.hunger_direct",
            "task": "dialogue",
            "system_prompt": teacher_system_prompt(TeacherConfig()),
            "user_prompt": dialogue_user_prompt(sample),
            "metadata": {"npc_id": "npc.doran", "scenario_id": "scenario_0001"},
        }
    ]

    rows = build_bootstrap_teacher_outputs(prompt_rows, tasks=("dialogue",))

    assert len(rows) == 1
    assert rows[0].assistant_json["response"] == "I do not have food to spare. Try the bakery or the shrine before the square runs thin."


def test_bootstrap_teacher_redirects_food_trade_when_vendor_has_no_edible_goods() -> None:
    sample = {
        "world": {"day": 1, "tick": 0, "weather": "clear", "scarcity_index": 0.4, "market_prices": {"bread": 4, "tool": 15}},
        "location": {"name": "Red Anvil Smithy"},
        "player": {"hunger": 22.0},
        "npc": {
            "npc_id": "npc.doran",
            "name": "Doran",
            "profession": "blacksmith",
            "traits": ["gruff"],
            "hunger": 20.0,
            "inventory": {"tool": 2},
            "known_rumors": [],
            "is_vendor": True,
        },
        "persona": {"speech_style": ["plain"], "values": ["work"]},
        "interaction_context": {
            "player_prompt": "I need food. What can you sell me right now?",
            "player_goal": "trade_request",
            "expected_focus": "Answer directly.",
        },
        "beliefs": [],
        "recent_memories": [],
        "visible_rumors": [],
        "relationship_score": 0.0,
    }
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.doran.trade_request",
            "task": "dialogue",
            "system_prompt": teacher_system_prompt(TeacherConfig()),
            "user_prompt": dialogue_user_prompt(sample),
            "metadata": {"npc_id": "npc.doran", "scenario_id": "scenario_0002"},
        }
    ]

    rows = build_bootstrap_teacher_outputs(prompt_rows, tasks=("dialogue",))

    assert len(rows) == 1
    assert rows[0].assistant_json["response"] == (
        "If it matters, keep it plain. I do not have food to sell from Red Anvil Smithy right now. "
        "Try the bakery or the tavern before the shelves thin further."
    )


def test_bootstrap_teacher_quotes_exact_vendor_price_from_buy_options() -> None:
    sample = {
        "world": {"day": 1, "tick": 0, "weather": "clear", "scarcity_index": 0.4, "market_prices": {"bread": 5}},
        "location": {"name": "Market Square"},
        "player": {"hunger": 22.0},
        "npc": {
            "npc_id": "npc.mara",
            "name": "Mara",
            "profession": "merchant",
            "traits": ["quick"],
            "hunger": 18.0,
            "inventory": {"bread": 6, "fish": 2},
            "buy_options": [{"item": "bread", "quantity": 6, "price": 6}],
            "sell_options": [],
            "ask_options": [],
            "give_options": [],
            "debt_options": [{"item": "bread", "quantity": 6, "price": 6}],
            "trade_fact": {
                "kind": "trade_quote",
                "item": "bread",
                "quantity": 1,
                "available_quantity": 6,
                "listed_unit_price": 6,
                "debt_unit_price": 6,
                "offered_total_gold": None,
                "minimum_total_gold": None,
                "accepted_total_gold": None,
                "counter_total_gold": None,
                "error_code": None,
                "stock": [],
            },
            "known_rumors": [],
            "is_vendor": True,
        },
        "persona": {"speech_style": ["plain"], "values": ["trade"]},
        "interaction_context": {
            "player_prompt": "How much is bread today?",
            "player_goal": "direct_say",
            "expected_focus": "Quote the exact current vendor price for the named item from live trade options.",
        },
        "beliefs": [],
        "recent_memories": [],
        "visible_rumors": [],
        "relationship_score": 0.0,
    }
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.mara.vendor_price_direct",
            "task": "dialogue",
            "system_prompt": teacher_system_prompt(TeacherConfig()),
            "user_prompt": dialogue_user_prompt(sample),
            "metadata": {"npc_id": "npc.mara", "scenario_id": "scenario_0003"},
        }
    ]

    rows = build_bootstrap_teacher_outputs(prompt_rows, tasks=("dialogue",))

    assert len(rows) == 1
    assert rows[0].assistant_json["response"] == "Bread is 6 gold right now. On debt I would call it 6 gold."


def test_bootstrap_teacher_renders_counter_offer_from_trade_fact() -> None:
    sample = {
        "world": {"day": 1, "tick": 0, "weather": "clear", "scarcity_index": 0.4, "market_prices": {"bread": 5}},
        "location": {"name": "Market Square"},
        "player": {"hunger": 22.0},
        "npc": {
            "npc_id": "npc.mara",
            "name": "Mara",
            "profession": "merchant",
            "traits": ["quick"],
            "hunger": 18.0,
            "inventory": {"bread": 6},
            "buy_options": [{"item": "bread", "quantity": 6, "price": 6}],
            "sell_options": [],
            "ask_options": [{"item": "bread", "quantity": 1, "price": None}],
            "give_options": [],
            "debt_options": [{"item": "bread", "quantity": 3, "price": 6}],
            "trade_fact": {
                "kind": "trade_offer",
                "item": "bread",
                "quantity": 1,
                "available_quantity": 6,
                "listed_unit_price": 6,
                "debt_unit_price": None,
                "offered_total_gold": 3,
                "minimum_total_gold": 4,
                "accepted_total_gold": None,
                "counter_total_gold": 4,
                "error_code": None,
                "stock": [],
            },
            "known_rumors": [],
            "is_vendor": True,
        },
        "persona": {"speech_style": ["plain"], "values": ["trade"]},
        "interaction_context": {
            "player_prompt": "Would you take 3 gold for one bread?",
            "player_goal": "direct_say",
            "expected_focus": "Answer from the current counteroffer outcome and keep the exact adjudicated number.",
        },
        "beliefs": [],
        "recent_memories": [],
        "visible_rumors": [],
        "relationship_score": 0.0,
    }
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.mara.vendor_offer_counter_direct",
            "task": "dialogue",
            "system_prompt": teacher_system_prompt(TeacherConfig()),
            "user_prompt": dialogue_user_prompt(sample),
            "metadata": {"npc_id": "npc.mara", "scenario_id": "scenario_0004"},
        }
    ]

    rows = build_bootstrap_teacher_outputs(prompt_rows, tasks=("dialogue",))

    assert len(rows) == 1
    assert rows[0].assistant_json["response"] == "That is too low. For bread x1, I would need 4 gold."


def test_bootstrap_teacher_grounds_free_food_request_in_ask_options() -> None:
    sample = {
        "world": {"day": 1, "tick": 0, "weather": "clear", "scarcity_index": 0.4, "market_prices": {"bread": 5}},
        "location": {"name": "Market Square"},
        "player": {"hunger": 72.0},
        "npc": {
            "npc_id": "npc.mara",
            "name": "Mara",
            "profession": "merchant",
            "traits": ["quick"],
            "hunger": 18.0,
            "inventory": {"bread": 6},
            "buy_options": [{"item": "bread", "quantity": 6, "price": 6}],
            "sell_options": [],
            "ask_options": [{"item": "bread", "quantity": 1, "price": None}],
            "give_options": [],
            "debt_options": [{"item": "bread", "quantity": 3, "price": 6}],
            "known_rumors": [],
            "is_vendor": True,
        },
        "persona": {"speech_style": ["plain"], "values": ["trade"]},
        "interaction_context": {
            "player_prompt": "I am hungry. Can you give me one bread for free?",
            "player_goal": "direct_say",
            "expected_focus": "Ground any free or spare help in the current zero-cash sharing contract instead of drifting into prices.",
        },
        "beliefs": [],
        "recent_memories": [],
        "visible_rumors": [],
        "relationship_score": 0.0,
    }
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.mara.vendor_free_food_direct",
            "task": "dialogue",
            "system_prompt": teacher_system_prompt(TeacherConfig()),
            "user_prompt": dialogue_user_prompt(sample),
            "metadata": {"npc_id": "npc.mara", "scenario_id": "scenario_0005"},
        }
    ]

    rows = build_bootstrap_teacher_outputs(prompt_rows, tasks=("dialogue",))

    assert len(rows) == 1
    assert rows[0].assistant_json["response"] == "I can spare a bread for free, but not more than that."


def test_bootstrap_teacher_grounds_debt_request_in_debt_options() -> None:
    sample = {
        "world": {"day": 1, "tick": 0, "weather": "clear", "scarcity_index": 0.4, "market_prices": {"bread": 5}},
        "location": {"name": "Market Square"},
        "player": {"hunger": 22.0},
        "npc": {
            "npc_id": "npc.mara",
            "name": "Mara",
            "profession": "merchant",
            "traits": ["quick"],
            "hunger": 18.0,
            "inventory": {"bread": 6},
            "buy_options": [{"item": "bread", "quantity": 6, "price": 6}],
            "sell_options": [],
            "ask_options": [{"item": "bread", "quantity": 1, "price": None}],
            "give_options": [],
            "debt_options": [{"item": "bread", "quantity": 3, "price": 6}],
            "known_rumors": [],
            "is_vendor": True,
        },
        "persona": {"speech_style": ["plain"], "values": ["trade"]},
        "interaction_context": {
            "player_prompt": "Could I take one bread on debt?",
            "player_goal": "direct_say",
            "expected_focus": "Answer from the current debt contract instead of guessing from market prices.",
        },
        "beliefs": [],
        "recent_memories": [],
        "visible_rumors": [],
        "relationship_score": 0.0,
    }
    prompt_rows = [
        {
            "custom_id": "dialogue.demo.0.npc.mara.vendor_debt_direct",
            "task": "dialogue",
            "system_prompt": teacher_system_prompt(TeacherConfig()),
            "user_prompt": dialogue_user_prompt(sample),
            "metadata": {"npc_id": "npc.mara", "scenario_id": "scenario_0006"},
        }
    ]

    rows = build_bootstrap_teacher_outputs(prompt_rows, tasks=("dialogue",))

    assert len(rows) == 1
    assert rows[0].assistant_json["response"] == "I can still let bread go on debt for 6 gold."


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
    assert 'processing_class=tokenizer' in script_text
    assert 'dataset_text_field=RUN_SPEC["dataset_text_field"]' in script_text
    assert 'max_length=RUN_SPEC["max_seq_length"]' in script_text
    assert 'eval_strategy="steps"' in script_text


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
    assert run_spec.load_in_4bit is False
    assert run_spec.optimizer == "adamw_torch"
    assert script_path.exists()
    assert "ROOT = _project_root()" in script_text
    assert 'get_peft_model(model, peft_config)' in script_text
    assert "BitsAndBytesConfig" in script_text
    assert "prepare_model_for_kbit_training" in script_text
    assert 'remove_columns=train_raw.column_names' in script_text


def test_low_vram_profile_applies_hf_peft_memory_overrides() -> None:
    baseline = build_finetune_manifest(vram_gb=24)[0]
    run_spec = build_hf_peft_run_spec(
        baseline,
        RunPaths(
            train_dataset_path="data/sft/train_teacher_sft_dataset.jsonl",
            eval_dataset_path="data/sft/eval_teacher_sft_dataset.jsonl",
            output_dir="data/training/qwen3_5_4b_baseline",
        ),
    )
    args = SimpleNamespace(
        memory_profile="low_vram",
        max_seq_length=None,
        batch_size=None,
        grad_accum=None,
        lora_rank=None,
        lora_alpha=None,
        optimizer=None,
        epochs=None,
        eval_steps=None,
        save_steps=None,
        load_in_4bit=False,
    )

    updated = _apply_hf_peft_overrides(run_spec, args)

    assert updated.max_seq_length == 2048
    assert updated.per_device_train_batch_size == 1
    assert updated.gradient_accumulation_steps == 16
    assert updated.lora_rank == 16
    assert updated.lora_alpha == 16
    assert updated.load_in_4bit is True
    assert updated.optimizer == "paged_adamw_8bit"


def test_explicit_hf_peft_schedule_overrides_are_applied() -> None:
    baseline = build_finetune_manifest(vram_gb=24)[0]
    run_spec = build_hf_peft_run_spec(
        baseline,
        RunPaths(
            train_dataset_path="data/sft/train_teacher_sft_dataset.jsonl",
            eval_dataset_path="data/sft/eval_teacher_sft_dataset.jsonl",
            output_dir="data/training/qwen3_5_4b_baseline",
        ),
    )
    args = SimpleNamespace(
        memory_profile="default",
        max_seq_length=None,
        batch_size=None,
        grad_accum=None,
        lora_rank=None,
        lora_alpha=None,
        optimizer=None,
        epochs=1,
        eval_steps=1000,
        save_steps=1200,
        load_in_4bit=False,
    )

    updated = _apply_hf_peft_overrides(run_spec, args)

    assert updated.num_train_epochs == 1
    assert updated.eval_steps == 1000
    assert updated.save_steps == 1200


def test_unsloth_overrides_are_applied() -> None:
    baseline = build_finetune_manifest(vram_gb=24)[0]
    run_spec = build_unsloth_run_spec(
        baseline,
        RunPaths(
            train_dataset_path="data/sft/train_teacher_sft_dataset.jsonl",
            eval_dataset_path="data/sft/eval_teacher_sft_dataset.jsonl",
            output_dir="data/training/qwen3_5_4b_baseline",
        ),
    )
    args = SimpleNamespace(
        memory_profile="default",
        max_seq_length=1024,
        batch_size=2,
        grad_accum=8,
        lora_rank=16,
        lora_alpha=16,
        optimizer=None,
        epochs=1,
        eval_steps=128,
        save_steps=256,
        load_in_4bit=False,
    )

    updated = _apply_unsloth_overrides(run_spec, args)

    assert updated.max_seq_length == 1024
    assert updated.per_device_train_batch_size == 2
    assert updated.gradient_accumulation_steps == 8
    assert updated.lora_rank == 16
    assert updated.lora_alpha == 16
    assert updated.num_train_epochs == 1
    assert updated.eval_steps == 128
    assert updated.save_steps == 256


def test_unsloth_dependency_check_imports_unsloth_before_trl(monkeypatch) -> None:
    imports: list[str] = []

    def fake_import_module(name: str):
        imports.append(name)
        return object()

    monkeypatch.setattr("run_qwen4b_baseline_train.importlib.import_module", fake_import_module)

    _assert_training_dependencies("unsloth")

    assert imports[:3] == ["datasets", "unsloth", "trl"]


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
    assert '"user_prompt": "NPC:' in merged_rows[0]
    assert "mode: trade_request" in merged_rows[0]
