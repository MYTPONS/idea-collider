from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import torch

from . import prompts
from .schema import ALL_AXES, AXIS_GROUP
from .textutil import first_json_object

ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = ROOT / "artifacts" / "Qwen2.5-0.5B-Instruct"
ADAPTER_DIR = ROOT / "artifacts" / "qwen-collider-lora"
MERGED_DIR = ROOT / "artifacts" / "qwen-collider-merged"
HF_BASE = "Qwen/Qwen2.5-0.5B-Instruct"

_LABEL_ALIASES = {
    "constraint": "constraint",
    "约束": "constraint",
    "pain": "pain",
    "痛点": "pain",
}

_AXIS_ALIASES = {
    "可用性": "availability",
    "成本": "cost",
    "版本": "version",
    "信任": "trust",
    "合规": "compliance",
    "时间": "time",
    "空间": "space",
    "市场": "market",
    "供给侧": "supply",
    "网络": "network",
    "已观察事实": "observation",
    "预测": "prediction",
    "感受": "feeling",
    "功能条目": "feature",
    "愿望": "wish",
}


def resolve_model(model_dir: str | None = None) -> tuple[str, str]:
    if model_dir:
        if model_dir == "base":
            return "base", str(BASE_DIR) if BASE_DIR.exists() else HF_BASE
        path = Path(model_dir)
        if (path / "adapter_config.json").exists():
            return "adapter", str(path)
        return "merged", str(path)
    env = os.environ.get("COLLIDER_MODEL_DIR")
    if env:
        return resolve_model(env)
    if MERGED_DIR.exists():
        return "merged", str(MERGED_DIR)
    if ADAPTER_DIR.exists():
        return "adapter", str(ADAPTER_DIR)
    return "base", str(BASE_DIR) if BASE_DIR.exists() else HF_BASE


def _normalize_label(value: Any) -> str | None:
    return _LABEL_ALIASES.get(str(value or "").strip().lower())


def _normalize_axis(value: Any) -> str | None:
    text = str(value or "").strip()
    if text in ALL_AXES:
        return text
    return _AXIS_ALIASES.get(text)


class LocalModel:
    def __init__(
        self,
        model_dir: str | None = None,
        base_model: str | None = None,
        device: str | None = None,
    ) -> None:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.kind, self.path = resolve_model(model_dir)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        if self.device.type == "cuda":
            self.dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            self.dtype = torch.float32

        base = base_model or (str(BASE_DIR) if BASE_DIR.exists() else HF_BASE)
        if self.kind == "merged":
            self.tokenizer = AutoTokenizer.from_pretrained(self.path)
            self.model = AutoModelForCausalLM.from_pretrained(self.path, dtype=self.dtype)
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(base)
            self.model = AutoModelForCausalLM.from_pretrained(base, dtype=self.dtype)
            if self.kind == "adapter":
                from peft import PeftModel

                self.model = PeftModel.from_pretrained(self.model, self.path)
        self.model.to(self.device)
        self.model.eval()
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def describe(self) -> str:
        name = Path(self.path).name if Path(self.path).exists() else Path(self.path).name
        return f"{self.kind}:{name}"

    def generate(
        self,
        messages: list[dict[str, str]],
        max_new_tokens: int = 128,
        sample: bool = False,
        temperature: float = 0.9,
        top_p: float = 0.95,
    ) -> str:
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        enc = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
        enc = {key: value.to(self.device) for key, value in enc.items()}
        kwargs: dict[str, Any] = {"do_sample": sample}
        if sample:
            kwargs["temperature"] = temperature
            kwargs["top_p"] = top_p
        with torch.inference_mode():
            out = self.model.generate(
                **enc,
                max_new_tokens=max_new_tokens,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                **kwargs,
            )
        generated = out[0][enc["input_ids"].shape[-1] :]
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()

    def classify(self, text: str) -> dict[str, Any]:
        raw = self.generate(prompts.gate_messages(text), max_new_tokens=96)
        obj = first_json_object(raw)
        if obj is None:
            return {"label": None, "axis": None, "why": "", "raw": raw, "error": "unparseable"}
        label = _normalize_label(obj.get("label"))
        axis = _normalize_axis(obj.get("axis"))
        why = str(obj.get("why", "")).strip()
        if label is None:
            return {"label": None, "axis": axis, "why": why, "raw": raw, "error": "bad_label"}
        if axis is not None and AXIS_GROUP[axis] != label:
            axis = None
        return {"label": label, "axis": axis, "why": why, "raw": raw, "error": None}

    def collide(self, near_text: str, far_text: str) -> dict[str, Any]:
        raw = self.generate(
            prompts.collide_messages(near_text, far_text),
            max_new_tokens=320,
            sample=True,
        )
        obj = first_json_object(raw)
        if obj is None:
            return {
                "interaction": None,
                "must": "",
                "form": "",
                "why": "",
                "raw": raw,
                "error": "unparseable",
            }
        value = obj.get("interaction")
        if isinstance(value, str):
            value = value.strip().lower() in ("true", "yes", "1", "是")
        if not isinstance(value, bool):
            return {
                "interaction": None,
                "must": "",
                "form": "",
                "why": "",
                "raw": raw,
                "error": "bad_interaction",
            }
        return {
            "interaction": value,
            "must": str(obj.get("must", "")).strip(),
            "form": str(obj.get("form", "")).strip(),
            "why": str(obj.get("why", "")).strip(),
            "raw": raw,
            "error": None,
        }

    def relate(self, near_text: str, far_text: str) -> dict[str, Any]:
        raw = self.generate(prompts.relate_messages(near_text, far_text), max_new_tokens=24)
        obj = first_json_object(raw)
        if obj is None:
            return {"related": None, "raw": raw, "error": "unparseable"}
        value = obj.get("related")
        if isinstance(value, str):
            value = value.strip().lower() in ("true", "yes", "1", "是")
        if not isinstance(value, bool):
            return {"related": None, "raw": raw, "error": "bad_value"}
        return {"related": value, "raw": raw, "error": None}
