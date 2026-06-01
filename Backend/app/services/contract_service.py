"""
Contract Inference Service.
Handles PDF processing with OCR, LayoutLMv3 document layout analysis,
and Legal-BERT clause extraction.
"""

import os
import torch
import fitz  # PyMuPDF
import easyocr
import logging
import numpy as np
from PIL import Image
from io import BytesIO
from typing import Dict, Any, List, Optional, Tuple
from transformers import (
    pipeline,
    AutoTokenizer,
    AutoModelForQuestionAnswering,
    LayoutLMv3Processor,
    LayoutLMv3ForTokenClassification
)

from ..config import settings

logger = logging.getLogger(__name__)

# Initialize easyocr reader
try:
    reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())
except Exception as e:
    logger.warning(f"Failed to initialize EasyOCR: {e}")
    reader = None

# LayoutLMv3 label mapping for DocLayNet
DOCLAYNET_LABELS = [
    "Caption", "Footnote", "Formula", "List-item", "Page-footer",
    "Page-header", "Picture", "Section-header", "Table", "Text", "Title"
]

# Priority sections for contract analysis
CONTRACT_SECTIONS = {
    "Title": 0,
    "Section-header": 1,
    "Text": 2,
    "List-item": 3,
    "Table": 4,
    "Footnote": 5,
}


