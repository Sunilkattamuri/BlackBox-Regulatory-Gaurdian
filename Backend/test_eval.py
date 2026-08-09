import pandas as pd
from phoenix.client import Client
from phoenix.evals.llm import LLM
from phoenix.evals import create_classifier, evaluate_dataframe
import os

client = Client(base_url='http://127.0.0.1:6006')
spans_df = client.spans.get_spans_dataframe(project_name='regulatory-guardian-app')
eval_df = spans_df[spans_df['span_kind'].isin(['LLM', 'CHAIN'])].copy()
if 'attributes.input.value' in eval_df.columns: 
    eval_df['input'] = eval_df['attributes.input.value'].astype(str)
if 'attributes.output.value' in eval_df.columns: 
    eval_df['output'] = eval_df['attributes.output.value'].astype(str)
eval_queries = eval_df[['input', 'output']].dropna().head(2)

judge_model = LLM(
    provider='openai', 
    model=os.getenv('LLM_MODEL', 'llama3.1'), 
    base_url=f"{os.getenv('LLM_BASE_URL', 'http://localhost:11434')}/v1", 
    api_key='ollama'
)
qa_evaluator = create_classifier(
    name='qa_correctness', 
    llm=judge_model, 
    prompt_template='Input: {input}\nOutput: {output}\nDetermine if output is correct. Provide reasoning.', 
    choices={'correct': 1.0, 'incorrect': 0.0}
)
res = evaluate_dataframe(eval_queries, [qa_evaluator])
score_col = 'qa_correctness_score' if 'qa_correctness_score' in res.columns else 'qa_correctness'
upload_df = pd.DataFrame(res[score_col].tolist(), index=res.index)
print("--- OUTPUT ---")
print(upload_df[['score', 'label', 'explanation']])
