import os
import json
from datasets import load_dataset, Dataset, DatasetDict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_local_cuad(file_path):
    """
    Parses and flattens a local SQuAD-formatted CUAD JSON file into a Dataset.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    rows = []
    for doc in data.get("data", []):
        title = doc.get("title", "")
        for paragraph in doc.get("paragraphs", []):
            context = paragraph.get("context", "")
            for qa in paragraph.get("qas", []):
                qa_id = qa.get("id", "")
                question = qa.get("question", "")
                answers = qa.get("answers", [])
                
                # Standard SQuAD structure answers dict
                answers_dict = {
                    "answer_start": [ans.get("answer_start") for ans in answers if ans.get("answer_start") is not None],
                    "text": [ans.get("text", "") for ans in answers]
                }
                
                rows.append({
                    "id": qa_id,
                    "title": title,
                    "context": context,
                    "question": question,
                    "answers": answers_dict
                })
                
    return Dataset.from_list(rows)

def prepare_cuad_dataset(output_dir="./data/cuad"):
    """
    Downloads and prepares the CUAD dataset for Legal-BERT fine-tuning.
    If CUADv1.json exists locally, parses it directly to avoid downloading.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(script_dir)
    data_dir = os.path.join(backend_dir, "Data")
    
    cuad_json = os.path.join(data_dir, "CUADv1.json")
    train_json = os.path.join(data_dir, "train_separate_questions.json")
    test_json = os.path.join(data_dir, "test.json")
    
    if os.path.exists(cuad_json):
        logger.info(f"Local CUAD JSON files found in {data_dir}. Preparing dataset from local files to avoid downloading...")
        try:
            if os.path.exists(train_json) and os.path.exists(test_json):
                logger.info("Loading pre-split train and test JSON files...")
                train_ds = load_local_cuad(train_json)
                test_ds = load_local_cuad(test_json)
                dataset = DatasetDict({"train": train_ds, "test": test_ds, "validation": test_ds})
            else:
                logger.info("Loading full CUADv1.json and performing train-test split...")
                full_ds = load_local_cuad(cuad_json)
                split_ds = full_ds.train_test_split(test_size=0.1, seed=42)
                dataset = DatasetDict({
                    "train": split_ds["train"],
                    "test": split_ds["test"],
                    "validation": split_ds["test"]
                })
            
            os.makedirs(output_dir, exist_ok=True)
            dataset.save_to_disk(output_dir)
            logger.info(f"CUAD dataset prepared and saved to {output_dir}")
            return dataset
        except Exception as e:
            logger.error(f"Error preparing CUAD dataset locally: {e}")
            logger.info("Falling back to downloading from Hugging Face...")

    logger.info("Downloading CUAD dataset...")
    # Using HuggingFace datasets
    try:
        # CUAD is available as "cuad" on HF datasets
        dataset = load_dataset("theatticusproject/atticus-open-contract-dataset-aok-beta")
        
        os.makedirs(output_dir, exist_ok=True)
        dataset.save_to_disk(output_dir)
        logger.info(f"CUAD dataset saved to {output_dir}")
        return dataset
    except Exception as e:
        logger.error(f"Error downloading CUAD: {e}")
        return None

def prepare_doclaynet_dataset(output_dir="./data/doclaynet"):
    """
    Downloads and prepares the DocLayNet dataset for LayoutLMv3 fine-tuning.
    DocLayNet is used for document layout analysis.
    """
    logger.info("Downloading DocLayNet dataset (this might take a while)...")
    try:
        # Load the pre-processed, script-free 1% small subset from the Hub
        dataset = load_dataset("merve/doclaynet-small")
        
        os.makedirs(output_dir, exist_ok=True)
        dataset.save_to_disk(output_dir)
        logger.info(f"DocLayNet dataset (subset) saved to {output_dir}")
        return dataset
    except Exception as e:
        logger.error(f"Error downloading DocLayNet: {e}")
        return None

if __name__ == "__main__":
    logger.info("Starting data preparation...")
    # prepare_cuad_dataset()
    prepare_doclaynet_dataset()
    logger.info("Data preparation scripts are ready. Run them to download datasets.")

