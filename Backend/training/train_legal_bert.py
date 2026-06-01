import os
import torch
import logging
from datasets import load_from_disk
from transformers import (
    AutoTokenizer,
    AutoModelForQuestionAnswering,
    TrainingArguments,
    Trainer,
    DefaultDataCollator
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MODEL_NAME = "nlpaueb/legal-bert-base-uncased"
DATA_DIR = "./data/cuad"
OUTPUT_DIR = "./models/legal_bert_cuad"
BATCH_SIZE = 16
GRAD_ACCUM_STEPS = 2
EPOCHS = 5
LEARNING_RATE = 3e-5
MAX_LENGTH = 512
DOC_STRIDE = 128
MAX_UNANSWERABLE_RATIO = 1.5  # Keep at most 1.5x unanswerable vs answerable chunks


def main():
    logger.info("Initializing Legal-BERT fine-tuning for CUAD (Question Answering)...")

    # Check if GPU is available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    if not os.path.exists(DATA_DIR):
        logger.error(f"Dataset directory {DATA_DIR} not found. Please run data_prep.py first.")
        return

    # 1. Load Dataset
    logger.info("Loading CUAD dataset...")
    dataset = load_from_disk(DATA_DIR)

    # 2. Load Tokenizer and Model
    logger.info(f"Loading tokenizer and model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForQuestionAnswering.from_pretrained(MODEL_NAME)

    # 3. Preprocess with sliding window to handle long CUAD contracts
    def preprocess_function(examples):
        questions = [q.strip() for q in examples["question"]]
        inputs = tokenizer(
            questions,
            examples["context"],
            max_length=MAX_LENGTH,
            truncation="only_second",
            stride=DOC_STRIDE,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding="max_length",
        )

        # Map each chunk back to its original example
        sample_mapping = inputs.pop("overflow_to_sample_mapping")
        offset_mapping = inputs.pop("offset_mapping")
        answers = examples["answers"]

        start_positions = []
        end_positions = []

        for i, offsets in enumerate(offset_mapping):
            input_ids = inputs["input_ids"][i]
            # CLS token index for unanswerable
            cls_index = input_ids.index(tokenizer.cls_token_id)

            # Which original example this chunk belongs to
            sample_index = sample_mapping[i]
            answer = answers[sample_index]
            sequence_ids = inputs.sequence_ids(i)

            # If no answer, set label to CLS position
            if len(answer["answer_start"]) == 0 or answer["text"][0] == "":
                start_positions.append(cls_index)
                end_positions.append(cls_index)
                continue

            # Use first answer
            start_char = answer["answer_start"][0]
            end_char = start_char + len(answer["text"][0])

            # Find the start and end of the context in this chunk
            token_start_index = 0
            while sequence_ids[token_start_index] != 1:
                token_start_index += 1
            context_start = token_start_index

            token_end_index = len(input_ids) - 1
            while sequence_ids[token_end_index] != 1:
                token_end_index -= 1
            context_end = token_end_index

            # If the answer is not fully inside this chunk's context window, label as CLS (unanswerable for this chunk)
            if offsets[context_start][0] > start_char or offsets[context_end][1] < end_char:
                start_positions.append(cls_index)
                end_positions.append(cls_index)
            else:
                # Find the start token position
                idx = context_start
                while idx <= context_end and offsets[idx][0] <= start_char:
                    idx += 1
                start_positions.append(idx - 1)

                # Find the end token position (walk forward to find the last token covering end_char)
                idx = context_start
                while idx <= context_end and offsets[idx][1] < end_char:
                    idx += 1
                end_positions.append(idx)

        inputs["start_positions"] = start_positions
        inputs["end_positions"] = end_positions
        return inputs

    logger.info("Tokenizing dataset with sliding window (stride=%d, max_length=%d)...", DOC_STRIDE, MAX_LENGTH)
    try:
        tokenized_datasets = dataset.map(
            preprocess_function,
            batched=True,
            remove_columns=dataset["train"].column_names,
        )
    except Exception as e:
        logger.warning(f"Failed to tokenize dataset. Ensure CUAD format matches SQuAD. Error: {e}")
        return

    # ============================================================
    # TWO-STAGE TRAINING PIPELINE
    # Stage 1: Answerable-only (teaches span extraction)
    # Stage 2: Balanced data (teaches answer vs no-answer)
    # ============================================================

    import random
    random.seed(42)

    eval_split = "validation" if "validation" in tokenized_datasets else "test"

    def get_indices_by_label(ds):
        """Fast column-level access to get answerable/unanswerable indices."""
        start_positions = ds["start_positions"]
        answerable = [i for i, s in enumerate(start_positions) if s != 0]
        unanswerable = [i for i, s in enumerate(start_positions) if s == 0]
        return answerable, unanswerable

    def balance_split(ds, split_name, ratio=MAX_UNANSWERABLE_RATIO):
        """Subsample unanswerable chunks to maintain target ratio."""
        ans_idx, unans_idx = get_indices_by_label(ds)
        n_ans, n_unans = len(ans_idx), len(unans_idx)
        logger.info(
            f"{split_name}: {len(ds)} chunks, "
            f"{n_ans} answerable ({100*n_ans/len(ds):.1f}%), "
            f"{n_unans} unanswerable ({100*n_unans/len(ds):.1f}%)"
        )
        max_unans = int(n_ans * ratio)
        if n_unans > max_unans:
            logger.info(f"  Subsampling unanswerable: {n_unans} -> {max_unans}")
            sampled = random.sample(unans_idx, max_unans)
            ds = ds.select(sorted(ans_idx + sampled))
            logger.info(f"  Balanced: {len(ds)} chunks")
        return ds

    data_collator = DefaultDataCollator()

    # --- STAGE 1: Answerable-only training ---
    logger.info("=" * 60)
    logger.info("STAGE 1: Training on answerable chunks only (span extraction)")
    logger.info("=" * 60)

    train_ans, _ = get_indices_by_label(tokenized_datasets["train"])
    eval_ans, _ = get_indices_by_label(tokenized_datasets[eval_split])

    stage1_train = tokenized_datasets["train"].select(train_ans)
    stage1_eval = tokenized_datasets[eval_split].select(eval_ans)

    logger.info(f"Stage 1 data - Train: {len(stage1_train)} chunks, Eval: {len(stage1_eval)} chunks")

    stage1_args = TrainingArguments(
        output_dir=os.path.join(OUTPUT_DIR, "stage1"),
        eval_strategy="epoch",
        learning_rate=3e-5,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM_STEPS,
        num_train_epochs=3,
        weight_decay=0.01,
        warmup_ratio=0.15,
        push_to_hub=False,
        fp16=torch.cuda.is_available(),
        logging_steps=50,
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        dataloader_num_workers=2,
    )

    trainer_s1 = Trainer(
        model=model,
        args=stage1_args,
        train_dataset=stage1_train,
        eval_dataset=stage1_eval,
        processing_class=tokenizer,
        data_collator=data_collator,
    )

    logger.info("Starting Stage 1 training...")
    trainer_s1.train()
    logger.info("Stage 1 complete! Model has learned span extraction.")

    # --- STAGE 2: Balanced training ---
    logger.info("=" * 60)
    logger.info("STAGE 2: Training on balanced data (answer vs no-answer)")
    logger.info("=" * 60)

    stage2_train = balance_split(tokenized_datasets["train"], "Stage 2 Training set")
    stage2_eval = balance_split(tokenized_datasets[eval_split], "Stage 2 Eval set")

    stage2_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        eval_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM_STEPS,
        num_train_epochs=5,
        weight_decay=0.01,
        warmup_ratio=0.05,
        push_to_hub=False,
        fp16=torch.cuda.is_available(),
        logging_steps=50,
        save_strategy="epoch",
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        dataloader_num_workers=2,
    )

    trainer_s2 = Trainer(
        model=model,  # Already has Stage 1 span extraction weights
        args=stage2_args,
        train_dataset=stage2_train,
        eval_dataset=stage2_eval,
        processing_class=tokenizer,
        data_collator=data_collator,
    )

    logger.info("Starting Stage 2 training...")
    trainer_s2.train()

    # Save final model
    logger.info(f"Saving fine-tuned model to {OUTPUT_DIR}...")
    trainer_s2.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    logger.info("Two-stage training complete!")


if __name__ == "__main__":
    main()