class ContractInferenceService:
    def __init__(self):
        self.device = 0 if torch.cuda.is_available() else -1
        self.qa_pipeline = None
        self.layout_processor = None
        self.layout_model = None
        self.layout_labels = DOCLAYNET_LABELS
        self._load_models()

    def _load_models(self):
        logger.info("Loading inference models...")

        # 1. Load Legal-BERT QA
        legal_bert_path = settings.LEGAL_BERT_PATH
        if os.path.exists(legal_bert_path):
            try:
                tokenizer = AutoTokenizer.from_pretrained(legal_bert_path)
                model = AutoModelForQuestionAnswering.from_pretrained(legal_bert_path)
                self.qa_pipeline = pipeline(
                    "question-answering", model=model, tokenizer=tokenizer,
                    device=self.device
                )
                logger.info(f"Loaded fine-tuned Legal-BERT from {legal_bert_path}")
            except Exception as e:
                logger.error(f"Error loading fine-tuned Legal-BERT: {e}. Falling back to base model.")
                self._load_base_legal_bert()
        else:
            logger.info("Fine-tuned Legal-BERT not found. Loading base model.")
            self._load_base_legal_bert()

        # 2. Load LayoutLMv3
        layoutlm_path = settings.LAYOUTLMV3_PATH
        if os.path.exists(layoutlm_path):
            try:
                self.layout_processor = LayoutLMv3Processor.from_pretrained(
                    layoutlm_path, apply_ocr=False
                )
                self.layout_model = LayoutLMv3ForTokenClassification.from_pretrained(
                    layoutlm_path
                )
                if self.device == 0:
                    self.layout_model.to("cuda")
                self.layout_model.eval()

                # Check if model has custom labels
                if hasattr(self.layout_model.config, 'id2label'):
                    self.layout_labels = [
                        self.layout_model.config.id2label[i]
                        for i in range(len(self.layout_model.config.id2label))
                    ]

                logger.info(f"Loaded LayoutLMv3 from {layoutlm_path} with "
                            f"{len(self.layout_labels)} labels")
            except Exception as e:
                logger.error(f"Error loading LayoutLMv3: {e}")
        else:
            logger.info(f"LayoutLMv3 not found at {layoutlm_path}. "
                        "Layout analysis will be skipped.")

    def _load_base_legal_bert(self):
        """Load the base Legal-BERT model as a fallback."""
        try:
            self.qa_pipeline = pipeline(
                "question-answering",
                model="nlpaueb/legal-bert-base-uncased",
                device=self.device,
            )
            logger.info("Loaded base Legal-BERT model")
        except Exception as e:
            logger.error(f"Failed to load base Legal-BERT: {e}")

    def extract_text_from_pdf(self, file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Extracts raw text and page-level metadata from PDF using PyMuPDF and EasyOCR.

        Returns:
            Tuple of (full_text, page_data) where page_data contains per-page info
            including text, OCR results, and image data for LayoutLMv3.
        """
        text = ""
        page_data = []
        doc = fitz.open(file_path)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text()
            ocr_used = False
            ocr_results = []

            if page_text.strip() == "" and reader is not None:
                # OCR fallback for scanned pages
                ocr_used = True
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")

                # Save temp image for easyocr
                temp_img_path = f"temp_page_{page_num}.png"
                try:
                    with open(temp_img_path, "wb") as f:
                        f.write(img_data)

                    ocr_result = reader.readtext(temp_img_path)
                    page_text = " ".join([res[1] for res in ocr_result])

                    # Store OCR results with bounding boxes for LayoutLMv3
                    for bbox, text_content, confidence in ocr_result:
                        # Convert easyocr bbox format to x0,y0,x1,y1
                        x_coords = [p[0] for p in bbox]
                        y_coords = [p[1] for p in bbox]
                        ocr_results.append({
                            "text": text_content,
                            "bbox": [
                                int(min(x_coords)), int(min(y_coords)),
                                int(max(x_coords)), int(max(y_coords))
                            ],
                            "confidence": confidence,
                        })
                finally:
                    if os.path.exists(temp_img_path):
                        os.remove(temp_img_path)

            # Get page image for LayoutLMv3
            pix = page.get_pixmap(dpi=150)
            img = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")

            # Extract word-level bounding boxes from PyMuPDF if no OCR
            words_with_boxes = []
            if not ocr_used:
                word_blocks = page.get_text("words")  # (x0, y0, x1, y1, word, ...)
                for wb in word_blocks:
                    if len(wb) >= 5:
                        words_with_boxes.append({
                            "text": wb[4],
                            "bbox": [int(wb[0]), int(wb[1]), int(wb[2]), int(wb[3])],
                        })
            else:
                words_with_boxes = ocr_results

            page_data.append({
                "page_num": page_num,
                "text": page_text,
                "image": img,
                "words": words_with_boxes,
                "ocr_used": ocr_used,
                "width": pix.width,
                "height": pix.height,
            })

            text += page_text + "\n"

        doc.close()
        return text, page_data

    def analyze_layout(self, page_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run LayoutLMv3 on each page to classify document regions.
        Returns structured layout analysis with labeled sections.
        """
        if not self.layout_model or not self.layout_processor:
            logger.info("LayoutLMv3 not available, skipping layout analysis")
            return {"status": "skipped", "reason": "LayoutLMv3 model not loaded"}

        layout_results = {
            "pages": [],
            "sections": {},  # Aggregated sections across pages
            "status": "completed",
        }

        for page in page_data:
            words = page.get("words", [])
            if not words:
                layout_results["pages"].append({
                    "page_num": page["page_num"],
                    "regions": [],
                    "note": "No words detected on this page",
                })
                continue

            try:
                # Prepare inputs for LayoutLMv3
                word_texts = [w["text"] for w in words]
                word_boxes = [w["bbox"] for w in words]

                # Normalize bounding boxes to 0-1000 range
                page_width = page.get("width", 1)
                page_height = page.get("height", 1)

                normalized_boxes = []
                for box in word_boxes:
                    normalized_boxes.append([
                        int(box[0] * 1000 / page_width),
                        int(box[1] * 1000 / page_height),
                        int(box[2] * 1000 / page_width),
                        int(box[3] * 1000 / page_height),
                    ])

                # Clamp values to [0, 1000]
                normalized_boxes = [
                    [max(0, min(1000, c)) for c in box]
                    for box in normalized_boxes
                ]

                # Process through LayoutLMv3
                encoding = self.layout_processor(
                    page["image"],
                    word_texts,
                    boxes=normalized_boxes,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                    padding="max_length",
                )

                if self.device == 0:
                    encoding = {k: v.to("cuda") for k, v in encoding.items()}

                with torch.no_grad():
                    outputs = self.layout_model(**encoding)

                predictions = outputs.logits.argmax(-1).squeeze().tolist()
                if isinstance(predictions, int):
                    predictions = [predictions]

                # Map predictions back to words (skip special tokens)
                # LayoutLMv3 adds CLS, SEP tokens — offset by 1
                regions = []
                current_label = None
                current_text = []
                current_bbox = None

                for i, word in enumerate(word_texts):
                    if i + 1 < len(predictions):
                        pred_idx = predictions[i + 1]  # +1 for CLS token
                        if pred_idx < len(self.layout_labels):
                            label = self.layout_labels[pred_idx]
                        else:
                            label = "Text"
                    else:
                        label = "Text"

                    if label == current_label:
                        current_text.append(word)
                        # Expand bbox
                        if current_bbox and i < len(word_boxes):
                            current_bbox = [
                                min(current_bbox[0], word_boxes[i][0]),
                                min(current_bbox[1], word_boxes[i][1]),
                                max(current_bbox[2], word_boxes[i][2]),
                                max(current_bbox[3], word_boxes[i][3]),
                            ]
                    else:
                        # Save previous region
                        if current_label and current_text:
                            region_text = " ".join(current_text)
                            regions.append({
                                "label": current_label,
                                "text": region_text,
                                "bbox": current_bbox,
                            })

                            # Aggregate into sections
                            if current_label not in layout_results["sections"]:
                                layout_results["sections"][current_label] = []
                            layout_results["sections"][current_label].append(region_text)

                        current_label = label
                        current_text = [word]
                        current_bbox = word_boxes[i] if i < len(word_boxes) else None

                # Don't forget the last region
                if current_label and current_text:
                    region_text = " ".join(current_text)
                    regions.append({
                        "label": current_label,
                        "text": region_text,
                        "bbox": current_bbox,
                    })
                    if current_label not in layout_results["sections"]:
                        layout_results["sections"][current_label] = []
                    layout_results["sections"][current_label].append(region_text)

                layout_results["pages"].append({
                    "page_num": page["page_num"],
                    "regions": regions,
                    "total_regions": len(regions),
                })

            except Exception as e:
                logger.error(f"LayoutLMv3 error on page {page['page_num']}: {e}")
                layout_results["pages"].append({
                    "page_num": page["page_num"],
                    "regions": [],
                    "error": str(e),
                })

        return layout_results

    def _build_enhanced_context(
        self, raw_text: str, layout_results: Dict[str, Any]
    ) -> str:
        """
        Build an enhanced context for QA by prioritizing text from
        important layout sections (headers, titled sections) identified by LayoutLMv3.
        """
        if layout_results.get("status") != "completed":
            return raw_text[:4000]

        sections = layout_results.get("sections", {})

        # Build context prioritizing important sections
        priority_text_parts = []

        # 1. Titles and section headers first (most informative)
        for label in ["Title", "Section-header"]:
            if label in sections:
                priority_text_parts.extend(sections[label])

        # 2. Main text content
        if "Text" in sections:
            priority_text_parts.extend(sections["Text"])

        # 3. List items (often contain contractual terms)
        if "List-item" in sections:
            priority_text_parts.extend(sections["List-item"])

        # 4. Table content
        if "Table" in sections:
            priority_text_parts.extend(sections["Table"])

        enhanced_context = "\n".join(priority_text_parts)

        if len(enhanced_context) > 4000:
            enhanced_context = enhanced_context[:4000]
        elif len(enhanced_context) < 200:
            # If layout extraction yielded too little, fall back to raw text
            enhanced_context = raw_text[:4000]

        return enhanced_context

    def analyze_contract(self, file_path: str) -> Dict[str, Any]:
        """
        Main pipeline: OCR → Layout Analysis (LayoutLMv3) → Clause Extraction (Legal-BERT).

        Returns structured analysis with layout data, extracted clauses, and risk flags.
        """
        # Step 1: Extract text and page data
        raw_text, page_data = self.extract_text_from_pdf(file_path)

        # Step 2: Run LayoutLMv3 layout analysis
        layout_results = self.analyze_layout(page_data)

        # Step 3: Build enhanced context using layout structure
        enhanced_context = self._build_enhanced_context(raw_text, layout_results)

        # Step 4: Define questions based on CUAD standards
        questions = [
            "What is the effective date of the contract?",
            "Who are the parties to the contract?",
            "What is the governing law?",
            "Are there any termination clauses?",
            "Is there a confidentiality or non-disclosure agreement?",
            "What are the payment terms?",
            "Are there any indemnification clauses?",
            "What is the duration or term of the contract?",
            "Are there any limitation of liability clauses?",
            "Is there an arbitration or dispute resolution clause?",
        ]

        # Step 5: Extract clauses using Legal-BERT QA
        extracted_clauses = {}
        if self.qa_pipeline and len(enhanced_context.strip()) > 0:
            for q in questions:
                try:
                    ans = self.qa_pipeline(question=q, context=enhanced_context)
                    extracted_clauses[q] = {
                        "answer": ans['answer'],
                        "score": round(ans['score'], 4),
                    }
                except Exception as e:
                    logger.error(f"Error during QA inference for '{q}': {e}")
                    extracted_clauses[q] = {"answer": "Error extracting", "score": 0.0}

        # Step 6: Generate risk flags
        risk_flags = self._generate_risk_flags(extracted_clauses, layout_results)

        # Step 7: Compile layout summary
        layout_summary = self._compile_layout_summary(layout_results)

        return {
            "raw_text": raw_text[:500] + "... (truncated)" if len(raw_text) > 500 else raw_text,
            "clauses": extracted_clauses,
            "risk_flags": risk_flags,
            "layout_analysis": layout_summary,
            "pages_analyzed": len(page_data),
            "layout_status": layout_results.get("status", "skipped"),
            "ocr_pages": sum(1 for p in page_data if p.get("ocr_used", False)),
        }

    def _generate_risk_flags(
        self,
        clauses: Dict[str, Dict],
        layout_results: Dict[str, Any],
    ) -> List[Optional[Dict[str, str]]]:
        """Generate risk flags based on extracted clauses and layout analysis."""
        risk_flags = []

        # Check for missing critical clauses
        critical_checks = {
            "Are there any termination clauses?": {
                "type": "Missing Termination Clause",
                "severity": "High",
                "description": "No termination clause detected. This may limit exit options.",
            },
            "What is the governing law?": {
                "type": "Missing Governing Law",
                "severity": "High",
                "description": "No governing law specified. Jurisdictional ambiguity risk.",
            },
            "Is there a confidentiality or non-disclosure agreement?": {
                "type": "Missing Confidentiality Clause",
                "severity": "Medium",
                "description": "No confidentiality/NDA clause detected.",
            },
            "Are there any limitation of liability clauses?": {
                "type": "Missing Liability Limitation",
                "severity": "High",
                "description": "No limitation of liability found. Unlimited liability exposure.",
            },
            "Is there an arbitration or dispute resolution clause?": {
                "type": "Missing Dispute Resolution",
                "severity": "Medium",
                "description": "No arbitration/dispute resolution mechanism specified.",
            },
        }

        for question, flag_info in critical_checks.items():
            if question in clauses:
                clause = clauses[question]
                answer = clause.get("answer", "").lower()
                score = clause.get("score", 0)

                # Flag if low confidence or answer suggests absence
                if score < 0.1 or "error" in answer or "no" == answer.strip():
                    risk_flags.append(flag_info)

        # Layout-based risks
        if layout_results.get("status") == "completed":
            sections = layout_results.get("sections", {})
            if "Table" not in sections:
                risk_flags.append({
                    "type": "No Tables Detected",
                    "severity": "Low",
                    "description": "No tables found. Check for missing schedules or annexures.",
                })
            if "Section-header" not in sections or len(sections.get("Section-header", [])) < 3:
                risk_flags.append({
                    "type": "Poorly Structured Document",
                    "severity": "Low",
                    "description": "Few section headers detected. Document may be poorly structured.",
                })

        return [f for f in risk_flags if f is not None]

    def _compile_layout_summary(self, layout_results: Dict[str, Any]) -> Dict[str, Any]:
        """Compile a summary of the layout analysis for storage."""
        if layout_results.get("status") != "completed":
            return {
                "status": layout_results.get("status", "skipped"),
                "reason": layout_results.get("reason", "LayoutLMv3 not available"),
            }

        sections = layout_results.get("sections", {})
        return {
            "status": "completed",
            "total_pages": len(layout_results.get("pages", [])),
            "section_counts": {
                label: len(texts) for label, texts in sections.items()
            },
            "detected_sections": list(sections.keys()),
            "has_tables": "Table" in sections,
            "has_headers": "Section-header" in sections,
            "section_headers": sections.get("Section-header", [])[:10],
        }


contract_service = ContractInferenceService()
