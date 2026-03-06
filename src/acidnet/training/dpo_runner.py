from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.training.finetune_manifest import FineTuneExperiment


@dataclass(frozen=True, slots=True)
class DPORunSpec:
    experiment_key: str
    model_name: str
    sft_adapter_path: str | None
    output_dir: str
    beta: float
    max_prompt_length: int
    max_length: int
    learning_rate: float
    per_device_train_batch_size: int
    gradient_accumulation_steps: int
    num_train_epochs: int
    eval_steps: int
    save_steps: int
    lora_rank: int
    lora_alpha: int
    bf16: bool
    train_dataset_path: str
    eval_dataset_path: str


def build_dpo_run_spec(
    experiment: FineTuneExperiment,
    *,
    train_dataset_path: str,
    eval_dataset_path: str,
    output_dir: str,
    sft_adapter_path: str | None = None,
) -> DPORunSpec:
    return DPORunSpec(
        experiment_key=f"{experiment.key}_dpo",
        model_name=experiment.train_model_id,
        sft_adapter_path=sft_adapter_path,
        output_dir=output_dir,
        beta=0.1,
        max_prompt_length=min(2048, experiment.max_seq_length // 2),
        max_length=experiment.max_seq_length,
        learning_rate=5e-6,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=max(8, experiment.gradient_accumulation_steps),
        num_train_epochs=1,
        eval_steps=100,
        save_steps=100,
        lora_rank=experiment.lora_rank,
        lora_alpha=experiment.lora_alpha,
        bf16=experiment.precision == "bf16",
        train_dataset_path=train_dataset_path,
        eval_dataset_path=eval_dataset_path,
    )


def export_dpo_run_spec(path: str | Path, run_spec: DPORunSpec) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(run_spec), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def render_dpo_training_script(run_spec: DPORunSpec) -> str:
    spec_repr = repr(asdict(run_spec))
    return f"""from __future__ import annotations

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

from acidnet.training.windows_env import ensure_windows_shims_on_path

ensure_windows_shims_on_path()

import torch
from datasets import load_dataset
from peft import LoraConfig, PeftModel, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOConfig, DPOTrainer

RUN_SPEC = {spec_repr}


def build_prompt(record):
    if isinstance(record.get("prompt"), str) and record["prompt"].strip():
        return record["prompt"]
    messages = record.get("messages")
    if isinstance(messages, str):
        return messages
    return "\\n".join(f"{{item['role']}}: {{item['content']}}" for item in messages)


def to_dpo_record(record):
    return {{
        "prompt": build_prompt(record),
        "chosen": record["chosen"],
        "rejected": record["rejected"],
    }}


def main() -> None:
    dtype = torch.bfloat16 if RUN_SPEC["bf16"] and torch.cuda.is_available() else torch.float16
    tokenizer = AutoTokenizer.from_pretrained(RUN_SPEC["model_name"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        RUN_SPEC["model_name"],
        dtype=dtype,
        device_map="auto" if torch.cuda.is_available() else None,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    model.config.use_cache = False

    if RUN_SPEC["sft_adapter_path"]:
        model = PeftModel.from_pretrained(model, RUN_SPEC["sft_adapter_path"], is_trainable=True)
    else:
        peft_config = LoraConfig(
            r=RUN_SPEC["lora_rank"],
            lora_alpha=RUN_SPEC["lora_alpha"],
            lora_dropout=0.05,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )
        model = get_peft_model(model, peft_config)

    train_raw = load_dataset("json", data_files=RUN_SPEC["train_dataset_path"], split="train")
    eval_raw = load_dataset("json", data_files=RUN_SPEC["eval_dataset_path"], split="train")
    train_dataset = train_raw.map(to_dpo_record, remove_columns=train_raw.column_names)
    eval_dataset = eval_raw.map(to_dpo_record, remove_columns=eval_raw.column_names)

    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        args=DPOConfig(
            output_dir=RUN_SPEC["output_dir"],
            beta=RUN_SPEC["beta"],
            max_prompt_length=RUN_SPEC["max_prompt_length"],
            max_length=RUN_SPEC["max_length"],
            learning_rate=RUN_SPEC["learning_rate"],
            per_device_train_batch_size=RUN_SPEC["per_device_train_batch_size"],
            gradient_accumulation_steps=RUN_SPEC["gradient_accumulation_steps"],
            num_train_epochs=RUN_SPEC["num_train_epochs"],
            eval_strategy="steps",
            eval_steps=RUN_SPEC["eval_steps"],
            save_steps=RUN_SPEC["save_steps"],
            logging_steps=10,
            bf16=RUN_SPEC["bf16"] and torch.cuda.is_available(),
            fp16=not RUN_SPEC["bf16"] and torch.cuda.is_available(),
            report_to=[],
            optim="adamw_torch",
        ),
        processing_class=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
    )
    trainer.train()
    trainer.save_model(RUN_SPEC["output_dir"])
    tokenizer.save_pretrained(RUN_SPEC["output_dir"])


if __name__ == "__main__":
    main()
"""


def export_dpo_training_script(path: str | Path, run_spec: DPORunSpec) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_dpo_training_script(run_spec), encoding="utf-8")
    return output_path
