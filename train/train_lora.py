from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collider.prompts import collide_messages, gate_messages, relate_messages


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_examples(
    paths: list[Path], tasks: set[str] | None = None
) -> list[tuple[list[dict[str, str]], str]]:
    examples = []
    for path in paths:
        for row in read_jsonl(path):
            task = row["task"]
            if tasks is not None and task not in tasks:
                continue
            target = json.dumps(row["output"], ensure_ascii=False, separators=(",", ":"))
            if task == "gate":
                messages = gate_messages(row["input"])
            elif task == "collide":
                messages = collide_messages(row["input"]["near"], row["input"]["far"])
            elif task == "relate":
                messages = relate_messages(row["input"]["near"], row["input"]["far"])
            else:
                continue
            examples.append((messages, target))
    return examples


def encode(tokenizer, messages, target, max_len: int) -> dict:
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    target_ids = tokenizer(target, add_special_tokens=False)["input_ids"] + [tokenizer.eos_token_id]
    input_ids = (prompt_ids + target_ids)[:max_len]
    labels = ([-100] * len(prompt_ids) + target_ids)[:max_len]
    return {"input_ids": input_ids, "labels": labels, "attention_mask": [1] * len(input_ids)}


class PadCollator:
    def __init__(self, pad_id: int, multiple: int = 8) -> None:
        self.pad_id = pad_id
        self.multiple = multiple

    def __call__(self, features: list[dict]) -> dict[str, torch.Tensor]:
        longest = max(len(feature["input_ids"]) for feature in features)
        if self.multiple:
            longest = ((longest + self.multiple - 1) // self.multiple) * self.multiple
        batch: dict[str, list[list[int]]] = {"input_ids": [], "labels": [], "attention_mask": []}
        for feature in features:
            pad = longest - len(feature["input_ids"])
            batch["input_ids"].append(feature["input_ids"] + [self.pad_id] * pad)
            batch["labels"].append(feature["labels"] + [-100] * pad)
            batch["attention_mask"].append(feature["attention_mask"] + [0] * pad)
        return {key: torch.tensor(value, dtype=torch.long) for key, value in batch.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate-train", default="data/gate_train.jsonl")
    parser.add_argument("--gate-dev", default="data/gate_dev.jsonl")
    parser.add_argument("--collide", default="data/collide_train.jsonl")
    parser.add_argument("--tasks", default="gate", help="逗号分隔:gate,collide")
    parser.add_argument("--base", default="artifacts/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--out", default="artifacts/qwen-collider-lora")
    parser.add_argument("--merged", default="artifacts/qwen-collider-merged")
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--max-len", type=int, default=384)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--no-merge", action="store_true")
    args = parser.parse_args()

    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    set_seed(args.seed)
    base = str(ROOT / args.base) if (ROOT / args.base).exists() else args.base
    tokenizer = AutoTokenizer.from_pretrained(base)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    tasks = {t.strip() for t in args.tasks.split(",") if t.strip()}
    train_rows = load_examples([ROOT / args.gate_train, ROOT / args.collide], tasks)
    dev_rows = load_examples([ROOT / args.gate_dev], {"gate"})
    train_set = [encode(tokenizer, m, t, args.max_len) for m, t in train_rows]
    dev_set = [encode(tokenizer, m, t, args.max_len) for m, t in dev_rows]

    use_cuda = torch.cuda.is_available()
    model = AutoModelForCausalLM.from_pretrained(
        base, dtype=torch.bfloat16 if use_cuda else torch.float32
    )
    model.config.use_cache = False
    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    model.print_trainable_parameters()

    out_dir = ROOT / args.out
    training_args = TrainingArguments(
        output_dir=str(out_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=10,
        logging_steps=10,
        gradient_checkpointing=True,
        eval_strategy="epoch",
        save_strategy="no",
        bf16=use_cuda,
        fp16=False,
        report_to="none",
        seed=args.seed,
        data_seed=args.seed,
        dataloader_num_workers=0,
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_set,
        eval_dataset=dev_set,
        data_collator=PadCollator(tokenizer.pad_token_id),
    )
    started = time.time()
    train_result = trainer.train()
    eval_result = trainer.evaluate()
    elapsed = round(time.time() - started, 1)

    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)

    merged_path = None
    if not args.no_merge:
        merged = model.merge_and_unload()
        merged_path = ROOT / args.merged
        merged.save_pretrained(merged_path)
        tokenizer.save_pretrained(merged_path)

    log = {
        "base": base,
        "adapter": str(out_dir),
        "merged": str(merged_path) if merged_path else None,
        "train_examples": len(train_set),
        "dev_examples": len(dev_set),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "grad_accum": args.grad_accum,
        "lr": args.lr,
        "train_loss": train_result.training_loss,
        "eval_loss": eval_result.get("eval_loss"),
        "elapsed_secs": elapsed,
        "steps": train_result.global_step,
    }
    runs = ROOT / "runs"
    runs.mkdir(exist_ok=True)
    (runs / "train_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(log, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
