from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.training.finetune_manifest import FineTuneExperiment
from acidnet.training.unsloth_runner import RunPaths


@dataclass(frozen=True, slots=True)
class HFPeftRunSpec:
    experiment_key: str
    model_name: str
    output_dir: str
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
    lora_dropout: float
    bf16: bool
    load_in_4bit: bool
    optimizer: str
    train_dataset_path: str
    eval_dataset_path: str


def build_hf_peft_run_spec(experiment: FineTuneExperiment, paths: RunPaths) -> HFPeftRunSpec:
    return HFPeftRunSpec(
        experiment_key=experiment.key,
        model_name=experiment.train_model_id,
        output_dir=paths.output_dir,
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
        lora_dropout=0.05,
        bf16=experiment.precision == "bf16",
        load_in_4bit=False,
        optimizer="adamw_torch",
        train_dataset_path=paths.train_dataset_path,
        eval_dataset_path=paths.eval_dataset_path,
    )


def export_hf_peft_run_spec(path: str | Path, run_spec: HFPeftRunSpec) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(run_spec), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def render_hf_peft_training_script(run_spec: HFPeftRunSpec) -> str:
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

from acidnet.training.windows_env import ensure_windows_shims_on_path

ensure_windows_shims_on_path()

import torch
from datasets import load_dataset
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

RUN_SPEC = {spec_repr}


def build_text(record, tokenizer):
    messages = json.loads(record["messages"]) if isinstance(record["messages"], str) else record["messages"]
    if hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
                enable_thinking=False,
            )
        except Exception:
            pass
    return "\\n".join(f"{{item['role']}}: {{item['content']}}" for item in messages)


def tokenize_record(record, tokenizer):
    text = build_text(record, tokenizer)
    return tokenizer(
        text,
        truncation=True,
        max_length=RUN_SPEC["max_seq_length"],
        padding=False,
    )


def main() -> None:
    dtype = torch.bfloat16 if RUN_SPEC["bf16"] and torch.cuda.is_available() else torch.float16
    tokenizer = AutoTokenizer.from_pretrained(RUN_SPEC["model_name"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = None
    device_map = None
    if RUN_SPEC["load_in_4bit"]:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=dtype,
            bnb_4bit_quant_type="nf4",
        )
        device_map = "auto" if torch.cuda.is_available() else None

    model = AutoModelForCausalLM.from_pretrained(
        RUN_SPEC["model_name"],
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
        quantization_config=quantization_config,
        device_map=device_map,
    )
    model.config.use_cache = False
    if RUN_SPEC["load_in_4bit"]:
        model = prepare_model_for_kbit_training(model)
    if hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()

    peft_config = LoraConfig(
        r=RUN_SPEC["lora_rank"],
        lora_alpha=RUN_SPEC["lora_alpha"],
        lora_dropout=RUN_SPEC["lora_dropout"],
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, peft_config)

    train_raw = load_dataset("json", data_files=RUN_SPEC["train_dataset_path"], split="train")
    eval_raw = load_dataset("json", data_files=RUN_SPEC["eval_dataset_path"], split="train")
    train_dataset = train_raw.map(
        lambda record: tokenize_record(record, tokenizer),
        remove_columns=train_raw.column_names,
    )
    eval_dataset = eval_raw.map(
        lambda record: tokenize_record(record, tokenizer),
        remove_columns=eval_raw.column_names,
    )

    training_args = TrainingArguments(
        output_dir=RUN_SPEC["output_dir"],
        per_device_train_batch_size=RUN_SPEC["per_device_train_batch_size"],
        per_device_eval_batch_size=RUN_SPEC["per_device_train_batch_size"],
        gradient_accumulation_steps=RUN_SPEC["gradient_accumulation_steps"],
        num_train_epochs=RUN_SPEC["num_train_epochs"],
        learning_rate=RUN_SPEC["learning_rate"],
        warmup_ratio=RUN_SPEC["warmup_ratio"],
        bf16=RUN_SPEC["bf16"] and torch.cuda.is_available(),
        fp16=not RUN_SPEC["bf16"] and torch.cuda.is_available(),
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=RUN_SPEC["eval_steps"],
        save_steps=RUN_SPEC["save_steps"],
        save_total_limit=2,
        report_to=[],
        gradient_checkpointing=True,
        optim=RUN_SPEC["optimizer"],
        remove_unused_columns=True,
        dataloader_pin_memory=True,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset if len(eval_dataset) > 0 else None,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    trainer.train()
    model.save_pretrained(RUN_SPEC["output_dir"])
    tokenizer.save_pretrained(RUN_SPEC["output_dir"])


if __name__ == "__main__":
    main()
"""


def export_hf_peft_training_script(path: str | Path, run_spec: HFPeftRunSpec) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_hf_peft_training_script(run_spec), encoding="utf-8")
    return output_path
