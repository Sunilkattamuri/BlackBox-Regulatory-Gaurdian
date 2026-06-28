import React, { useState, useEffect, useRef } from 'react';
import { ArrowLeft, AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function ContractViewer({ contract, onBack }) {
  const [activeClause, setActiveClause] = useState(null);
  const scrollRef = useRef(null);

  const extracted = contract?.extracted_data || {};
  
  // Format clauses from dict to array
  const clauses = Object.entries(extracted.clauses || {}).map(([question, data]) => ({
    type: question
      .replace('What is the ', '')
      .replace('?', '')
      .replace('Are there any ', '')
      .replace('Is there ', '')
      .replace('Is there an ', ''),
    text: data.answer,
    confidence: data.score
  }));

  const risks = (extracted.risk_flags || []).map(r => ({
    type: r.type,
    desc: r.description,
    severity: r.severity
  }));

  const obligations = Array.isArray(extracted.obligations) ? extracted.obligations : [];
  const impacts = Array.isArray(extracted.impact_assessment) ? extracted.impact_assessment : [];
  const complianceReport = extracted.compliance_report || null;

  useEffect(() => {
    if (activeClause && scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [activeClause]);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <button 
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back to Dashboard</span>
        </button>
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-400">Click any clause to highlight it in the document</span>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-3 gap-6 overflow-hidden">
        {/* PDF Document Viewer (Mocked) */}
        <div className="col-span-2 bg-slate-900 border border-white/10 rounded-xl overflow-hidden flex flex-col relative">
          <div className="p-4 bg-slate-800/50 border-b border-white/5 flex items-center justify-between z-20">
            <h3 className="font-medium text-slate-200">{contract.filename}</h3>
            <span className="text-xs text-slate-500">{extracted.pages_analyzed ? `${extracted.pages_analyzed} Pages Processed` : 'Document Viewer'}</span>
          </div>
          
          <div className="flex-1 p-8 overflow-auto text-slate-300 space-y-6 text-sm leading-relaxed relative">
            <div className="whitespace-pre-wrap font-mono text-sm">
              {(() => {
                const text = extracted.full_text || extracted.raw_text || "No text could be extracted from this document.";
                if (!activeClause || !activeClause.text) return text;

                // Robust matching for PDF text (which often has weird line breaks)
                let index = -1;
                let matchLength = 0;
                
                try {
                  // Use the first 40 characters to find the start of the clause
                  const searchStr = activeClause.text.substring(0, 40);
                  // Escape regex chars and replace spaces with whitespace matcher
                  const safeText = searchStr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                  const regexStr = safeText.replace(/\s+/g, '\\s+');
                  const regex = new RegExp(regexStr, 'i');
                  
                  const match = text.match(regex);
                  if (match) {
                    index = match.index;
                    // Highlight a generous chunk that should cover the clause text
                    matchLength = Math.min(activeClause.text.length + 100, text.length - index);
                  }
                } catch(e) {
                  console.error("Highlighting regex error", e);
                }

                if (index !== -1) {
                  return (
                    <>
                      {text.substring(0, index)}
                      <mark 
                        ref={scrollRef}
                        className="bg-emerald-500/40 text-emerald-50 rounded px-1 shadow-[0_0_15px_rgba(16,185,129,0.4)] transition-all duration-500"
                      >
                        {text.substring(index, index + matchLength)}
                      </mark>
                      {text.substring(index + matchLength)}
                    </>
                  );
                }
                
                return text;
              })()}
            </div>
          </div>
        </div>

        {/* Sidebar Analysis */}
        <div className="col-span-1 space-y-6 overflow-auto">
          
          <div className="bg-slate-900 border border-white/10 rounded-xl p-5">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
              <CheckCircle2 className="w-5 h-5 text-indigo-400" />
              Extracted Clauses
            </h3>
            <div className="space-y-4">
              {clauses.map((clause, i) => (
                <div 
                  key={i} 
                  onClick={() => setActiveClause(clause)}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors duration-200 ${
                    activeClause === clause 
                      ? 'bg-indigo-900/40 border-indigo-500/50 shadow-inner shadow-indigo-500/10' 
                      : 'bg-slate-800/50 border-white/5 hover:bg-slate-800 hover:border-white/10'
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">{clause.type}</span>
                  </div>
                  <p className="text-sm text-slate-300 line-clamp-3">{clause.text}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-900 border border-amber-500/20 rounded-xl p-5 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-bl-[100px]" />
            <h3 className="text-lg font-semibold text-amber-400 flex items-center gap-2 mb-4 relative">
              <AlertTriangle className="w-5 h-5" />
              Identified Risks
            </h3>
            <div className="space-y-3 relative">
              {risks.length > 0 ? risks.map((risk, i) => (
                <div key={i} className={`flex gap-3 items-start bg-slate-950/50 p-3 rounded-lg border ${
                  risk.severity === 'High' ? 'border-red-500/20' : 
                  risk.severity === 'Medium' ? 'border-amber-500/20' : 'border-yellow-500/20'
                }`}>
                  <div className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${
                    risk.severity === 'High' ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]' : 
                    risk.severity === 'Medium' ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.8)]' : 'bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.8)]'
                  }`} />
                  <div>
                    <p className={`text-sm font-semibold ${
                      risk.severity === 'High' ? 'text-red-400' : 
                      risk.severity === 'Medium' ? 'text-amber-400' : 'text-yellow-400'
                    }`}>{risk.type}</p>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">{risk.desc}</p>
                  </div>
                </div>
              )) : (
                <div className="bg-emerald-500/10 border border-emerald-500/30 p-4 rounded-lg flex items-start gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-emerald-400">No Critical Risks Identified</p>
                    <p className="text-xs text-emerald-500/80 mt-1">All essential clauses appear to be present and structured properly in this document.</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {obligations.length > 0 && (
            <div className="bg-slate-900 border border-blue-500/20 rounded-xl p-5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-bl-[100px]" />
              <h3 className="text-lg font-semibold text-blue-400 flex items-center gap-2 mb-4 relative">
                Extracted Obligations
              </h3>
              <div className="space-y-3 relative">
                {obligations.map((obs, i) => (
                  <div key={i} className="bg-slate-950/50 p-3 rounded-lg border border-blue-500/10">
                    <p className="text-sm text-slate-200">{obs.Text || obs.text}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">
                        {obs.Severity || obs.severity || 'Medium'}
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">
                        {obs.Deadline || obs.deadline || 'No deadline'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {impacts.length > 0 && (
            <div className="bg-slate-900 border border-purple-500/20 rounded-xl p-5 relative overflow-hidden">
              <h3 className="text-lg font-semibold text-purple-400 flex items-center gap-2 mb-4">
                Impact Assessment
              </h3>
              <div className="space-y-3">
                {impacts.map((imp, i) => (
                  <div key={i} className="bg-slate-950/50 p-3 rounded-lg border border-purple-500/10">
                    <p className="text-xs font-semibold text-purple-300 mb-1">Affected Departments:</p>
                    <p className="text-xs text-slate-400 mb-2">
                      {Array.isArray(imp.Departments) 
                        ? imp.Departments.map(d => typeof d === 'string' ? d : (d.Name || d.Department || JSON.stringify(d))).join(', ') 
                        : (typeof imp.Departments === 'string' ? imp.Departments : JSON.stringify(imp.Departments || 'None'))}
                    </p>
                    <p className="text-xs font-semibold text-purple-300 mb-1">Action Items:</p>
                    <ul className="text-xs text-slate-400 list-disc pl-4">
                      {(Array.isArray(imp["Action Items"]) ? imp["Action Items"] : []).map((item, j) => (
                        <li key={j}>
                          {typeof item === 'string' ? item : (
                            <span>
                              {item.Policy && <span className="font-medium text-slate-300">{item.Policy}: </span>}
                              {item.Description || item.Action || JSON.stringify(item)}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}

          {complianceReport && (
            <div className="bg-slate-900 border border-emerald-500/20 rounded-xl p-5 relative overflow-hidden">
              <h3 className="text-lg font-semibold text-emerald-400 flex items-center gap-2 mb-4">
                Compliance Report
              </h3>
              <div className="text-xs text-slate-300 prose prose-invert prose-sm max-w-none whitespace-pre-wrap">
                {complianceReport}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
