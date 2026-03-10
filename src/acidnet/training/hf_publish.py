from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE = ROOT / ".env"
DEFAULT_DATASET_FILES = (
    Path("data") / "sft" / "train_bootstrap_teacher_sft_dataset.jsonl",
    Path("data") / "sft" / "eval_bootstrap_teacher_sft_dataset.jsonl",
    Path("data") / "sft" / "bench_train_1024.jsonl",
    Path("data") / "sft" / "bench_eval_128.jsonl",
)
DEFAULT_OPTIONAL_DATASET_FILES = (
    Path("data") / "preferences" / "bootstrap_dialogue_preferences.parquet",
    Path("data") / "preferences" / "bootstrap_dialogue_preferences_manifest.json",
)


class UploadApi(Protocol):
    def create_repo(self, repo_id: str, *, repo_type: str, private: bool, exist_ok: bool) -> Any:
        ...

    def upload_folder(
        self,
        *,
        folder_path: str,
        path_in_repo: str,
        repo_id: str,
        repo_type: str,
        commit_message: str,
    ) -> Any:
        ...

    def upload_file(
        self,
        *,
        path_or_fileobj: str,
        path_in_repo: str,
        repo_id: str,
        repo_type: str,
        commit_message: str,
    ) -> Any:
        ...


@dataclass(frozen=True)
class HFPublishSettings:
    token: str
    namespace: str
    model_repo: str
    dataset_repo: str
    private: bool


@dataclass(frozen=True)
class HFPublishPlan:
    run_name: str
    dataset_name: str
    model_repo_id: str
    dataset_repo_id: str
    private: bool
    adapter_dir: Path | None
    gguf_paths: tuple[Path, ...]
    dataset_files: tuple[Path, ...]
    manifest_path: Path
    metadata: dict[str, Any]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish LoRA/GGUF artifacts and runtime-dialogue datasets to Hugging Face Hub."
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Path to the .env file with HF_NAMESPACE / HF_MODEL_REPO / HF_DATASET_REPO / HF_TOKEN.",
    )
    parser.add_argument("--run-name", required=True, help="Run identifier used under runs/<run-name>/ in the Hub repos.")
    parser.add_argument(
        "--dataset-name",
        default="",
        help="Optional dataset identifier under runs/<dataset-name>/. Defaults to --run-name.",
    )
    parser.add_argument(
        "--adapter-dir",
        default="",
        help="Local LoRA adapter directory to upload to the model repo.",
    )
    parser.add_argument(
        "--gguf-path",
        action="append",
        default=[],
        help="Local GGUF file or directory to upload to the model repo. Repeat for multiple paths.",
    )
    parser.add_argument(
        "--dataset-file",
        action="append",
        default=[],
        help="Dataset file to upload to the dataset repo. Repeat for multiple files. Defaults to the canonical full+bench split.",
    )
    parser.add_argument(
        "--manifest-path",
        default="",
        help="Optional local manifest output path. Defaults to data/training/<run-name>_hf_publish_manifest.json.",
    )
    parser.add_argument(
        "--base-model",
        default="",
        help="Optional base model identifier for metadata.",
    )
    parser.add_argument(
        "--promotion-status",
        choices=("candidate", "failed_gate", "promoted"),
        default="candidate",
        help="Promotion state recorded in the publish manifest and Hub README cards.",
    )
    parser.add_argument(
        "--promote-latest",
        action="store_true",
        help="Also refresh promoted/latest aliases in the Hub repos. Use only for gate-passing promoted runs.",
    )
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="Skip publishing LoRA/GGUF artifacts.",
    )
    parser.add_argument(
        "--skip-dataset",
        action="store_true",
        help="Skip publishing dataset files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and write the local manifest without contacting Hugging Face Hub.",
    )
    return parser


