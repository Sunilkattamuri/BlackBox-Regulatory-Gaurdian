import os
import torch
import logging
import numpy as np
from datasets import load_from_disk
from transformers import (
    LayoutLMv3Processor,
    LayoutLMv3ForTokenClassification,
    TrainingArguments,
    Trainer
)
import evaluate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MODEL_NAME = "microsoft/layoutlmv3-base"
DATA_DIR = "./data/doclaynet"
OUTPUT_DIR = "./models/layoutlmv3_doclaynet"
BATCH_SIZE = 4
EPOCHS = 3
LEARNING_RATE = 1e-5

def main():
    logger.info("Initializing LayoutLMv3 fine-tuning for DocLayNet...")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    
    if not os.path.exists(DATA_DIR):
        logger.error(f"Dataset directory {DATA_DIR} not found. Please run data_prep.py first.")
        return

    # 1. Load Dataset
    logger.info("Loading DocLayNet dataset...")
    dataset = load_from_disk(DATA_DIR)
    
    # Check if 'train' split exists, if not, find the first split or use the dataset itself
    train_split = None
    eval_split = None
    if hasattr(dataset, "keys"):
        # It is a DatasetDict
        for split in ["train", "test", "validation", "val"]:
            if split in dataset:
                train_split = split
                break
        if train_split is None and len(dataset.keys()) > 0:
            train_split = list(dataset.keys())[0]
            
        # Try to find a validation split that is different from train_split
        for split in ["validation", "val", "test", "train"]:
            if split in dataset and split != train_split:
                eval_split = split
                break
            
    if train_split is not None:
        logger.info(f"Using '{train_split}' split as the training dataset.")
        train_dataset_raw = dataset[train_split]
    else:
        logger.info("Assuming dataset object itself is the train dataset.")
        train_dataset_raw = dataset
        
    if eval_split is not None:
        logger.info(f"Using '{eval_split}' split as the evaluation dataset.")
        eval_dataset_raw = dataset[eval_split]
    else:
        logger.info("No separate evaluation dataset split found.")
        eval_dataset_raw = None
        
    # Define labels (DocLayNet specific, e.g., Text, Title, List, Table, Figure)
    try:
        if "category" in train_dataset_raw.features:
            label_list = train_dataset_raw.features["category"].names
        elif "category_id" in train_dataset_raw.features:
            label_list = train_dataset_raw.features["category_id"].feature.names if hasattr(train_dataset_raw.features["category_id"], "feature") else train_dataset_raw.features["category_id"].names
        else:
            label_list = ["Caption", "Footnote", "Formula", "List-item", "Page-footer", "Page-header", "Picture", "Section-header", "Table", "Text", "Title"]
    except:
        label_list = ["Caption", "Footnote", "Formula", "List-item", "Page-footer", "Page-header", "Picture", "Section-header", "Table", "Text", "Title"]
        
    id2label = {i: label for i, label in enumerate(label_list)}
    label2id = {label: i for i, label in enumerate(label_list)}
    
    # 2. Load Processor and Model
    logger.info(f"Loading processor and model: {MODEL_NAME}")
    processor = LayoutLMv3Processor.from_pretrained(MODEL_NAME, apply_ocr=False)
    model = LayoutLMv3ForTokenClassification.from_pretrained(
        MODEL_NAME, 
        id2label=id2label, 
        label2id=label2id
    )

    # 3. Preprocess Function
    def preprocess_function(examples):
        # Dynamically map the columns in DocLayNet to LayoutLMv3 expected inputs
        images = examples["image"]
        batch_size = len(images)
        
        # We need to build words, boxes, and word_labels for each example in the batch
        batch_words = []
        batch_boxes = []
        batch_word_labels = []
        
        for i in range(batch_size):
            words = []
            boxes = []
            word_labels = []
            
            # If the dataset already has 'tokens', use them
            if "tokens" in examples:
                words = examples["tokens"][i]
                boxes = examples["bboxes"][i]
                if "ner_tags" in examples:
                    # Clip tags to be within range [0, len(label_list) - 1]
                    word_labels = [max(0, min(len(label_list) - 1, tag)) for tag in examples["ner_tags"][i]]
                else:
                    word_labels = [0] * len(words)
            else:
                # Extract from pdf_cells and bboxes
                pdf_cells = examples["pdf_cells"][i] if "pdf_cells" in examples else []
                category_ids = examples["category_id"][i] if "category_id" in examples else []
                bboxes = examples["bboxes"][i] if "bboxes" in examples else []
                
                # Each paragraph/box in bboxes has a corresponding category_id
                # pdf_cells is a list of lists of cells for each bbox
                for box_idx, box in enumerate(bboxes):
                    cat_id = category_ids[box_idx] if box_idx < len(category_ids) else 0
                    # DocLayNet category IDs are 1-indexed (1 to 11). Map to 0-indexed (0 to 10) to avoid GPU index out of bounds.
                    if isinstance(cat_id, int):
                        if 1 <= cat_id <= len(label_list):
                            cat_id = cat_id - 1
                        else:
                            cat_id = 0
                    else:
                        cat_id = 0
                    
                    # Get cells for this box
                    cells = pdf_cells[box_idx] if box_idx < len(pdf_cells) else []
                    
                    # A cell can be a dict or a string or a list. Let's handle all gracefully
                    if isinstance(cells, list):
                        for cell in cells:
                            if isinstance(cell, dict):
                                text = cell.get("text", "")
                                c_box = cell.get("bbox", box)
                            elif isinstance(cell, str):
                                text = cell
                                c_box = box
                            else:
                                text = str(cell)
                                c_box = box
                                
                            if text.strip():
                                words.append(text)
                                boxes.append(c_box)
                                word_labels.append(cat_id)
                    elif isinstance(cells, dict):
                        text = cells.get("text", "")
                        c_box = cells.get("bbox", box)
                        if text.strip():
                            words.append(text)
                            boxes.append(c_box)
                            word_labels.append(cat_id)
                    elif isinstance(cells, str):
                        if cells.strip():
                            words.append(cells)
                            boxes.append(box)
                            word_labels.append(cat_id)
                            
                # Fallback if no words were extracted
                if not words:
                    words = ["empty"]
                    boxes = [[0, 0, 0, 0]]
                    word_labels = [0]
                    
            batch_words.append(words)
            batch_boxes.append(boxes)
            batch_word_labels.append(word_labels)
            
        # LayoutLMv3Processor expects boxes coordinates normalized to 0-1000
        normalized_batch_boxes = []
        for i, boxes in enumerate(batch_boxes):
            norm_boxes = []
            img = images[i]
            width, height = img.size if hasattr(img, "size") else (1000, 1000)
            
            for box in boxes:
                # LayoutLMv3 expects: [x0, y0, x1, y1] scaled to 1000
                if len(box) == 4:
                    x0, y0, x1, y1 = box[0], box[1], box[2], box[3]
                    # If x1 and y1 are width/height (COCO [x, y, w, h]), convert to [x0, y0, x1, y1]
                    if x1 < x0 or y1 < y0:
                        x1 = x0 + x1
                        y1 = y0 + y1
                    
                    # Scale to 1000
                    x0 = int(1000 * (x0 / width))
                    y0 = int(1000 * (y0 / height))
                    x1 = int(1000 * (x1 / width))
                    y1 = int(1000 * (y1 / height))
                    
                    # Clip to 0-1000
                    x0 = max(0, min(1000, x0))
                    y0 = max(0, min(1000, y0))
                    x1 = max(0, min(1000, x1))
                    y1 = max(0, min(1000, y1))
                    norm_boxes.append([x0, y0, x1, y1])
                else:
                    norm_boxes.append([0, 0, 0, 0])
            normalized_batch_boxes.append(norm_boxes)
            
        encoding = processor(
            images, 
            batch_words, 
            boxes=normalized_batch_boxes, 
            word_labels=batch_word_labels,
            truncation=True, 
            padding="max_length"
        )
        return encoding

    logger.info("Tokenizing and processing dataset...")
    try:
        train_dataset = train_dataset_raw.map(
            preprocess_function, 
            batched=True, 
            remove_columns=train_dataset_raw.column_names
        )
        if eval_dataset_raw is not None:
            eval_dataset = eval_dataset_raw.map(
                preprocess_function,
                batched=True,
                remove_columns=eval_dataset_raw.column_names
            )
        else:
            eval_dataset = None
    except Exception as e:
        logger.warning(f"Failed to process dataset. Detailed mapping depends on DocLayNet columns. Error: {e}")
        return

    # 4. Metrics
    metric = evaluate.load("seqeval")
    def compute_metrics(p):
        predictions, labels = p
        predictions = np.argmax(predictions, axis=2)

        # Remove ignored index (special tokens)
        true_predictions = [
            [label_list[p] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]
        true_labels = [
            [label_list[l] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]

        results = metric.compute(predictions=true_predictions, references=true_labels)
        return {
            "precision": results["overall_precision"],
            "recall": results["overall_recall"],
            "f1": results["overall_f1"],
            "accuracy": results["overall_accuracy"],
        }

    # 5. Training Arguments
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        max_steps=1000, # Using max_steps instead of epochs for quicker prototype testing
        eval_strategy="steps",
        eval_steps=200,
        learning_rate=LEARNING_RATE,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        weight_decay=0.01,
        push_to_hub=False,
        fp16=torch.cuda.is_available(),
        remove_unused_columns=False # Important for LayoutLM
    )

    # 6. Initialize Trainer
    from transformers import default_data_collator
    if eval_dataset is None:
        logger.info("No evaluation dataset provided. Overriding eval_strategy to 'no'.")
        training_args.eval_strategy = "no"
        
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=processor, # Using processor
        data_collator=default_data_collator,
        compute_metrics=compute_metrics
    )

    # 7. Train
    logger.info("Starting LayoutLMv3 training...")
    trainer.train()
    
    # 8. Save
    logger.info(f"Saving fine-tuned model to {OUTPUT_DIR}...")
    trainer.save_model(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)
    logger.info("Training complete!")

if __name__ == "__main__":
    main()
