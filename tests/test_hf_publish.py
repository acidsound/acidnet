import json
from pathlib import Path

import acidnet.training.hf_publish as hf_publish


class FakeUploadApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def create_repo(self, repo_id: str, *, repo_type: str, private: bool, exist_ok: bool) -> None:
        self.calls.append(
            (
                "create_repo",
                {
                    "repo_id": repo_id,
                    "repo_type": repo_type,
                    "private": private,
                    "exist_ok": exist_ok,
                },
            )
        )

    def upload_folder(
        self,
        *,
        folder_path: str,
        path_in_repo: str,
        repo_id: str,
        repo_type: str,
        commit_message: str,
    ) -> None:
        self.calls.append(
            (
                "upload_folder",
                {
                    "folder_path": folder_path,
                    "path_in_repo": path_in_repo,
                    "repo_id": repo_id,
                    "repo_type": repo_type,
                    "commit_message": commit_message,
                },
            )
        )

    def upload_file(
        self,
        *,
        path_or_fileobj: str,
        path_in_repo: str,
        repo_id: str,
        repo_type: str,
        commit_message: str,
    ) -> None:
        self.calls.append(
            (
                "upload_file",
                {
                    "path_or_fileobj": path_or_fileobj,
                    "path_in_repo": path_in_repo,
                    "repo_id": repo_id,
                    "repo_type": repo_type,
                    "commit_message": commit_message,
                },
            )
        )


def test_load_env_file_supports_export_and_quotes(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# comment",
                "export HF_TOKEN='hf_secret'",
                'HF_NAMESPACE="acidsound"',
                "HF_PRIVATE=true",
            ]
        ),
        encoding="utf-8",
    )

    values = hf_publish.load_env_file(env_path)

    assert values["HF_TOKEN"] == "hf_secret"
    assert values["HF_NAMESPACE"] == "acidsound"
    assert values["HF_PRIVATE"] == "true"


def test_resolve_publish_settings_prefers_process_env() -> None:
    settings = hf_publish.resolve_publish_settings(
        {
            "HF_TOKEN": "hf_file_token",
            "HF_NAMESPACE": "file-namespace",
            "HF_MODEL_REPO": "file_model",
            "HF_DATASET_REPO": "file_dataset",
            "HF_PRIVATE": "false",
        },
        process_env={
            "HF_TOKEN": "hf_process_token",
            "HF_NAMESPACE": "process-namespace",
        },
    )

    assert settings == hf_publish.HFPublishSettings(
        token="hf_process_token",
        namespace="process-namespace",
        model_repo="file_model",
        dataset_repo="file_dataset",
        private=False,
    )