def load_env_file(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise ValueError(f"Invalid .env line {line_number} in {env_path}: expected KEY=VALUE.")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def resolve_publish_settings(file_env: dict[str, str], process_env: dict[str, str] | None = None) -> HFPublishSettings:
    process_values = process_env or dict(os.environ)

    def get_value(key: str, default: str = "") -> str:
        return process_values.get(key) or file_env.get(key) or default

    token = get_value("HF_TOKEN")
    if not token:
        raise ValueError("HF_TOKEN is required in .env or the process environment.")

    return HFPublishSettings(
        token=token,
        namespace=get_value("HF_NAMESPACE", "acidsound"),
        model_repo=get_value("HF_MODEL_REPO", "acidnet_model"),
        dataset_repo=get_value("HF_DATASET_REPO", "acidnet_dataset"),
        private=parse_bool(get_value("HF_PRIVATE", "true")),
    )


def parse_bool(raw_value: str) -> bool:
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def build_publish_plan(args: argparse.Namespace, process_env: dict[str, str] | None = None) -> tuple[HFPublishSettings, HFPublishPlan]:
    file_env = load_env_file(args.env_file)
    settings = resolve_publish_settings(file_env, process_env=process_env)

    run_name = args.run_name.strip()
    if not run_name:
        raise ValueError("--run-name must not be empty.")
    dataset_name = args.dataset_name.strip() or run_name

    adapter_dir = None if args.skip_model or not args.adapter_dir else resolve_repo_path(args.adapter_dir)
    gguf_paths = tuple() if args.skip_model else tuple(resolve_repo_path(path) for path in args.gguf_path)
    dataset_paths = (
        tuple()
        if args.skip_dataset
        else (
            tuple(resolve_repo_path(path) for path in args.dataset_file)
            if args.dataset_file
            else default_dataset_paths()
        )
    )
    manifest_path = (
        resolve_repo_path(args.manifest_path)
        if args.manifest_path
        else ROOT / "data" / "training" / f"{run_name}_hf_publish_manifest.json"
    )

    if args.skip_model and args.skip_dataset:
        raise ValueError("At least one of model or dataset publishing must stay enabled.")
    if not args.skip_model and adapter_dir is None and not gguf_paths:
        raise ValueError("Model publishing requires --adapter-dir or at least one --gguf-path.")
    if args.promote_latest and args.promotion_status != "promoted":
        raise ValueError("--promote-latest may only be used with --promotion-status promoted.")

    validate_model_inputs(adapter_dir=adapter_dir, gguf_paths=gguf_paths, skip_model=args.skip_model)
    validate_dataset_inputs(dataset_paths=dataset_paths, skip_dataset=args.skip_dataset)

    model_repo_paths = build_model_repo_paths(run_name=run_name, adapter_dir=adapter_dir, gguf_paths=gguf_paths)
    dataset_repo_paths = build_dataset_repo_paths(dataset_name=dataset_name, dataset_paths=dataset_paths)
    gate_summary = extract_gate_summary(dataset_paths)
    if args.promote_latest:
        model_repo_paths["promoted_latest"] = build_promoted_model_repo_paths(
            adapter_dir=adapter_dir,
            gguf_paths=gguf_paths,
        )
        dataset_repo_paths["promoted_latest"] = build_promoted_dataset_repo_paths(dataset_paths=dataset_paths)

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_name": run_name,
        "dataset_name": dataset_name,
        "namespace": settings.namespace,
        "model_repo_id": f"{settings.namespace}/{settings.model_repo}",
        "dataset_repo_id": f"{settings.namespace}/{settings.dataset_repo}",
        "private": settings.private,
        "adapter_dir": portable_repo_path(adapter_dir) if adapter_dir else None,
        "gguf_paths": [portable_repo_path(path) for path in gguf_paths],
        "dataset_files": [portable_repo_path(path) for path in dataset_paths],
        "manifest_path": portable_repo_path(manifest_path),
        "model_repo_paths": model_repo_paths,
        "dataset_repo_paths": dataset_repo_paths,
        "code_commit": current_git_commit(ROOT),
        "base_model": args.base_model or None,
        "promotion_status": args.promotion_status,
        "promote_latest": bool(args.promote_latest),
        "gate_summary": gate_summary,
    }
    plan = HFPublishPlan(
        run_name=run_name,
        dataset_name=dataset_name,
        model_repo_id=f"{settings.namespace}/{settings.model_repo}",
        dataset_repo_id=f"{settings.namespace}/{settings.dataset_repo}",
        private=settings.private,
        adapter_dir=adapter_dir,
        gguf_paths=gguf_paths,
        dataset_files=dataset_paths,
        manifest_path=manifest_path,
        metadata=metadata,
    )
    return settings, plan


