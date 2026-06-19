import shap
import torch
import numpy as np
from typing import Dict, Any

class XAIService:
    def __init__(self):
        self.explainer = None

    def generate_explanation(self, qa_pipeline, text: str, question: str) -> Dict[str, Any]:
        """
        Generates SHAP values for a given QA prediction.
        """
        if not qa_pipeline:
            return {
                "status": "error",
                "message": "QA pipeline not loaded. Cannot generate SHAP values."
            }
            
        try:
            # 1. Truncate text to avoid massive computation
            # SHAP is computationally expensive; keep window small
            text_window = text[:1000] if len(text) > 1000 else text

            # 2. Define custom prediction function for SHAP
            # It takes a list of masked contexts and returns confidence scores
            def predict_score(contexts):
                scores = []
                for c in contexts:
                    if not c.strip():
                        scores.append(0.0)
                        continue
                    try:
                        res = qa_pipeline(question=question, context=c)
                        scores.append(res['score'])
                    except Exception:
                        scores.append(0.0)
                return np.array(scores)

            # 3. Create a text masker using the model's tokenizer
            masker = shap.maskers.Text(tokenizer=qa_pipeline.tokenizer)
            
            # 4. Initialize the SHAP Explainer
            # This defaults to a Kernel/Permutation explainer for custom python functions
            explainer = shap.Explainer(predict_score, masker)
            
            # 5. Compute SHAP values
            shap_values = explainer([text_window])
            
            # 6. Extract tokens and their mathematical attributions
            tokens = [str(t) for t in shap_values[0].data]
            values = shap_values[0].values.tolist()
            base_value = float(shap_values[0].base_values)
            
            return {
                "tokens": tokens,
                "shap_values": values,
                "base_value": base_value,
                "status": "success"
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": str(e)
            }

xai_service = XAIService()
