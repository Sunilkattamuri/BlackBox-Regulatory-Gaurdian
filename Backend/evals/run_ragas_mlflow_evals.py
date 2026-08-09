import os
import mlflow
import pandas as pd
from datasets import Dataset

# Ragas imports
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_precision,
    context_recall
)

# LangChain models for Ragas evaluation
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import HuggingFaceEmbeddings

def main():
    print("Initializing Ragas + MLflow Evaluation...")
    
    # 1. Setup MLflow Tracking
    # By default, MLflow logs to ./mlruns. We will use a local sqlite DB for persistence.
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Regulatory_Guardian_RAG_Evals")
    
    # 2. Define Mock Dataset
    # Ragas requires a specific schema: question, answer, contexts, ground_truth
    print("Creating sample evaluation dataset...")
    data = {
        "question": [
            "What is the capital of France?",
            "What happens if there is a data breach according to standard policies?",
        ],
        "answer": [
            "Paris is the capital of France.",
            "The company must notify regulators within 72 hours of a data breach.",
        ],
        "contexts": [
            ["France is a country in Europe. Its capital city is Paris."],
            ["Data protection regulations require that any data breach must be reported to the relevant authorities within 72 hours of discovery."],
        ],
        "ground_truth": [
            "Paris",
            "Notification must happen within 72 hours.",
        ]
    }
    
    # Ragas expects a huggingface dataset
    dataset = Dataset.from_dict(data)
    
    # 3. Setup Evaluator LLM & Embeddings (using Ollama locally)
    ollama_model = os.getenv("LLM_MODEL", "llama3.1")
    ollama_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    
    print(f"Setting up Evaluator LLM using {ollama_model}...")
    try:
        judge_llm = ChatOllama(model=ollama_model, base_url=ollama_url, temperature=0.0)
        # Use HuggingFace embeddings since Ollama might not support embedding on this model
        judge_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    except Exception as e:
        print(f"Failed to initialize Ollama wrapper: {e}")
        return
    
    # 4. Evaluate using Ragas
    print("Running Ragas evaluation (this may take a minute with local Ollama)...")
    
    # Wrap in MLflow run
    with mlflow.start_run(run_name="ragas_baseline_eval") as run:
        # Log parameters
        mlflow.log_param("evaluator_model", ollama_model)
        mlflow.log_param("dataset_size", len(dataset))
        
        try:
            # We pass the llm and embeddings explicitly to Ragas
            result = evaluate(
                dataset,
                metrics=[
                    answer_relevancy,
                    faithfulness,
                    context_precision,
                    context_recall
                ],
                llm=judge_llm,
                embeddings=judge_embeddings,
            )
            
            print("\n--- Evaluation Results ---")
            print(result)
            
            # Log the detailed dataset with scores as an artifact
            result_df = result.to_pandas()
            result_csv_path = "ragas_eval_results.csv"
            result_df.to_csv(result_csv_path, index=False)
            mlflow.log_artifact(result_csv_path)
            
            # Log metrics to MLflow (calculate mean of each metric column)
            metric_cols = ["answer_relevancy", "faithfulness", "context_precision", "context_recall"]
            for col in metric_cols:
                if col in result_df.columns:
                    mean_val = result_df[col].mean()
                    if pd.notna(mean_val):
                        mlflow.log_metric(col, mean_val)
            
            print(f"\nSuccessfully logged metrics to MLflow! Run ID: {run.info.run_id}")
            print("\nTo view results in your browser, open a new terminal in the Backend folder and run:")
            print("  mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000")
            print("Then navigate to http://localhost:5000")
            
        except Exception as e:
            print(f"Ragas evaluation failed: {e}")
            print("HINT: Ensure your Ollama server is running and the model is downloaded.")

if __name__ == "__main__":
    main()