def resolve_repo_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else (ROOT / path)


def default_dataset_paths() -> tuple[Path, ...]:
    paths = [resolve_repo_path(path) for path in DEFAULT_DATASET_FILES]
    for candidate in DEFAULT_OPTIONAL_DATASET_FILES:
        resolved = resolve_repo_path(candidate)
        if resolved.exists():
            paths.append(resolved)
    return tuple(paths)


def portable_repo_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def build_model_repo_paths(
    *,
    run_name: str,
    adapter_dir: Path | None,
    gguf_paths: tuple[Path, ...],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "readme": "README.md",
        "publish_manifest": f"runs/{run_name}/manifests/publish_manifest.json",
    }
    if adapter_dir is not None:
        payload["adapter_dir"] = f"runs/{run_name}/adapter"
    if gguf_paths:
        payload["gguf_paths"] = [model_repo_path_for_file(path, run_name=run_name) for path in gguf_paths]
    return payload


def build_promoted_model_repo_paths(
    *,
    adapter_dir: Path | None,
    gguf_paths: tuple[Path, ...],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "publish_manifest": "promoted/latest/manifests/publish_manifest.json",
    }
    if adapter_dir is not None:
        payload["adapter_dir"] = "promoted/latest/adapter"
    if gguf_paths:
        payload["gguf_paths"] = [model_repo_path_for_root(path, root_prefix="promoted/latest/gguf") for path in gguf_paths]
    return payload


def build_dataset_repo_paths(*, dataset_name: str, dataset_paths: tuple[Path, ...]) -> dict[str, object]:
    payload: dict[str, object] = {
        "readme": "README.md",
        "publish_manifest": f"runs/{dataset_name}/manifests/publish_manifest.json",
    }
    if dataset_paths:
        payload["dataset_files"] = [dataset_repo_path_for_file(path, dataset_name=dataset_name) for path in dataset_paths]
    return payload


def build_promoted_dataset_repo_paths(*, dataset_paths: tuple[Path, ...]) -> dict[str, object]:
    payload: dict[str, object] = {
        "publish_manifest": "promoted/latest/manifests/publish_manifest.json",
    }
    if dataset_paths:
        payload["dataset_files"] = [dataset_repo_path_for_root(path, root_prefix="promoted/latest") for path in dataset_paths]
    return payload


def model_repo_path_for_file(path: Path, *, run_name: str) -> str:
    return model_repo_path_for_root(path, root_prefix=f"runs/{run_name}/gguf")


def model_repo_path_for_root(path: Path, *, root_prefix: str) -> str:
    name = path.name
    if name.endswith(".gguf"):
        normalized = normalize_gguf_name(name)
        return f"{root_prefix}/{normalized}"
    if name.endswith(".json") and "manifest" in name.lower():
        return f"{root_prefix}/adapter_manifest.json"
    return f"{root_prefix}/{name}"


def normalize_gguf_name(name: str) -> str:
    match = re.search(r"(adapter(?:-[^.]+)?)\.gguf$", name)
    if match:
        return f"{match.group(1)}.gguf"
    return name


def dataset_repo_path_for_file(path: Path, *, dataset_name: str) -> str:
    return dataset_repo_path_for_root(path, root_prefix=f"runs/{dataset_name}")


def dataset_repo_path_for_root(path: Path, *, root_prefix: str) -> str:
    relative = portable_repo_path(path)
    mapped_name = map_dataset_relative_path(relative)
    return f"{root_prefix}/{mapped_name}"


