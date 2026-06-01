"""
Diagnostic script to debug Legal-BERT Answerable F1 issues.
Checks: training labels, model raw predictions, span extraction, data distribution.
"""
import os
import torch
import numpy as np
from datasets import load_from_disk
from transformers import AutoTokenizer, AutoModelForQuestionAnswering

LEGAL_BERT_PATH = "models/legal_bert_cuad"
CUAD_DATA_DIR = "./data/cuad"

def main():
    print("=" * 70)
    print("LEGAL-BERT DIAGNOSTIC")
    print("=" * 70)
    
    # 1. Load dataset
    dataset = load_from_disk(CUAD_DATA_DIR)
    test_split = "test" if "test" in dataset else list(dataset.keys())[0]
    train_split = "train"
    eval_ds = dataset[test_split]
    train_ds = dataset[train_split]
    
    # 2. Dataset distribution analysis
    print("\n--- DATASET DISTRIBUTION ---")
    for split_name, split_ds in [("train", train_ds), ("test", eval_ds)]:
        n_total = len(split_ds)
        n_has_ans = sum(1 for ex in split_ds if len(ex["answers"]["text"]) > 0 and ex["answers"]["text"][0] != "")
        n_no_ans = n_total - n_has_ans
        print(f"  {split_name}: {n_total} total, {n_has_ans} answerable ({100*n_has_ans/n_total:.1f}%), {n_no_ans} unanswerable ({100*n_no_ans/n_total:.1f}%)")
    
    # 3. Check training data labels
    print("\n--- TRAINING DATA LABEL CHECK ---")
    tokenizer = AutoTokenizer.from_pretrained(LEGAL_BERT_PATH)
    
    # Pick 5 answerable examples from training data
    answerable_train = [ex for ex in train_ds if len(ex["answers"]["text"]) > 0 and ex["answers"]["text"][0] != ""]
    print(f"  Total answerable training examples: {len(answerable_train)}")
    
    # Tokenize a few and check labels
    check_examples = answerable_train[:5]
    for i, ex in enumerate(check_examples):
        question = ex["question"]
        context = ex["context"]
        answer_text = ex["answers"]["text"][0]
        answer_start = ex["answers"]["answer_start"][0]
        answer_end = answer_start + len(answer_text)
        
        inputs = tokenizer(
            question, context,
            max_length=512,
            truncation="only_second",
            stride=128,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding="max_length"
        )
        
        sample_mapping = inputs["overflow_to_sample_mapping"]
        offset_mapping = inputs["offset_mapping"]
        
        # Find which chunk contains the answer
        found_in_chunk = None
        for c in range(len(inputs["input_ids"])):
            sequence_ids = inputs.sequence_ids(c)
            context_indices = [idx for idx, seq_id in enumerate(sequence_ids) if seq_id == 1]
            if not context_indices:
                continue
            ctx_start_idx = context_indices[0]
            ctx_end_idx = context_indices[-1]
            
            # Check if answer is in this chunk
            if offset_mapping[c][ctx_start_idx][0] <= answer_start and offset_mapping[c][ctx_end_idx][1] >= answer_end:
                found_in_chunk = c
                
                # Compute labels the way training does
                idx = ctx_start_idx
                while idx <= ctx_end_idx and offset_mapping[c][idx][0] <= answer_start:
                    idx += 1
                label_start = idx - 1
                
                # Original end logic (backward walk)
                idx_orig = ctx_end_idx
                while idx_orig >= ctx_start_idx and offset_mapping[c][idx_orig][1] >= answer_end:
                    idx_orig -= 1
                label_end_orig = idx_orig + 1
                
                # New end logic (forward walk)
                idx_new = ctx_start_idx
                while idx_new <= ctx_end_idx and offset_mapping[c][idx_new][1] < answer_end:
                    idx_new += 1
                label_end_new = idx_new
                
                # Decode the labeled span
                labeled_tokens_orig = inputs["input_ids"][c][label_start:label_end_orig+1]
                labeled_text_orig = tokenizer.decode(labeled_tokens_orig)
                
                labeled_tokens_new = inputs["input_ids"][c][label_start:label_end_new+1]
                labeled_text_new = tokenizer.decode(labeled_tokens_new)
                
                print(f"\n  Example {i}: chunk {c}/{len(inputs['input_ids'])}")
                print(f"    Question: {question[:80]}...")
                print(f"    Gold answer ({len(answer_text)} chars): '{answer_text[:100]}...'") if len(answer_text) > 100 else print(f"    Gold answer ({len(answer_text)} chars): '{answer_text}'")
                print(f"    Label span (orig logic): [{label_start}, {label_end_orig}] -> '{labeled_text_orig[:100]}'")
                print(f"    Label span (new  logic): [{label_start}, {label_end_new}]  -> '{labeled_text_new[:100]}'")
                print(f"    Labels match: {label_end_orig == label_end_new}")
                break
        
        if found_in_chunk is None:
            print(f"\n  Example {i}: Answer NOT found in any chunk!")
            print(f"    Question: {question[:80]}...")
            print(f"    Answer at char [{answer_start}, {answer_end}]")
            print(f"    Context length: {len(context)} chars")
            print(f"    Total chunks: {len(inputs['input_ids'])}")
    
    # 4. Check tokenized training data labels
    print("\n\n--- TOKENIZED TRAINING DATA LABELS ---")
    tokenized_train_path = os.path.join(CUAD_DATA_DIR, "..", "cuad_tokenized")
    
    # Tokenize a batch and check label distribution
    batch = answerable_train[:50]
    questions = [ex["question"].strip() for ex in batch]
    contexts = [ex["context"] for ex in batch]
    answers = [ex["answers"] for ex in batch]
    
    inputs = tokenizer(
        questions, contexts,
        max_length=512,
        truncation="only_second",
        stride=128,
        return_overflowing_tokens=True,
        return_offsets_mapping=True,
        padding="max_length"
    )
    sample_mapping = inputs["overflow_to_sample_mapping"]
    offset_mapping_all = inputs["offset_mapping"]
    
    n_chunks = len(inputs["input_ids"])
    n_answerable_chunks = 0
    n_cls_chunks = 0
    
    for ci in range(n_chunks):
        sample_idx = sample_mapping[ci]
        answer = answers[sample_idx]
        sequence_ids = inputs.sequence_ids(ci)
        offsets = offset_mapping_all[ci]
        cls_index = inputs["input_ids"][ci].index(tokenizer.cls_token_id)
        
        if len(answer["answer_start"]) == 0 or answer["text"][0] == "":
            n_cls_chunks += 1
            continue
        
        start_char = answer["answer_start"][0]
        end_char = start_char + len(answer["text"][0])
        
        token_start_index = 0
        while sequence_ids[token_start_index] != 1:
            token_start_index += 1
        context_start = token_start_index
        
        token_end_index = len(inputs["input_ids"][ci]) - 1
        while sequence_ids[token_end_index] != 1:
            token_end_index -= 1
        context_end = token_end_index
        
        if offsets[context_start][0] > start_char or offsets[context_end][1] < end_char:
            n_cls_chunks += 1
        else:
            n_answerable_chunks += 1
    
    print(f"  From 50 answerable examples -> {n_chunks} total chunks")
    print(f"  Chunks with answer in window: {n_answerable_chunks} ({100*n_answerable_chunks/n_chunks:.1f}%)")
    print(f"  Chunks labeled as CLS (unanswerable): {n_cls_chunks} ({100*n_cls_chunks/n_chunks:.1f}%)")
    
    # 5. Model prediction diagnostics
    print("\n\n--- MODEL PREDICTION DIAGNOSTICS ---")
    model = AutoModelForQuestionAnswering.from_pretrained(LEGAL_BERT_PATH)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    
    # Get answerable test examples
    eval_subset = eval_ds.shuffle(seed=42).select(range(min(len(eval_ds), 100)))
    answerable_test = [ex for ex in eval_subset if len(ex["answers"]["text"]) > 0 and ex["answers"]["text"][0] != ""]
    
    print(f"  Checking {min(10, len(answerable_test))} answerable test examples...\n")
    
    for i, ex in enumerate(answerable_test[:10]):
        question = ex["question"]
        context = ex["context"]
        answer_text = ex["answers"]["text"][0]
        answer_start_char = ex["answers"]["answer_start"][0]
        
        context_trunc = context[:20000]
        answer_in_window = answer_start_char + len(answer_text) <= 20000
        
        inputs_raw = tokenizer(
            question, context_trunc,
            max_length=512, stride=128,
            truncation="only_second",
            return_overflowing_tokens=True,
            return_offsets_mapping=True
        )
        
        num_chunks = len(inputs_raw["input_ids"])
        
        # Run inference on all chunks
        all_start_logits = []
        all_end_logits = []
        for batch_idx in range(0, num_chunks, 8):
            batch_ids = torch.tensor(inputs_raw["input_ids"][batch_idx:batch_idx+8]).to(device)
            batch_mask = torch.tensor(inputs_raw["attention_mask"][batch_idx:batch_idx+8]).to(device)
            inp = {"input_ids": batch_ids, "attention_mask": batch_mask}
            if "token_type_ids" in inputs_raw:
                inp["token_type_ids"] = torch.tensor(inputs_raw["token_type_ids"][batch_idx:batch_idx+8]).to(device)
            with torch.no_grad():
                out = model(**inp)
            all_start_logits.append(out.start_logits.cpu())
            all_end_logits.append(out.end_logits.cpu())
        
        start_logits = torch.cat(all_start_logits, dim=0)
        end_logits = torch.cat(all_end_logits, dim=0)
        
        # Find best span across all chunks
        best_diff = -999999
        best_text = ""
        best_null = 0
        best_span_score = 0
        
        for c in range(num_chunks):
            seq_ids = inputs_raw.sequence_ids(c)
            offsets = inputs_raw["offset_mapping"][c]
            ctx_indices = [idx for idx, sid in enumerate(seq_ids) if sid == 1]
            if not ctx_indices:
                continue
            ctx_s, ctx_e = ctx_indices[0], ctx_indices[-1]
            
            sl = start_logits[c].tolist()
            el = end_logits[c].tolist()
            null_score = sl[0] + el[0]
            
            # Find best span in context region
            best_cs = -999999
            best_si, best_ei = 0, 0
            
            top_starts = sorted(range(ctx_s, ctx_e+1), key=lambda x: sl[x], reverse=True)[:20]
            top_ends = sorted(range(ctx_s, ctx_e+1), key=lambda x: el[x], reverse=True)[:20]
            
            for si in top_starts:
                for ei in top_ends:
                    if ei < si or ei - si + 1 > 150:
                        continue
                    score = sl[si] + el[ei]
                    if score > best_cs:
                        best_cs = score
                        best_si, best_ei = si, ei
            
            if best_si > 0 and best_ei >= best_si:
                diff = best_cs - null_score
                if diff > best_diff:
                    best_diff = diff
                    best_null = null_score
                    best_span_score = best_cs
                    cs = offsets[best_si][0]
                    ce = offsets[best_ei][1]
                    best_text = context_trunc[cs:ce].strip()
        
        # Check CLS logit dominance
        cls_start_logits = [start_logits[c][0].item() for c in range(num_chunks)]
        cls_end_logits = [end_logits[c][0].item() for c in range(num_chunks)]
        max_ctx_start = max(start_logits[c][1:].max().item() for c in range(num_chunks))
        max_ctx_end = max(end_logits[c][1:].max().item() for c in range(num_chunks))
        
        print(f"  Example {i}: {question[:70]}...")
        print(f"    Answer in 20k window: {answer_in_window}")
        print(f"    Gold: '{answer_text[:80]}...'") if len(answer_text) > 80 else print(f"    Gold: '{answer_text}'")
        print(f"    Pred: '{best_text[:80]}...'") if len(best_text) > 80 else print(f"    Pred: '{best_text}'")
        print(f"    Chunks: {num_chunks}")
        print(f"    Null score: {best_null:.2f}, Span score: {best_span_score:.2f}, Diff: {best_diff:.2f}")
        print(f"    CLS start logit (max across chunks): {max(cls_start_logits):.2f}")
        print(f"    CLS end logit (max across chunks): {max(cls_end_logits):.2f}")
        print(f"    Max context start logit: {max_ctx_start:.2f}")
        print(f"    Max context end logit: {max_ctx_end:.2f}")
        
        # F1 between pred and gold
        if best_text and answer_text:
            pred_tokens = best_text.lower().split()
            gold_tokens = answer_text.lower().split()
            common = set(pred_tokens) & set(gold_tokens)
            if len(pred_tokens) > 0 and len(gold_tokens) > 0 and len(common) > 0:
                p = len(common) / len(pred_tokens)
                r = len(common) / len(gold_tokens)
                f1 = 2 * p * r / (p + r)
            else:
                f1 = 0.0
            print(f"    Token-level F1: {f1:.2f}")
        print()
    
    # 6. Summary diagnostic
    print("\n--- SUMMARY ---")
    print("If CLS logits consistently dominate context logits -> model hasn't learned span extraction")
    print("If context logits are competitive but spans are wrong -> eval extraction bug")
    print("If very few answerable chunks in training -> data imbalance issue")
    print("If gold answers are outside 20k window -> context truncation issue")

if __name__ == "__main__":
    main()
