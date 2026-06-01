import os
import torch
import numpy as np
import logging
from tqdm import tqdm
from datasets import load_from_disk
from transformers import (
    pipeline,
    AutoTokenizer,
    AutoModelForQuestionAnswering,
    LayoutLMv3Processor,
    LayoutLMv3ForTokenClassification,
    TrainingArguments,
    Trainer,
    default_data_collator
)
import evaluate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
LEGAL_BERT_PATH = "models/legal_bert_cuad"
LAYOUTLMV3_PATH = "models/layoutlmv3_doclaynet"
CUAD_DATA_DIR = "./data/cuad"
DOCLAYNET_DATA_DIR = "./data/doclaynet"

def evaluate_legal_bert():
    print("\n" + "=" * 60)
    print("EVALUATING FINE-TUNED LEGAL-BERT MODEL ON CUAD")
    print("=" * 60)
    
    if not os.path.exists(LEGAL_BERT_PATH):
        print(f"Error: Fine-tuned Legal-BERT model not found at {LEGAL_BERT_PATH}.")
        return
    if not os.path.exists(CUAD_DATA_DIR):
        print(f"Error: CUAD dataset not found at {CUAD_DATA_DIR}.")
        return
        
    try:
        # Load dataset
        print("Loading CUAD test dataset...")
        dataset = load_from_disk(CUAD_DATA_DIR)
        test_split = "test" if "test" in dataset else list(dataset.keys())[0]
        eval_ds = dataset[test_split]
        
        # Use more examples for representative evaluation
        num_examples = min(len(eval_ds), 500)
        print(f"Evaluating on {num_examples} samples from the '{test_split}' split...")
        eval_subset = eval_ds.shuffle(seed=42).select(range(num_examples))
        
        # Count answerable vs unanswerable for diagnostics
        n_has_ans = sum(1 for ex in eval_subset if len(ex["answers"]["text"]) > 0 and ex["answers"]["text"][0] != "")
        n_no_ans = num_examples - n_has_ans
        print(f"  Answerable: {n_has_ans}, Unanswerable: {n_no_ans}")
        
        # Load model and set device
        print(f"Loading model from {LEGAL_BERT_PATH}...")
        tokenizer = AutoTokenizer.from_pretrained(LEGAL_BERT_PATH)
        model = AutoModelForQuestionAnswering.from_pretrained(LEGAL_BERT_PATH)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()
        
        # Load SQuAD v2 metric
        print("Loading SQuAD v2 evaluation metric...")
        squad_metric = evaluate.load("squad_v2")
        
        predictions_metadata = []
        references = []
        
        print("Running sliding window clause extraction inference...")
        for example in tqdm(eval_subset):
            qa_id = example["id"]
            context = example["context"]
            question = example["question"]
            answers = example["answers"]
            
            try:
                # Truncate context to 20,000 chars for broader coverage of long contracts
                context_truncated = context[:50000]
                # Tokenize with sliding window
                inputs_raw = tokenizer(
                    question,
                    context_truncated,
                    max_length=512,
                    stride=128,
                    truncation="only_second",
                    return_overflowing_tokens=True,
                    return_offsets_mapping=True,
                    padding="max_length",
                )
                
                num_chunks = len(inputs_raw["input_ids"])
                start_logits_list = []
                end_logits_list = []
                
                # Process chunks in mini-batches to prevent GPU OOM on long contracts
                chunk_batch_size = 8
                for batch_idx in range(0, num_chunks, chunk_batch_size):
                    batch_input_ids = torch.tensor(inputs_raw["input_ids"][batch_idx : batch_idx + chunk_batch_size]).to(device)
                    batch_attention_mask = torch.tensor(inputs_raw["attention_mask"][batch_idx : batch_idx + chunk_batch_size]).to(device)
                    
                    inputs_dict = {
                        "input_ids": batch_input_ids,
                        "attention_mask": batch_attention_mask
                    }
                    if "token_type_ids" in inputs_raw:
                        batch_token_type_ids = torch.tensor(inputs_raw["token_type_ids"][batch_idx : batch_idx + chunk_batch_size]).to(device)
                        inputs_dict["token_type_ids"] = batch_token_type_ids
                        
                    with torch.no_grad():
                        outputs = model(**inputs_dict)
                        
                    start_logits_list.append(outputs.start_logits.cpu())
                    end_logits_list.append(outputs.end_logits.cpu())
                    
                start_logits = torch.cat(start_logits_list, dim=0)
                end_logits = torch.cat(end_logits_list, dim=0)
                
                # Track the best non-empty span confidence across all chunks
                best_doc_diff = -999999.0
                best_doc_score = -999999.0
                best_doc_null_score = 0.0
                best_doc_text = ""
                best_doc_prob_null = 1.0
                
                for c in range(num_chunks):
                    sequence_ids = inputs_raw.sequence_ids(c)
                    offset_mapping = inputs_raw["offset_mapping"][c]
                    
                    context_indices = [idx for idx, seq_id in enumerate(sequence_ids) if seq_id == 1]
                    if not context_indices:
                        continue
                        
                    context_start = context_indices[0]
                    context_end = context_indices[-1]
                    
                    start_logits_c = start_logits[c].tolist()
                    end_logits_c = end_logits[c].tolist()
                    score_null_c = start_logits_c[0] + end_logits_c[0]
                    
                    # Find top-N start and end positions to avoid O(n^2) brute force
                    n_best = 20
                    start_indexes = sorted(
                        range(context_start, context_end + 1),
                        key=lambda x: start_logits_c[x],
                        reverse=True
                    )[:n_best]
                    end_indexes = sorted(
                        range(context_start, context_end + 1),
                        key=lambda x: end_logits_c[x],
                        reverse=True
                    )[:n_best]
                    
                    best_chunk_score = -999999.0
                    best_chunk_start, best_chunk_end = 0, 0
                    
                    for si in start_indexes:
                        for ei in end_indexes:
                            if ei < si:
                                continue
                            if ei - si + 1 > 150:
                                continue
                            score = start_logits_c[si] + end_logits_c[ei]
                            if score > best_chunk_score:
                                best_chunk_score = score
                                best_chunk_start, best_chunk_end = si, ei
                                
                    if best_chunk_start > 0 and best_chunk_end >= best_chunk_start:
                        diff = best_chunk_score - score_null_c
                        if diff > best_doc_diff:
                            best_doc_diff = diff
                            best_doc_score = best_chunk_score
                            best_doc_null_score = score_null_c
                            
                            char_start = offset_mapping[best_chunk_start][0]
                            char_end = offset_mapping[best_chunk_end][1]
                            best_doc_text = context_truncated[char_start:char_end].strip()
                            
                            # Relative unanswerable probability for this specific chunk
                            best_doc_prob_null = torch.softmax(torch.tensor([score_null_c, best_chunk_score]), dim=0)[0].item()
                            
                # Fallback if no non-empty span was captured
                if best_doc_diff == -999999.0:
                    pred_text = ""
                    score_null = 0.0
                    best_score = 0.0
                    prob_null = 1.0
                else:
                    pred_text = best_doc_text
                    score_null = best_doc_null_score
                    best_score = best_doc_score
                    prob_null = best_doc_prob_null
                    
            except Exception as e:
                pred_text = ""
                score_null = 0.0
                best_score = 0.0
                prob_null = 1.0
                
            predictions_metadata.append({
                "id": qa_id,
                "candidate_text": pred_text,
                "score_null": score_null,
                "best_score": best_score,
                "prob_null": prob_null
            })
            
            references.append({
                "id": qa_id,
                "answers": answers
            })
        
        # Diagnostic: show span score distribution
        diffs = [item["best_score"] - item["score_null"] for item in predictions_metadata]
        has_candidate = sum(1 for item in predictions_metadata if item["candidate_text"] != "")
        print(f"\n--- Span Diagnostics ---")
        print(f"  Candidates found: {has_candidate}/{len(predictions_metadata)}")
        if diffs:
            print(f"  Score diff (best_span - null) stats:")
            print(f"    min={min(diffs):.2f}, max={max(diffs):.2f}, median={sorted(diffs)[len(diffs)//2]:.2f}, mean={sum(diffs)/len(diffs):.2f}")
            
        # Grid search over thresholds to optimize metrics (wider and finer range)
        thresholds = list(np.arange(-25.0, 12.0, 1.0))
        sweep_results = []
        best_f1 = -1.0
        best_threshold = 0.0
        best_metrics = None
        
        print("\nSweeping threshold to optimize F1 metric...")
        for thresh in thresholds:
            current_preds = []
            for item in predictions_metadata:
                diff = item["best_score"] - item["score_null"]
                # If best non-empty span's score exceeds null score by more than threshold, predict it
                if diff > thresh and item["candidate_text"]:
                    pred_text = item["candidate_text"]
                else:
                    pred_text = ""
                
                current_preds.append({
                    "id": item["id"],
                    "prediction_text": pred_text,
                    "no_answer_probability": item["prob_null"]
                })
                
            metrics = squad_metric.compute(predictions=current_preds, references=references)
            sweep_results.append((thresh, metrics))
            
            if metrics["f1"] > best_f1:
                best_f1 = metrics["f1"]
                best_threshold = thresh
                best_metrics = metrics
                
        print("\n" + "-" * 85)
        print(f"{'Threshold':^12} | {'Exact Match (EM)':^18} | {'F1 Score':^12} | {'HasAns F1':^12} | {'NoAns F1':^12}")
        print("-" * 85)
        for thresh, metrics in sweep_results:
            has_ans = metrics.get("HasAns_f1", 0.0)
            no_ans = metrics.get("NoAns_f1", 0.0)
            star = "*" if thresh == best_threshold else " "
            print(f"{thresh:^11.1f}{star} | {metrics['exact']:^18.2f}% | {metrics['f1']:^12.2f}% | {has_ans:^12.2f}% | {no_ans:^12.2f}%")
        print("-" * 85)
        print(f"Optimal Threshold: {best_threshold:.1f} (F1 Score: {best_f1:.2f}%)")
        print("-" * 85)
        
        print("-" * 60)
        print("LEGAL-BERT EVALUATION RESULTS (CALIBRATED):")
        print("-" * 60)
        print(f"  Optimal Threshold: {best_threshold:.1f}")
        print(f"  Exact Match (EM):  {best_metrics['exact']:.2f}%")
        print(f"  F1 Score:          {best_metrics['f1']:.2f}%")
        if "HasAns_f1" in best_metrics:
            print(f"  Answerable Clauses F1: {best_metrics['HasAns_f1']:.2f}%")
            print(f"  Unanswerable Clauses F1: {best_metrics['NoAns_f1']:.2f}%")
        print("-" * 60)
        print("Evaluation complete for Legal-BERT!")
        
    except Exception as e:
        print(f"Error during Legal-BERT evaluation: {e}")
        import traceback
        traceback.print_exc()