def map_dataset_relative_path(relative_path: str) -> str:
    if relative_path == "data/prompt_packs/bootstrap_teacher_requests.parquet":
        return "prompt_packs/requests.parquet"
    if relative_path == "data/prompt_packs/bootstrap_teacher_requests.jsonl":
        return "prompt_packs/requests.jsonl"
    if relative_path == "data/prompt_packs/bootstrap_teacher_outputs.jsonl":
        return "prompt_packs/teacher_outputs.jsonl"
    if relative_path == "data/sft/train_bootstrap_teacher_sft_dataset.jsonl":
        return "sft/train.jsonl"
    if relative_path == "data/sft/eval_bootstrap_teacher_sft_dataset.jsonl":
        return "sft/eval.jsonl"
    if relative_path == "data/sft/train_bootstrap_teacher_sft_dataset.parquet":
        return "sft/train.parquet"
    if relative_path == "data/sft/eval_bootstrap_teacher_sft_dataset.parquet":
        return "sft/eval.parquet"
    if relative_path == "data/sft/bench_train_1024.jsonl":
        return "sft/bench_train_1024.jsonl"
    if relative_path == "data/sft/bench_eval_128.jsonl":
        return "sft/bench_eval_128.jsonl"
    if relative_path == "data/preferences/bootstrap_dialogue_preferences.parquet":
        return "preferences/preferences.parquet"
    if relative_path == "data/preferences/bootstrap_dialogue_preferences.jsonl":
        return "preferences/preferences.jsonl"
    if relative_path == "data/preferences/bootstrap_dialogue_preferences_manifest.json":
        return "preferences/manifest.json"
    if relative_path == "data/training/bootstrap_qwen4b_pipeline.json":
        return "manifests/pipeline.json"
    if relative_path.endswith("_run_spec.json"):
        return "manifests/run_spec.json"
    if relative_path.startswith("data/eval/") and "model_gate" in relative_path and relative_path.endswith(".json"):
        return "manifests/gate_report.json"
    if relative_path.endswith("_hf_publish_manifest.json"):
        return "manifests/publish_manifest.json"
    return f"extras/{Path(relative_path).name}"


def validate_model_inputs(*, adapter_dir: Path | None, gguf_paths: tuple[Path, ...], skip_model: bool) -> None:
    if skip_model:
        return
    if adapter_dir is not None:
        if not adapter_dir.exists():
            raise FileNotFoundError(f"Adapter directory not found: {adapter_dir}")
        if not adapter_dir.is_dir():
            raise ValueError(f"Adapter path must be a directory: {adapter_dir}")
    for path in gguf_paths:
        if not path.exists():
            raise FileNotFoundError(f"GGUF path not found: {path}")


def validate_dataset_inputs(*, dataset_paths: tuple[Path, ...], skip_dataset: bool) -> None:
    if skip_dataset:
        return
    for path in dataset_paths:
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")
        if not path.is_file():
            raise ValueError(f"Dataset path must be a file: {path}")


