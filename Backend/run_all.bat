@echo off
echo Starting LayoutLMv3 Training...
python training/train_layoutlmv3.py
echo LayoutLMv3 Training Completed!
echo.
echo Starting Legal-BERT Training...
python training/train_legal_bert.py
echo Legal-BERT Training Completed!
