import pandas as pd
from phoenix.client import Client

def export_failed_evals():
    client = Client(base_url='http://127.0.0.1:6006')
    print("Fetching traces...")
    spans_df = client.spans.get_spans_dataframe(project_name='regulatory-guardian-app')
    
    # We need to fetch the annotations. 
    # Unfortunately, get_spans_dataframe doesn't return the full explanation by default in all versions.
    # We can try to extract it from the spans_df if it's there.
    # Annotations are usually stored in columns prefixed with `eval.` or similar.
    print(spans_df.columns)
    
    # Let's just dump the relevant subset
    if not spans_df.empty:
        spans_df.to_csv("all_spans_dump.csv")
        print("Dumped to all_spans_dump.csv")

if __name__ == "__main__":
    export_failed_evals()