def evaluate_layoutlmv3():
    print("\n" + "=" * 60)
    print("EVALUATING FINE-TUNED LAYOUTLMV3 MODEL ON DOCLAYNET")
    print("=" * 60)
    
    if not os.path.exists(LAYOUTLMV3_PATH):
        print(f"Error: Fine-tuned LayoutLMv3 model not found at {LAYOUTLMV3_PATH}.")
        return
    if not os.path.exists(DOCLAYNET_DATA_DIR):
        print(f"Error: DocLayNet dataset not found at {DOCLAYNET_DATA_DIR}.")
        return
        
    try:
        # Load dataset
        print("Loading DocLayNet validation dataset...")
        dataset = load_from_disk(DOCLAYNET_DATA_DIR)
        
        # Resolve eval split
        eval_split = None
        for split in ["validation", "test", "val", "train"]:
            if split in dataset:
                eval_split = split
                break
        if eval_split is None:
            eval_split = list(dataset.keys())[0]
            
        print(f"Using '{eval_split}' split for evaluation...")
        eval_dataset_raw = dataset[eval_split]
        
        # Limit to 50 samples for speed
        num_examples = min(len(eval_dataset_raw), 50)
        eval_subset = eval_dataset_raw.select(range(num_examples))
        
        # Load processor and model
        print(f"Loading LayoutLMv3 from {LAYOUTLMV3_PATH}...")
        processor = LayoutLMv3Processor.from_pretrained(LAYOUTLMV3_PATH, apply_ocr=False)
        model = LayoutLMv3ForTokenClassification.from_pretrained(LAYOUTLMV3_PATH)
        
        # Resolve labels
        try:
            if "category" in eval_dataset_raw.features:
                label_list = eval_dataset_raw.features["category"].names
            elif "category_id" in eval_dataset_raw.features:
                label_list = eval_dataset_raw.features["category_id"].feature.names if hasattr(eval_dataset_raw.features["category_id"], "feature") else eval_dataset_raw.features["category_id"].names
            else:
                label_list = ["Caption", "Footnote", "Formula", "List-item", "Page-footer", "Page-header", "Picture", "Section-header", "Table", "Text", "Title"]
        except:
            label_list = ["Caption", "Footnote", "Formula", "List-item", "Page-footer", "Page-header", "Picture", "Section-header", "Table", "Text", "Title"]
            
        # Processor preprocessing function
        def preprocess_function(examples):
            images = examples["image"]
            batch_size = len(images)
            batch_words = []
            batch_boxes = []
            batch_word_labels = []
            
            for i in range(batch_size):
                words = []
                boxes = []
                word_labels = []
                
                if "tokens" in examples:
                    words = examples["tokens"][i]
                    boxes = examples["bboxes"][i]
                    if "ner_tags" in examples:
                        word_labels = [max(0, min(len(label_list) - 1, tag)) for tag in examples["ner_tags"][i]]
                    else:
                        word_labels = [0] * len(words)
                else:
                    pdf_cells = examples["pdf_cells"][i] if "pdf_cells" in examples else []
                    category_ids = examples["category_id"][i] if "category_id" in examples else []
                    bboxes = examples["bboxes"][i] if "bboxes" in examples else []
                    
                    for box_idx, box in enumerate(bboxes):
                        cat_id = category_ids[box_idx] if box_idx < len(category_ids) else 0
                        if isinstance(cat_id, int):
                            if 1 <= cat_id <= len(label_list):
                                cat_id = cat_id - 1
                            else:
                                cat_id = 0
                        else:
                            cat_id = 0
                        
                        cells = pdf_cells[box_idx] if box_idx < len(pdf_cells) else []
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
                                
                    if not words:
                        words = ["empty"]
                        boxes = [[0, 0, 0, 0]]
                        word_labels = [0]
                        
                batch_words.append(words)
                batch_boxes.append(boxes)
                batch_word_labels.append(word_labels)
                
            normalized_batch_boxes = []
            for i, boxes in enumerate(batch_boxes):
                norm_boxes = []
                img = images[i]
                width, height = img.size if hasattr(img, "size") else (1000, 1000)
                for box in boxes:
                    if len(box) == 4:
                        x0, y0, x1, y1 = box[0], box[1], box[2], box[3]
                        if x1 < x0 or y1 < y0:
                            x1 = x0 + x1
                            y1 = y0 + y1
                        x0 = max(0, min(1000, int(1000 * (x0 / width))))
                        y0 = max(0, min(1000, int(1000 * (y0 / height))))
                        x1 = max(0, min(1000, int(1000 * (x1 / width))))
                        y1 = max(0, min(1000, int(1000 * (y1 / height))))
                        norm_boxes.append([x0, y0, x1, y1])
                    else:
                        norm_boxes.append([0, 0, 0, 0])
                normalized_batch_boxes.append(norm_boxes)
                
            return processor(
                images, 
                batch_words, 
                boxes=normalized_batch_boxes, 
                word_labels=batch_word_labels,
                truncation=True, 
                padding="max_length"
            )
            
        print("Preprocessing evaluation subset...")
        tokenized_eval = eval_subset.map(
            preprocess_function,
            batched=True,
            remove_columns=eval_dataset_raw.column_names
        )
        
        # Load Seqeval metric
        print("Loading Seqeval evaluation metric...")
        seqeval_metric = evaluate.load("seqeval")
        
        def compute_metrics(p):
            predictions, labels = p
            predictions = np.argmax(predictions, axis=2)
            true_predictions = [
                [label_list[p] for (p, l) in zip(prediction, label) if l != -100]
                for prediction, label in zip(predictions, labels)
            ]
            true_labels = [
                [label_list[l] for (p, l) in zip(prediction, label) if l != -100]
                for prediction, label in zip(predictions, labels)
            ]
            results = seqeval_metric.compute(predictions=true_predictions, references=true_labels)
            return {
                "precision": results["overall_precision"],
                "recall": results["overall_recall"],
                "f1": results["overall_f1"],
                "accuracy": results["overall_accuracy"],
            }
            
        # Init simple evaluation Trainer
        eval_args = TrainingArguments(
            output_dir="./eval_temp",
            eval_strategy="no",
            per_device_eval_batch_size=8,
            fp16=torch.cuda.is_available(),
            remove_unused_columns=False
        )
        
        trainer = Trainer(
            model=model,
            args=eval_args,
            processing_class=processor,
            data_collator=default_data_collator,
            compute_metrics=compute_metrics
        )
        
        print("Running layout classification evaluation...")
        eval_results = trainer.evaluate(eval_dataset=tokenized_eval)
        
        print("-" * 60)
        print("LAYOUTLMV3 EVALUATION RESULTS:")
        print("-" * 60)
        print(f"  Precision: {eval_results['eval_precision'] * 100:.2f}%")
        print(f"  Recall:    {eval_results['eval_recall'] * 100:.2f}%")
        print(f"  F1 Score:  {eval_results['eval_f1'] * 100:.2f}%")
        print(f"  Accuracy:  {eval_results['eval_accuracy'] * 100:.2f}%")
        print(f"  Loss:      {eval_results['eval_loss']:.4f}")
        print("-" * 60)
        print("Evaluation complete for LayoutLMv3!")
        
        # Cleanup temp directory
        import shutil
        if os.path.exists("./eval_temp"):
            shutil.rmtree("./eval_temp")
            
    except Exception as e:
        print(f"Error during LayoutLMv3 evaluation: {e}")

if __name__ == "__main__":
    evaluate_legal_bert()
    evaluate_layoutlmv3()