def current_git_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            check=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def extract_gate_summary(dataset_paths: tuple[Path, ...]) -> dict[str, Any] | None:
    for path in dataset_paths:
        relative = portable_repo_path(path)
        if not (relative.startswith("data/eval/") and "model_gate" in relative and path.suffix == ".json"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        circulation = payload.get("circulation") or {}
        return {
            "report_path": relative,
            "gate_passed": payload.get("gate_passed"),
            "prompt_average_score": payload.get("prompt_average_score"),
            "prompt_rows_with_failures": payload.get("prompt_rows_with_failures"),
            "prompt_average_latency_ms": payload.get("prompt_average_latency_ms"),
            "circulation_score": circulation.get("circulation_score"),
            "starving_npc_count": circulation.get("starving_npc_count"),
        }
    return None


def write_manifest(plan: HFPublishPlan) -> Path:
    plan.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    plan.manifest_path.write_text(json.dumps(plan.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan.manifest_path


def publish_artifacts(settings: HFPublishSettings, plan: HFPublishPlan, *, api: UploadApi | None = None) -> Path:
    write_manifest(plan)
    if api is None:
        api = build_hf_api(settings.token)

    if plan.adapter_dir is not None or plan.gguf_paths:
        api.create_repo(repo_id=plan.model_repo_id, repo_type="model", private=plan.private, exist_ok=True)
        upload_repo_readme(api, plan, repo_type="model")
        upload_model_artifacts(api, plan)
        api.upload_file(
            path_or_fileobj=str(plan.manifest_path),
            path_in_repo=str(plan.metadata["model_repo_paths"]["publish_manifest"]),
            repo_id=plan.model_repo_id,
            repo_type="model",
            commit_message=f"Add publish manifest for {plan.run_name}",
        )
        promoted_paths = plan.metadata["model_repo_paths"].get("promoted_latest")
        if promoted_paths:
            upload_model_artifacts(api, plan, repo_paths=promoted_paths)
            api.upload_file(
                path_or_fileobj=str(plan.manifest_path),
                path_in_repo=str(promoted_paths["publish_manifest"]),
                repo_id=plan.model_repo_id,
                repo_type="model",
                commit_message=f"Refresh promoted latest manifest for {plan.run_name}",
            )

    if plan.dataset_files:
        api.create_repo(repo_id=plan.dataset_repo_id, repo_type="dataset", private=plan.private, exist_ok=True)
        upload_repo_readme(api, plan, repo_type="dataset")
        upload_dataset_artifacts(api, plan)
        api.upload_file(
            path_or_fileobj=str(plan.manifest_path),
            path_in_repo=str(plan.metadata["dataset_repo_paths"]["publish_manifest"]),
            repo_id=plan.dataset_repo_id,
            repo_type="dataset",
            commit_message=f"Add publish manifest for {plan.dataset_name}",
        )
        promoted_paths = plan.metadata["dataset_repo_paths"].get("promoted_latest")
        if promoted_paths:
            upload_dataset_artifacts(api, plan, repo_paths=promoted_paths)
            api.upload_file(
                path_or_fileobj=str(plan.manifest_path),
                path_in_repo=str(promoted_paths["publish_manifest"]),
                repo_id=plan.dataset_repo_id,
                repo_type="dataset",
                commit_message=f"Refresh promoted latest manifest for {plan.dataset_name}",
            )

    return plan.manifest_path


def upload_model_artifacts(api: UploadApi, plan: HFPublishPlan, *, repo_paths: dict[str, object] | None = None) -> None:
    resolved_repo_paths = repo_paths or plan.metadata["model_repo_paths"]
    if plan.adapter_dir is not None:
        api.upload_folder(
            folder_path=str(plan.adapter_dir),
            path_in_repo=str(resolved_repo_paths["adapter_dir"]),
            repo_id=plan.model_repo_id,
            repo_type="model",
            commit_message=f"Upload adapter for {plan.run_name}",
        )

    gguf_repo_paths = list(resolved_repo_paths.get("gguf_paths", []))
    for index, gguf_path in enumerate(plan.gguf_paths):
        target_path = gguf_repo_paths[index] if index < len(gguf_repo_paths) else model_repo_path_for_file(gguf_path, run_name=plan.run_name)
        if gguf_path.is_dir():
            api.upload_folder(
                folder_path=str(gguf_path),
                path_in_repo=target_path,
                repo_id=plan.model_repo_id,
                repo_type="model",
                commit_message=f"Upload GGUF directory for {plan.run_name}",
            )
            continue
        api.upload_file(
            path_or_fileobj=str(gguf_path),
            path_in_repo=target_path,
            repo_id=plan.model_repo_id,
            repo_type="model",
            commit_message=f"Upload GGUF file for {plan.run_name}",
        )


def upload_dataset_artifacts(api: UploadApi, plan: HFPublishPlan, *, repo_paths: dict[str, object] | None = None) -> None:
    resolved_repo_paths = repo_paths or plan.metadata["dataset_repo_paths"]
    dataset_repo_files = list(resolved_repo_paths.get("dataset_files", []))
    for index, dataset_path in enumerate(plan.dataset_files):
        target_path = (
            dataset_repo_files[index]
            if index < len(dataset_repo_files)
            else dataset_repo_path_for_file(dataset_path, dataset_name=plan.dataset_name)
        )
        api.upload_file(
            path_or_fileobj=str(dataset_path),
            path_in_repo=target_path,
            repo_id=plan.dataset_repo_id,
            repo_type="dataset",
            commit_message=f"Upload dataset file for {plan.dataset_name}",
        )


def upload_repo_readme(api: UploadApi, plan: HFPublishPlan, *, repo_type: str) -> None:
    content = build_repo_readme(plan, repo_type=repo_type)
    target_repo = plan.model_repo_id if repo_type == "model" else plan.dataset_repo_id
    commit_message = (
        f"Refresh model card for {plan.run_name}"
        if repo_type == "model"
        else f"Refresh dataset card for {plan.dataset_name}"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    try:
        api.upload_file(
            path_or_fileobj=str(temp_path),
            path_in_repo="README.md",
            repo_id=target_repo,
            repo_type=repo_type,
            commit_message=commit_message,
        )
    finally:
        temp_path.unlink(missing_ok=True)


def build_repo_readme(plan: HFPublishPlan, *, repo_type: str) -> str:
    if repo_type == "model":
        return build_model_repo_readme(plan)
    return build_dataset_repo_readme(plan)


def build_model_repo_readme(plan: HFPublishPlan) -> str:
    repo_paths = plan.metadata.get("model_repo_paths", {})
    promoted_paths = repo_paths.get("promoted_latest", {})
    promotion_status = plan.metadata.get("promotion_status", "candidate")
    gate_summary = plan.metadata.get("gate_summary") or {}
    gguf_lines = "\n".join(
        f"- `{local_path}` -> `{remote_path}`"
        for local_path, remote_path in zip(
            plan.metadata.get("gguf_paths", []),
            repo_paths.get("gguf_paths", []),
            strict=False,
        )
    ) or "- none"
    return (
        "---\n"
        f"base_model: {plan.metadata.get('base_model') or 'Qwen/Qwen3.5-4B'}\n"
        "tags:\n"
        "- acidnet\n"
        "- lora\n"
        "- gguf\n"
        "- qwen\n"
        "---\n\n"
        "# AcidNet Model Artifacts\n\n"
        "This repo stores portable AcidNet model artifacts.\n\n"
        "It is a registry, not the live runtime mount. AcidNet still serves and evaluates local files after you restore them into the repo working tree.\n\n"
        "## Latest Uploaded Run\n\n"
        f"- run: `{plan.run_name}`\n"
        f"- promotion status: `{promotion_status}`\n"
        f"- base model: `{plan.metadata.get('base_model') or 'unspecified'}`\n"
        f"- adapter repo path: `{repo_paths.get('adapter_dir', '(not published)')}`\n"
        f"- publish manifest: `{repo_paths.get('publish_manifest', '(missing)')}`\n"
        f"- repo card: `{repo_paths.get('readme', 'README.md')}`\n\n"
        "## Promoted Alias\n\n"
        + (
            f"- updated by this publish: `promoted/latest`\n"
            f"- adapter repo path: `{promoted_paths.get('adapter_dir', '(not published)')}`\n"
            f"- publish manifest: `{promoted_paths.get('publish_manifest', '(missing)')}`\n\n"
            if promoted_paths
            else "- not updated by this publish\n\n"
        )
        + (
            "## Gate Summary\n\n"
            f"- gate passed: `{gate_summary.get('gate_passed')}`\n"
            f"- prompt average score: `{gate_summary.get('prompt_average_score')}`\n"
            f"- prompt rows with failures: `{gate_summary.get('prompt_rows_with_failures')}`\n"
            f"- prompt average latency ms: `{gate_summary.get('prompt_average_latency_ms')}`\n"
            f"- circulation score: `{gate_summary.get('circulation_score')}`\n"
            f"- starving npc count: `{gate_summary.get('starving_npc_count')}`\n"
            f"- source report: `{gate_summary.get('report_path')}`\n\n"
            if gate_summary
            else ""
        )
        +
        "## Restore Map\n\n"
        f"- restore `{repo_paths.get('adapter_dir', '(not published)')}` into a local directory such as `data/training/{plan.run_name}_adapter/` for `local_peft` dev/eval parity\n"
        "- restore the GGUF files below into `data/gguf/` for `llama-server`\n"
        "- keep the base `Q4_K_M` model in a separate local path such as `models/`; this repo stores only the fine-tuned adapter artifacts\n\n"
        "## GGUF Files\n\n"
        f"{gguf_lines}\n"
    )


def build_dataset_repo_readme(plan: HFPublishPlan) -> str:
    repo_paths = plan.metadata.get("dataset_repo_paths", {})
    promoted_paths = repo_paths.get("promoted_latest", {})
    promotion_status = plan.metadata.get("promotion_status", "candidate")
    gate_summary = plan.metadata.get("gate_summary") or {}
    dataset_lines = "\n".join(
        f"- `{local_path}` -> `{remote_path}`"
        for local_path, remote_path in zip(
            plan.metadata.get("dataset_files", []),
            repo_paths.get("dataset_files", []),
            strict=False,
        )
    ) or "- none"
    return (
        "---\n"
        "tags:\n"
        "- acidnet\n"
        "- generated\n"
        "- dialogue\n"
        "task_categories:\n"
        "- text-generation\n"
        "---\n\n"
        "# AcidNet Runtime Dialogue Datasets\n\n"
        "This repo stores generated AcidNet dialogue datasets and provenance bundles.\n\n"
        "It is a portability registry. Training still reads local files under `data/`, so restore published files back into the same repo-relative paths before rerunning WSL training or local evaluation.\n\n"
        "## Latest Uploaded Run\n\n"
        f"- run: `{plan.dataset_name}`\n"
        f"- promotion status: `{promotion_status}`\n"
        f"- publish manifest: `{repo_paths.get('publish_manifest', '(missing)')}`\n"
        f"- repo card: `{repo_paths.get('readme', 'README.md')}`\n\n"
        "## Promoted Alias\n\n"
        + (
            f"- updated by this publish: `promoted/latest`\n"
            f"- publish manifest: `{promoted_paths.get('publish_manifest', '(missing)')}`\n\n"
            if promoted_paths
            else "- not updated by this publish\n\n"
        )
        + (
            "## Gate Summary\n\n"
            f"- gate passed: `{gate_summary.get('gate_passed')}`\n"
            f"- prompt average score: `{gate_summary.get('prompt_average_score')}`\n"
            f"- prompt rows with failures: `{gate_summary.get('prompt_rows_with_failures')}`\n"
            f"- prompt average latency ms: `{gate_summary.get('prompt_average_latency_ms')}`\n"
            f"- circulation score: `{gate_summary.get('circulation_score')}`\n"
            f"- starving npc count: `{gate_summary.get('starving_npc_count')}`\n"
            f"- source report: `{gate_summary.get('report_path')}`\n\n"
            if gate_summary
            else ""
        )
        +
        "## Restore Map\n\n"
        "- restore prompt-pack provenance into `data/prompt_packs/`\n"
        "- restore train/eval and bench splits into `data/sft/`\n"
        "- restore pipeline manifests and run specs into `data/training/`\n"
        "- restore gate reports into `data/eval/`\n\n"
        "## RL Precursor\n\n"
        "- if `runs/<run>/preferences/` is present, it is the optional dialogue-preference dataset for later RL/DPO-style work\n"
        "- restore that bundle into `data/preferences/`\n\n"
        "## Published Files\n\n"
        f"{dataset_lines}\n"
    )


def build_hf_api(token: str) -> UploadApi:
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing at runtime
        raise SystemExit(
            "huggingface_hub is required to publish artifacts. Install it in the active environment first."
        ) from exc
    return HfApi(token=token)


def plan_payload(plan: HFPublishPlan) -> dict[str, Any]:
    return {
        "run_name": plan.run_name,
        "dataset_name": plan.dataset_name,
        "model_repo_id": plan.model_repo_id,
        "dataset_repo_id": plan.dataset_repo_id,
        "private": plan.private,
        "adapter_dir": portable_repo_path(plan.adapter_dir) if plan.adapter_dir else None,
        "gguf_paths": [portable_repo_path(path) for path in plan.gguf_paths],
        "dataset_files": [portable_repo_path(path) for path in plan.dataset_files],
        "manifest_path": portable_repo_path(plan.manifest_path),
        "metadata": plan.metadata,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings, plan = build_publish_plan(args)
    manifest_path = write_manifest(plan)
    if args.dry_run:
        print(json.dumps(plan_payload(plan), ensure_ascii=False, indent=2))
        print(f"Dry run only. Manifest written to {manifest_path}")
        return 0
    publish_artifacts(settings, plan)
    if plan.adapter_dir is not None or plan.gguf_paths:
        print(f"Published model repo: {plan.model_repo_id}")
    if plan.dataset_files:
        print(f"Published dataset repo: {plan.dataset_repo_id}")
    print(f"Local publish manifest: {manifest_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