def test_build_publish_plan_uses_default_dataset_targets(tmp_path: Path, monkeypatch) -> None:
    train_path = tmp_path / "train.jsonl"
    train_path.write_text('{"messages":[]}\n', encoding="utf-8")
    eval_path = tmp_path / "eval.jsonl"
    eval_path.write_text('{"messages":[]}\n', encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.write_text("HF_TOKEN=hf_token\n", encoding="utf-8")
    monkeypatch.setattr(hf_publish, "DEFAULT_DATASET_FILES", (train_path, eval_path))
    monkeypatch.setattr(hf_publish, "DEFAULT_OPTIONAL_DATASET_FILES", ())

    args = hf_publish.build_parser().parse_args(
        [
            "--env-file",
            str(env_path),
            "--run-name",
            "runtime-dialogue-smoke",
            "--skip-model",
        ]
    )

    settings, plan = hf_publish.build_publish_plan(args, process_env={})

    assert settings.namespace == "acidsound"
    assert settings.model_repo == "acidnet_model"
    assert plan.dataset_name == "runtime-dialogue-smoke"
    assert plan.dataset_files == (train_path, eval_path)
    assert plan.manifest_path == (
        Path(__file__).resolve().parents[1]
        / "data"
        / "training"
        / "runtime-dialogue-smoke_hf_publish_manifest.json"
    )
    assert plan.metadata["dataset_files"] == [
        hf_publish.portable_repo_path(train_path),
        hf_publish.portable_repo_path(eval_path),
    ]
    assert plan.metadata["manifest_path"] == "data/training/runtime-dialogue-smoke_hf_publish_manifest.json"
    assert plan.metadata["promotion_status"] == "candidate"
    assert plan.metadata["promote_latest"] is False
    assert plan.metadata["dataset_repo_paths"] == {
        "readme": "README.md",
        "publish_manifest": "runs/runtime-dialogue-smoke/manifests/publish_manifest.json",
        "dataset_files": [
            "runs/runtime-dialogue-smoke/extras/train.jsonl",
            "runs/runtime-dialogue-smoke/extras/eval.jsonl",
        ],
    }


def test_publish_artifacts_uploads_model_dataset_and_manifest(tmp_path: Path) -> None:
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    gguf_path = tmp_path / "runtime.gguf"
    gguf_path.write_bytes(b"GGUF")
    train_path = tmp_path / "train.jsonl"
    train_path.write_text('{"messages":[]}\n', encoding="utf-8")
    eval_path = tmp_path / "eval.jsonl"
    eval_path.write_text('{"messages":[]}\n', encoding="utf-8")
    manifest_path = tmp_path / "publish_manifest.json"

    plan = hf_publish.HFPublishPlan(
        run_name="runtime-dialogue-full",
        dataset_name="runtime-dialogue-full",
        model_repo_id="acidsound/acidnet_model",
        dataset_repo_id="acidsound/acidnet_dataset",
        private=True,
        adapter_dir=adapter_dir,
        gguf_paths=(gguf_path,),
        dataset_files=(train_path, eval_path),
        manifest_path=manifest_path,
        metadata={
            "run_name": "runtime-dialogue-full",
            "promotion_status": "failed_gate",
            "promote_latest": False,
            "gate_summary": {
                "report_path": "data/eval/model_gate_runtime_dialogue_full_report.json",
                "gate_passed": False,
                "prompt_average_score": 0.979,
                "prompt_rows_with_failures": 4,
                "prompt_average_latency_ms": 2444.8,
                "circulation_score": 0.807,
                "starving_npc_count": 0,
            },
            "model_repo_paths": {
                "readme": "README.md",
                "publish_manifest": "runs/runtime-dialogue-full/manifests/publish_manifest.json",
                "adapter_dir": "runs/runtime-dialogue-full/adapter",
                "gguf_paths": ["runs/runtime-dialogue-full/gguf/runtime.gguf"],
            },
            "dataset_repo_paths": {
                "readme": "README.md",
                "publish_manifest": "runs/runtime-dialogue-full/manifests/publish_manifest.json",
                "dataset_files": [
                    "runs/runtime-dialogue-full/extras/train.jsonl",
                    "runs/runtime-dialogue-full/extras/eval.jsonl",
                ],
            },
        },
    )
    settings = hf_publish.HFPublishSettings(
        token="hf_token",
        namespace="acidsound",
        model_repo="acidnet_model",
        dataset_repo="acidnet_dataset",
        private=True,
    )
    api = FakeUploadApi()

    output_manifest = hf_publish.publish_artifacts(settings, plan, api=api)

    assert output_manifest == manifest_path
    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["run_name"] == "runtime-dialogue-full"

    assert (
        "create_repo",
        {
            "repo_id": "acidsound/acidnet_model",
            "repo_type": "model",
            "private": True,
            "exist_ok": True,
        },
    ) in api.calls
    assert (
        "create_repo",
        {
            "repo_id": "acidsound/acidnet_dataset",
            "repo_type": "dataset",
            "private": True,
            "exist_ok": True,
        },
    ) in api.calls
    assert (
        "upload_folder",
        {
            "folder_path": str(adapter_dir),
            "path_in_repo": "runs/runtime-dialogue-full/adapter",
            "repo_id": "acidsound/acidnet_model",
            "repo_type": "model",
            "commit_message": "Upload adapter for runtime-dialogue-full",
        },
    ) in api.calls
    assert (
        "upload_file",
        {
            "path_or_fileobj": str(gguf_path),
            "path_in_repo": "runs/runtime-dialogue-full/gguf/runtime.gguf",
            "repo_id": "acidsound/acidnet_model",
            "repo_type": "model",
            "commit_message": "Upload GGUF file for runtime-dialogue-full",
        },
    ) in api.calls
    assert (
        "upload_file",
        {
            "path_or_fileobj": str(train_path),
            "path_in_repo": "runs/runtime-dialogue-full/extras/train.jsonl",
            "repo_id": "acidsound/acidnet_dataset",
            "repo_type": "dataset",
            "commit_message": "Upload dataset file for runtime-dialogue-full",
        },
    ) in api.calls
    assert (
        "upload_file",
        {
            "path_or_fileobj": str(eval_path),
            "path_in_repo": "runs/runtime-dialogue-full/extras/eval.jsonl",
            "repo_id": "acidsound/acidnet_dataset",
            "repo_type": "dataset",
            "commit_message": "Upload dataset file for runtime-dialogue-full",
        },
    ) in api.calls
    assert any(
        call_name == "upload_file"
        and payload["path_in_repo"] == "README.md"
        and payload["repo_id"] == "acidsound/acidnet_model"
        and payload["repo_type"] == "model"
        and payload["commit_message"] == "Refresh model card for runtime-dialogue-full"
        for call_name, payload in api.calls
    )
    assert any(
        call_name == "upload_file"
        and payload["path_in_repo"] == "README.md"
        and payload["repo_id"] == "acidsound/acidnet_dataset"
        and payload["repo_type"] == "dataset"
        and payload["commit_message"] == "Refresh dataset card for runtime-dialogue-full"
        for call_name, payload in api.calls
    )


def test_manifest_uses_relative_paths_and_records_remote_targets(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    adapter_dir = repo_root / "data" / "test_artifacts" / "hf_publish_adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    gguf_path = repo_root / "data" / "test_artifacts" / "hf_publish.gguf"
    dataset_path = repo_root / "data" / "test_artifacts" / "hf_publish_dataset.jsonl"
    manifest_path = repo_root / "data" / "test_artifacts" / "hf_publish_manifest.json"

    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    gguf_path.write_bytes(b"GGUF")
    dataset_path.write_text('{"messages":[]}\n', encoding="utf-8")

    plan = hf_publish.HFPublishPlan(
        run_name="portable-run",
        dataset_name="portable-run",
        model_repo_id="acidsound/acidnet_model",
        dataset_repo_id="acidsound/acidnet_dataset",
        private=True,
        adapter_dir=adapter_dir,
        gguf_paths=(gguf_path,),
        dataset_files=(dataset_path,),
        manifest_path=manifest_path,
        metadata={
            "adapter_dir": hf_publish.portable_repo_path(adapter_dir),
            "gguf_paths": [hf_publish.portable_repo_path(gguf_path)],
            "dataset_files": [hf_publish.portable_repo_path(dataset_path)],
            "manifest_path": hf_publish.portable_repo_path(manifest_path),
            "promotion_status": "candidate",
            "promote_latest": False,
            "gate_summary": None,
            "model_repo_paths": {
                "readme": "README.md",
                "publish_manifest": "runs/portable-run/manifests/publish_manifest.json",
                "adapter_dir": "runs/portable-run/adapter",
                "gguf_paths": ["runs/portable-run/gguf/hf_publish.gguf"],
            },
            "dataset_repo_paths": {
                "readme": "README.md",
                "publish_manifest": "runs/portable-run/manifests/publish_manifest.json",
                "dataset_files": ["runs/portable-run/extras/hf_publish_dataset.jsonl"],
            },
        },
    )

    written = hf_publish.write_manifest(plan)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert payload["adapter_dir"] == "data/test_artifacts/hf_publish_adapter"
    assert payload["gguf_paths"] == ["data/test_artifacts/hf_publish.gguf"]
    assert payload["dataset_files"] == ["data/test_artifacts/hf_publish_dataset.jsonl"]
    assert payload["manifest_path"] == "data/test_artifacts/hf_publish_manifest.json"
    assert payload["promotion_status"] == "candidate"
    assert payload["promote_latest"] is False
    assert payload["model_repo_paths"]["readme"] == "README.md"
    assert payload["model_repo_paths"]["adapter_dir"] == "runs/portable-run/adapter"
    assert payload["dataset_repo_paths"]["readme"] == "README.md"
    assert payload["dataset_repo_paths"]["dataset_files"] == ["runs/portable-run/extras/hf_publish_dataset.jsonl"]


def test_build_publish_plan_adds_promoted_alias_when_requested(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("HF_TOKEN=hf_token\n", encoding="utf-8")
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    dataset_path = tmp_path / "train.jsonl"
    dataset_path.write_text('{"messages":[]}\n', encoding="utf-8")

    args = hf_publish.build_parser().parse_args(
        [
            "--env-file",
            str(env_path),
            "--run-name",
            "promoted-run",
            "--adapter-dir",
            str(adapter_dir),
            "--dataset-file",
            str(dataset_path),
            "--promotion-status",
            "promoted",
            "--promote-latest",
        ]
    )

    _, plan = hf_publish.build_publish_plan(args, process_env={})

    assert plan.metadata["promotion_status"] == "promoted"
    assert plan.metadata["promote_latest"] is True
    assert plan.metadata["model_repo_paths"]["promoted_latest"] == {
        "publish_manifest": "promoted/latest/manifests/publish_manifest.json",
        "adapter_dir": "promoted/latest/adapter",
    }
    assert plan.metadata["dataset_repo_paths"]["promoted_latest"] == {
        "publish_manifest": "promoted/latest/manifests/publish_manifest.json",
        "dataset_files": ["promoted/latest/extras/train.jsonl"],
    }
