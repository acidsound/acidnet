from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from acidnet.training.finetune_manifest import FineTuneExperiment


@dataclass(frozen=True, slots=True)
class RunPaths:
    train_dataset_path: str
    eval_dataset_path: str
    output_dir: str


@dataclass(frozen=True, slots=True)
class UnslothRunSpec:
    experiment_key: str
    model_name: str
    output_dir: str
    dataset_text_field: str
    max_seq_length: int
    learning_rate: float
    per_device_train_batch_size: int
    gradient_accumulation_steps: int
    num_train_epochs: int
    warmup_ratio: float
    eval_steps: int
    save_steps: int
    lora_rank: int
    lora_alpha: int
    bf16: bool
    train_dataset_path: str
    eval_dataset_path: str


def build_unsloth_run_spec(experiment: FineTuneExperiment, paths: RunPaths) -> UnslothRunSpec:
    return UnslothRunSpec(
        experiment_key=experiment.key,
        model_name=experiment.train_model_id,
        output_dir=paths.output_dir,
        dataset_text_field="messages",
        max_seq_length=experiment.max_seq_length,
        learning_rate=experiment.learning_rate,
        per_device_train_batch_size=experiment.per_device_batch_size,
        gradient_accumulation_steps=experiment.gradient_accumulation_steps,
        num_train_epochs=experiment.num_epochs,
        warmup_ratio=experiment.warmup_ratio,
        eval_steps=experiment.eval_steps,
        save_steps=experiment.save_steps,
        lora_rank=experiment.lora_rank,
        lora_alpha=experiment.lora_alpha,
        bf16=experiment.precision == "bf16",
        train_dataset_path=paths.train_dataset_path,
        eval_dataset_path=paths.eval_dataset_path,
    )


def export_unsloth_run_spec(path: str | Path, run_spec: UnslothRunSpec) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(run_spec), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def render_unsloth_training_script(run_spec: UnslothRunSpec) -> str:
    spec_repr = repr(asdict(run_spec))
    return f"""from __future__ import annotations

import json
import sys
from pathlib import Path


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "src").exists():
            return candidate
    return here.parent


ROOT = _project_root()
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from datasets import load_dataset
from trl import SFTConfig, SFTTrainer
from unsloth import FastLanguageModel

RUN_SPEC = {spec_repr}


def format_record(record, tokenizer):
    messages = json.loads(record["messages"]) if isinstance(record["messages"], str) else record["messages"]
    if hasattr(tokenizer, "apply_chat_template"):
        try:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
                enable_thinking=False,
            )
            return {{"text": text}}
        except Exception:
            pass
    return {{"text": "\\n".join(f"{{item['role']}}: {{item['content']}}" for item in messages)}}


def main() -> None:
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=RUN_SPEC["model_name"],
        max_seq_length=RUN_SPEC["max_seq_length"],
        dtype=None,
        load_in_16bit=RUN_SPEC["bf16"],
        load_in_4bit=False,
        full_finetuning=False,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=RUN_SPEC["lora_rank"],
        lora_alpha=RUN_SPEC["lora_alpha"],
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",
    )

    train_dataset = load_dataset("json", data_files=RUN_SPEC["train_dataset_path"], split="train").map(
        lambda record: format_record(record, tokenizer)
    )
    eval_dataset = load_dataset("json", data_files=RUN_SPEC["eval_dataset_path"], split="train").map(
        lambda record: format_record(record, tokenizer)
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        dataset_text_field="text",
        args=SFTConfig(
            output_dir=RUN_SPEC["output_dir"],
            max_seq_length=RUN_SPEC["max_seq_length"],
            learning_rate=RUN_SPEC["learning_rate"],
            per_device_train_batch_size=RUN_SPEC["per_device_train_batch_size"],
            gradient_accumulation_steps=RUN_SPEC["gradient_accumulation_steps"],
            num_train_epochs=RUN_SPEC["num_train_epochs"],
            warmup_ratio=RUN_SPEC["warmup_ratio"],
            eval_steps=RUN_SPEC["eval_steps"],
            save_steps=RUN_SPEC["save_steps"],
            bf16=RUN_SPEC["bf16"],
            optim="adamw_8bit",
            logging_steps=10,
            evaluation_strategy="steps",
            seed=3407,
            report_to="none",
        ),
    )
    trainer.train()
    trainer.save_model(RUN_SPEC["output_dir"])
    tokenizer.save_pretrained(RUN_SPEC["output_dir"])


if __name__ == "__main__":
    main()
"""


def export_unsloth_training_script(path: str | Path, run_spec: UnslothRunSpec) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_unsloth_training_script(run_spec), encoding="utf-8")
    return output_path
