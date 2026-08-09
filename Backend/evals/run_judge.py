import os
import pandas as pd
import phoenix as px
from phoenix.client import Client
from phoenix.evals import create_classifier, evaluate_dataframe
from phoenix.evals.llm import LLM

def main():
    # 1. Connect to Phoenix Server
    print("Connecting to local Phoenix Server (http://127.0.0.1:6006)...")
    try:
        client = Client(base_url="http://127.0.0.1:6006")
    except Exception as e:
        print(f"Could not connect to Phoenix: {e}")
        print("Make sure Phoenix is running (via phoenix serve or the other script)!")
        return

    # 2. Fetch Traces
    print("Fetching traces from 'regulatory-guardian' project...")
    try:
        spans_df = client.spans.get_spans_dataframe(project_name="regulatory-guardian-app")
    except Exception as e:
        print(f"Error fetching traces: {e}")
        return

    if spans_df is None or spans_df.empty:
        print("No traces found! Please run `run_phoenix_evals.py` first to generate traces.")
        return

    print(f"Found {len(spans_df)} total traces/spans.")

    # Filter for LLM or Chain spans to evaluate
    # OpenInference uses 'LLM' or 'CHAIN' for span_kind
    eval_df = spans_df[spans_df["span_kind"].isin(["LLM", "CHAIN"])].copy()
    
    if eval_df.empty:
        print("No LLM/CHAIN spans found to evaluate.")
        return

    # Phoenix evaluators expect 'input' and 'output' columns in the dataframe
    # Depending on the OpenInference version, these are stored in different attribute columns
    # We will safely extract them:
    if "attributes.input.value" in eval_df.columns:
        eval_df["input"] = eval_df["attributes.input.value"].astype(str)
    else:
        eval_df["input"] = "Unknown Input"

    if "attributes.output.value" in eval_df.columns:
        eval_df["output"] = eval_df["attributes.output.value"].astype(str)
    else:
        eval_df["output"] = "Unknown Output"

    # Drop empty rows just in case
    eval_queries = eval_df[["input", "output"]].dropna()
    print(f"Extracted {len(eval_queries)} valid spans for evaluation.")

    # 3. Setup the Evaluator LLM (The Judge)
    ollama_model = os.getenv("LLM_MODEL", "llama3.1")
    ollama_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    print(f"Initializing Judge LLM ({ollama_model} via Ollama/OpenAI interface)...")
    
    # Phoenix 3.3.0+ uses its own LLM wrapper. We point the OpenAI adapter to Ollama's local endpoint.
    judge_model = LLM(
        provider="openai",
        model=ollama_model,
        base_url=f"{ollama_url}/v1",
        api_key="ollama" # Dummy key
    )
    
    qa_prompt = """
You are an expert evaluator. Evaluate the AI's response based on the input question.
Input: {input}
Output: {output}
Determine if the output is correct. Provide your reasoning and a binary score (1 for correct, 0 for incorrect).
"""

    qa_evaluator = create_classifier(
        name="qa_correctness",
        llm=judge_model,
        prompt_template=qa_prompt,
        choices={
            "correct": 1.0,
            "incorrect": 0.0
        }
    )
    
    # 4. Run the Evaluation
    print("\nRunning evaluation on traces (this will take a moment as Ollama processes them)...")
    try:
        # evaluate_dataframe runs the evaluator over the dataframe
        eval_result_df = evaluate_dataframe(
            dataframe=eval_queries,
            evaluators=[qa_evaluator]
        ) # It returns a single dataframe in the new API
    except Exception as e:
        print(f"Evaluation failed: {e}")
        return

    # 5. Push results back to Phoenix
    print("\nEvaluation complete! Pushing scores back to Phoenix...")
    # In the new API, evaluate_dataframe returns a column containing a dictionary for each score.
    # We must expand this dictionary into separate 'score', 'label', and 'explanation' columns.
    
    # We first find the column returned by the evaluator. It usually ends with '_score' or matches the evaluator name.
    score_col = "qa_correctness_score" if "qa_correctness_score" in eval_result_df.columns else "qa_correctness"
    
    upload_df = pd.DataFrame(eval_result_df[score_col].tolist(), index=eval_result_df.index)
    print("Columns in upload_df:", upload_df.columns.tolist())
    print(upload_df.head())

    # Phoenix client lets you log evaluations to spans
    client.spans.log_span_annotations_dataframe(
        dataframe=upload_df,
        annotator_kind="LLM",
        annotation_name="qa_correctness"
    )

    print("Success! Check your Phoenix UI (http://127.0.0.1:6006).")
    print("The traces should now have 'qa_correctness' scores attached to them!")

if __name__ == "__main__":
    main()
