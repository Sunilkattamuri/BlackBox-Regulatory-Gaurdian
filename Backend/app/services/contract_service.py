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
import json
from langchain_ollama import ChatOllama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import SystemMessage, HumanMessage
from transformers import (
    LayoutLMv3Processor,
    LayoutLMv3ForTokenClassification,
    pipeline,
    AutoTokenizer,
    AutoModelForQuestionAnswering
)

from .agents.obligation_extractor import OBLIGATION_EXTRACTOR_SYSTEM_PROMPT
from .agents.impact_assessor import IMPACT_ASSESSOR_SYSTEM_PROMPT
from .agents.compliance_reporter import COMPLIANCE_REPORTER_SYSTEM_PROMPT

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
        self.bert_tokenizer = None
        self.bert_model = None
        self.layout_processor = None
        self.layout_model = None
        self.layout_labels = DOCLAYNET_LABELS
        self._load_models()

    def _load_models(self):
        logger.info("Loading inference models...")

        # 1. Load LLM (Ollama)
        try:
            self.llm = ChatOllama(
                model=settings.LLM_MODEL,
                temperature=0.0,
                base_url=settings.LLM_BASE_URL
            )
            # Quick check
            self.llm.invoke([HumanMessage(content="test")])
            logger.info(f"Loaded LLM: {settings.LLM_MODEL} from {settings.LLM_BASE_URL}")
        except Exception as e:
            logger.error(f"Failed to load LLM: {e}")
            self.llm = None

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

        # 3. Load fine-tuned Legal-BERT for QA Clause Extraction
        legal_bert_path = settings.LEGAL_BERT_PATH
        if os.path.exists(legal_bert_path):
            try:
                self.bert_tokenizer = AutoTokenizer.from_pretrained(legal_bert_path)
                self.bert_model = AutoModelForQuestionAnswering.from_pretrained(legal_bert_path)
                if self.device == 0:
                    self.bert_model.to("cuda")
                self.bert_model.eval()
                logger.info(f"Loaded fine-tuned Legal-BERT model from {legal_bert_path}")
            except Exception as e:
                logger.error(f"Error loading Legal-BERT from {legal_bert_path}: {e}")
                self.bert_tokenizer = None
                self.bert_model = None
        else:
            try:
                self.bert_tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
                self.bert_model = AutoModelForQuestionAnswering.from_pretrained("nlpaueb/legal-bert-base-uncased")
                if self.device == 0:
                    self.bert_model.to("cuda")
                self.bert_model.eval()
                logger.info("Loaded pretrained Legal-BERT model (nlpaueb/legal-bert-base-uncased)")
            except Exception as e:
                logger.info(f"Legal-BERT model not found at {legal_bert_path} and fallback failed: {e}")
                self.bert_tokenizer = None
                self.bert_model = None



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
        Main pipeline: OCR → Layout Analysis (LayoutLMv3) → Clause Extraction (LLM).

        Returns structured analysis with layout data, extracted clauses, and risk flags.
        """
        # Step 1: Extract text and page data
        raw_text, page_data = self.extract_text_from_pdf(file_path)

        # Step 2: Run LayoutLMv3 layout analysis
        layout_results = self.analyze_layout(page_data)

        # Step 3: Build enhanced context using layout structure
        enhanced_context = self._build_enhanced_context(raw_text, layout_results)

        # Step 4: Extract clauses using fine-tuned Legal-BERT (with LLM fallback)
        if self.bert_model and self.bert_tokenizer:
            extracted_clauses = self._extract_clauses_with_legal_bert(raw_text)
        else:
            extracted_clauses = self._extract_clauses_with_llm(raw_text)

        # Step 6: Generate risk flags
        risk_flags = self._generate_risk_flags(extracted_clauses, layout_results)

        # Step 7: Compile layout summary
        layout_summary = self._compile_layout_summary(layout_results)
        
        # Step 8: Multi-Agent Pipeline (Obligations -> Impact -> Report)
        try:
            obligations = self._extract_obligations_with_agent(raw_text)
            impact_assessment = self._assess_impact_with_agent(obligations)
        except Exception:
            # Fallback to LLM if agent initialization fails
            obligations = self._extract_obligations_with_llm(raw_text)
            impact_assessment = self._assess_impact_with_llm(obligations)
            
        compliance_report = self._generate_compliance_report_with_llm(
            raw_text[:1000], obligations, impact_assessment
        )

        return {
            "raw_text": raw_text[:500] + "... (truncated)" if len(raw_text) > 500 else raw_text,
            "full_text": raw_text,
            "clauses": extracted_clauses,
            "risk_flags": risk_flags,
            "layout_analysis": layout_summary,
            "pages_analyzed": len(page_data),
            "layout_status": layout_results.get("status", "skipped"),
            "ocr_pages": sum(1 for p in page_data if p.get("ocr_used", False)),
            "obligations": obligations,
            "impact_assessment": impact_assessment,
            "compliance_report": compliance_report,
        }

    CUAD_CLAUSE_QUERIES = {
        "Governing Law": "What is the governing law of the contract?",
        "Termination": "What are the termination rights and notice periods?",
        "Indemnification": "What are the indemnification provisions and obligations?",
        "Limitation of Liability": "What is the limitation of liability or financial cap?",
        "Parties": "Who are the parties entering into this agreement?",
        "Confidentiality": "What are the confidentiality obligations and restrictions?",
        "Intellectual Property": "What are the intellectual property rights and assignments?",
        "Non-Compete / Exclusivity": "What are the non-compete or exclusivity restrictions?"
    }

    def _expand_to_sentence_boundaries(self, text: str, substring: str) -> str:
        """Expands a raw predicted token span to complete sentence boundaries within text."""
        idx = text.find(substring)
        if idx == -1:
            return substring.strip().capitalize()
        
        # Expand backward to start of sentence / newline
        start_idx = idx
        while start_idx > 0 and text[start_idx - 1] not in ['.', '\n', '!', ';']:
            start_idx -= 1
            if idx - start_idx > 250:
                break
        
        # Expand forward to end of sentence / newline
        end_idx = idx + len(substring)
        while end_idx < len(text) and text[end_idx] not in ['.', '\n', '!', ';']:
            end_idx += 1
            if end_idx - (idx + len(substring)) > 250:
                break
        if end_idx < len(text) and text[end_idx] in ['.', '!', ';']:
            end_idx += 1

        expanded = text[start_idx:end_idx].strip()
        return expanded if len(expanded) >= len(substring) else substring.strip()

    def _extract_clauses_with_legal_bert(self, text: str) -> Dict[str, Dict]:
        """
        Extracts clauses using a Hybrid Legal-BERT + LLM ensemble:
        1. Legal-BERT locates precise clause token spans with sentence expansion.
        2. High-confidence spans (Score >= 1.5) are retained.
        3. LLM (Llama 3) supplements any missing or low-confidence clause categories.
        """
        if not self.bert_model or not self.bert_tokenizer:
            logger.warning("Legal-BERT QA model not available. Falling back to LLM.")
            return self._extract_clauses_with_llm(text)

        logger.info("Extracting clauses using Hybrid Legal-BERT + LLM Ensemble...")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            length_function=len
        )
        chunks = splitter.split_text(text)
        extracted_clauses = {}
        device = torch.device("cuda" if self.device == 0 and torch.cuda.is_available() else "cpu")

        for clause_name, query in self.CUAD_CLAUSE_QUERIES.items():
            best_answer = ""
            best_score = -999.0
            best_chunk_idx = 0
            best_chunk_text = ""

            for i, chunk in enumerate(chunks[:10]):
                try:
                    inputs = self.bert_tokenizer(
                        query,
                        chunk,
                        max_length=512,
                        truncation="only_second",
                        return_tensors="pt",
                        padding="max_length"
                    )
                    inputs = {k: v.to(device) for k, v in inputs.items()}
                    with torch.no_grad():
                        outputs = self.bert_model(**inputs)

                    start_logits = outputs.start_logits[0]
                    end_logits = outputs.end_logits[0]

                    start_idx = torch.argmax(start_logits).item()
                    end_idx = torch.argmax(end_logits).item()

                    if end_idx >= start_idx and (end_idx - start_idx) < 150 and start_idx > 0:
                        token_ids = inputs["input_ids"][0][start_idx : end_idx + 1]
                        ans_text = self.bert_tokenizer.decode(token_ids, skip_special_tokens=True).strip()
                        score = float(start_logits[start_idx] + end_logits[end_idx])

                        if len(ans_text) > 3 and score > best_score:
                            best_score = score
                            best_answer = ans_text
                            best_chunk_idx = i
                            best_chunk_text = chunk
                except Exception as e:
                    logger.debug(f"Legal-BERT extraction error for '{clause_name}' on chunk {i}: {e}")

            # Require calibrated score threshold (Score >= 1.5) for Legal-BERT span retention
            if best_answer and best_score >= 1.5:
                expanded_span = self._expand_to_sentence_boundaries(best_chunk_text, best_answer)
                extracted_clauses[clause_name] = {
                    "answer": expanded_span,
                    "score": round(best_score, 4),
                    "chunk_source": best_chunk_idx,
                    "model": "Legal-BERT (Fine-Tuned)"
                }

        # Hybrid Supplement: Use Llama 3 to extract full structured clauses for missing categories
        if hasattr(self, 'llm') and self.llm:
            try:
                logger.info("Supplementing remaining clause categories with Llama 3...")
                llm_clauses = self._extract_clauses_with_llm(text)
                for k, v in llm_clauses.items():
                    if k not in extracted_clauses:
                        extracted_clauses[k] = v
            except Exception as e:
                logger.warning(f"Failed to supplement clauses with LLM: {e}")

        if not extracted_clauses:
            logger.info("Legal-BERT produced no high-confidence clause spans. Falling back to LLM.")
            return self._extract_clauses_with_llm(text)

        return extracted_clauses

    def _extract_clauses_with_llm(self, text: str) -> Dict[str, Dict]:
        """Extracts clauses from the text using LLM and text chunking."""
        if not hasattr(self, 'llm') or not self.llm:
            return {"Error": {"answer": "LLM not initialized", "score": 0.0}}
            
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000, 
            chunk_overlap=400,
            length_function=len
        )
        chunks = splitter.split_text(text)
        
        all_clauses = {}
        
        system_prompt = (
            "You are an expert legal AI assistant. Your task is to extract all material clauses from the provided contract text chunk. "
            "Return the output strictly as a JSON object where keys are the clause names (e.g. 'Governing Law', 'Termination', 'Parties', etc.) "
            "and values are the extracted text of the clause. If no clauses are found, return {}. Do not include markdown formatting or explanations."
        )
        
        for i, chunk in enumerate(chunks):
            try:
                response = self.llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Extract clauses from this text:\n\n{chunk}")
                ])
                import re
                content = response.content.strip()
                # Use regex to find the first JSON object block to avoid extra text
                match = re.search(r'\{[\s\S]*\}', content)
                if match:
                    content = match.group(0)
                else:
                    content = "{}"
                    
                extracted = json.loads(content)
                for k, v in extracted.items():
                    if k not in all_clauses:
                        all_clauses[k] = {"answer": str(v), "score": 1.0, "chunk_source": i}
                    else:
                        all_clauses[k]["answer"] += f"\n\n{v}"
            except Exception as e:
                logger.error(f"Error extracting clauses from chunk {i}: {e}")
                
        return all_clauses

    def _generate_risk_flags(
        self,
        clauses: Dict[str, Dict],
        layout_results: Dict[str, Any],
    ) -> List[Optional[Dict[str, str]]]:
        """Generate risk flags based on extracted clauses and layout analysis."""
        risk_flags = []

        # 1. LLM-based risk extraction based on clause content
        if hasattr(self, 'llm') and self.llm and clauses:
            # Prepare context
            clauses_text = ""
            for k, v in clauses.items():
                clauses_text += f"{k}:\n{v.get('answer', '')}\n\n"

            system_prompt = (
                "You are an expert legal risk analyst. Review the provided contract clauses and identify any legal, "
                "financial, or business risks (e.g., unlimited liability, one-sided termination, missing governing law, unfavorable terms, etc.). "
                "Output strictly as a JSON array of objects. Each object must have 'type' (short title of the risk), "
                "'description' (detailed explanation of the risk), 'severity' ('High', 'Medium', or 'Low'), "
                "and 'reasoning' (XAI explanation: precisely why the AI model flagged this as a risk based on standard practice). "
                "If no risks are found, return []. Do not include markdown formatting or conversational text."
            )

            from langchain_text_splitters import RecursiveCharacterTextSplitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=4000,
                chunk_overlap=400,
                separators=["\n\n", "\n", " ", ""]
            )
            
            chunks = text_splitter.split_text(clauses_text)
            
            for chunk in chunks:
                try:
                    response = self.llm.invoke([
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=f"Identify risks in these clauses:\n\n{chunk}")
                    ])
                    
                    content = response.content.strip()
                    import re
                    # Use regex to find the first JSON array block
                    match = re.search(r'\[[\s\S]*\]', content)
                    if match:
                        content = match.group(0)
                    else:
                        content = "[]"
                        
                    extracted_risks = json.loads(content)
                    if isinstance(extracted_risks, list):
                        for r in extracted_risks:
                            if "type" in r and "description" in r and "severity" in r:
                                # ensure reasoning exists
                                if "reasoning" not in r:
                                    r["reasoning"] = "Standard risk pattern detected."
                                # avoid exact duplicates
                                if not any(existing.get("description") == r.get("description") for existing in risk_flags):
                                    risk_flags.append(r)
                except Exception as e:
                    logger.error(f"Error during LLM risk extraction for a chunk: {e}")

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

    def _extract_obligations_with_llm(self, text: str) -> List[Dict]:
        """Runs the Obligation Extractor system prompt on the text."""
        if not hasattr(self, 'llm') or not self.llm:
            return []
            
        system_prompt = OBLIGATION_EXTRACTOR_SYSTEM_PROMPT + "\n\nOutput strictly as a JSON array of objects with keys: Text, Severity, Deadline, Affected Entity, Category, Reasoning (XAI explanation: why this text is a mandatory compliance obligation). Do NOT include markdown."
        
        try:
            # We truncate the text slightly to avoid context limits, focusing on the first 6000 chars which usually contain core obligations
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Extract obligations from this document:\n\n{text[:6000]}")
            ])
            content = response.content.strip()
            import re
            match = re.search(r'\[[\s\S]*\]', content)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            logger.error(f"Error during Obligation Extraction: {e}")
        return []

    def _assess_impact_with_llm(self, obligations: List[Dict]) -> List[Dict]:
        """Runs the Impact Assessor system prompt on the extracted obligations."""
        if not hasattr(self, 'llm') or not self.llm or not obligations:
            return []
            
        system_prompt = IMPACT_ASSESSOR_SYSTEM_PROMPT + "\n\nOutput strictly as a JSON array of objects mapping to the input obligations, with keys: Action Items, Departments, Risk Level, Effort. Do NOT include markdown."
        
        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Assess the impact of these obligations:\n\n{json.dumps(obligations)}")
            ])
            content = response.content.strip()
            import re
            match = re.search(r'\[[\s\S]*\]', content)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            logger.error(f"Error during Impact Assessment: {e}")
        return []

    def _extract_obligations_with_agent(self, text: str) -> List[Dict]:
        """Runs the autonomous Obligation Extractor Agent on the text."""
        if not hasattr(self, 'llm') or not self.llm:
            return []
        try:
            from .agents.obligation_extractor import ObligationExtractorAgent
            agent = ObligationExtractorAgent()
            return agent.invoke_agent(self.llm, text)
        except Exception as e:
            logger.error(f"Error invoking ObligationExtractorAgent: {e}")
            return self._extract_obligations_with_llm(text)

    def _assess_impact_with_agent(self, obligations: List[Dict]) -> List[Dict]:
        """Runs the autonomous Impact Assessor Agent on the extracted obligations."""
        if not hasattr(self, 'llm') or not self.llm or not obligations:
            return []
        try:
            from .agents.impact_assessor import ImpactAssessorAgent
            import asyncio
            agent = ImpactAssessorAgent()
            return asyncio.run(agent.invoke_agent(self.llm, obligations))
        except Exception as e:
            logger.error(f"Error invoking ImpactAssessorAgent: {e}")
            return self._assess_impact_with_llm(obligations)

    def _generate_compliance_report_with_llm(self, summary_text: str, obligations: List[Dict], impacts: List[Dict]) -> str:
        """Runs the Compliance Reporter system prompt to synthesize a report."""
        if not hasattr(self, 'llm') or not self.llm:
            return "Compliance report could not be generated."
            
        system_prompt = COMPLIANCE_REPORTER_SYSTEM_PROMPT + "\n\nOutput the final report in clean markdown format."
        
        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Generate a compliance report based on this summary:\n{summary_text}\n\nObligations:\n{json.dumps(obligations)}\n\nImpacts:\n{json.dumps(impacts)}")
            ])
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error during Compliance Reporting: {e}")
            return "Error generating compliance report."

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
