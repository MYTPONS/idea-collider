import pytest

torch = pytest.importorskip("torch")

from train.train_lora import PadCollator, encode


class FakeTokenizer:
    eos_token_id = 9
    pad_token_id = 0

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        return "PROMPT"

    def __call__(self, text, add_special_tokens=False):
        mapping = {"PROMPT": [1, 2, 3], "TARGET": [4, 5]}
        return {"input_ids": mapping[text]}


def test_encode_masks_prompt_tokens():
    feature = encode(FakeTokenizer(), [{"role": "user", "content": "x"}], "TARGET", 128)
    assert feature["input_ids"] == [1, 2, 3, 4, 5, 9]
    assert feature["labels"] == [-100, -100, -100, 4, 5, 9]
    assert feature["attention_mask"] == [1, 1, 1, 1, 1, 1]


def test_encode_truncates_both_sequences():
    feature = encode(FakeTokenizer(), [{"role": "user", "content": "x"}], "TARGET", 5)
    assert feature["input_ids"] == [1, 2, 3, 4, 5]
    assert feature["labels"] == [-100, -100, -100, 4, 5]


def test_collator_pads_labels_with_ignore_index():
    batch = PadCollator(pad_id=0, multiple=4)(
        [
            {"input_ids": [1, 2], "labels": [1, 2], "attention_mask": [1, 1]},
            {"input_ids": [1], "labels": [1], "attention_mask": [1]},
        ]
    )
    assert batch["input_ids"].tolist() == [[1, 2, 0, 0], [1, 0, 0, 0]]
    assert batch["labels"].tolist() == [[1, 2, -100, -100], [1, -100, -100, -100]]
    assert batch["attention_mask"].tolist() == [[1, 1, 0, 0], [1, 0, 0, 0]]
    assert batch["labels"].dtype == torch.long
