import React, { useState, useEffect, useRef } from 'react';
import { ArrowLeft, AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function ContractViewer({ contract, onBack }) {
  const [activeHighlight, setActiveHighlight] = useState(null);
  const [activeTab, setActiveTab] = useState('clauses');
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
    severity: r.severity,
    reasoning: r.reasoning
  }));

  const obligations = Array.isArray(extracted.obligations) ? extracted.obligations : [];
  const impacts = Array.isArray(extracted.impact_assessment) ? extracted.impact_assessment : [];
  const complianceReport = extracted.compliance_report || null;

  useEffect(() => {
    if (activeHighlight && scrollRef.current && activeTab !== 'report') {
      scrollRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [activeHighlight, activeTab]);

  // Clear highlight when switching tabs
  useEffect(() => {
    setActiveHighlight(null);
  }, [activeTab]);

  const tabs = [
    { id: 'clauses', label: 'Clauses', count: clauses.length, color: 'indigo' },
    { id: 'obligations', label: 'Obligations', count: obligations.length, color: 'blue' },
    { id: 'risks', label: 'Risks', count: risks.length, color: 'amber' },
    { id: 'impacts', label: 'Impacts', count: impacts.length, color: 'purple' },
    ...(complianceReport ? [{ id: 'report', label: 'Compliance Report', count: 1, color: 'emerald' }] : [])
  ];

  return (
    <div className="h-full flex flex-col space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button 
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors bg-slate-800/50 px-4 py-2 rounded-lg"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back to Dashboard</span>
        </button>
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium text-slate-200">{contract.filename}</span>
          <span className="text-xs text-slate-500 bg-slate-800 px-3 py-1 rounded-full">
            {extracted.pages_analyzed ? `${extracted.pages_analyzed} Pages Processed` : 'Document Viewer'}
          </span>
        </div>
      </div>

      {/* Metric Cards (Tabs) */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const bgColors = {
            indigo: isActive ? 'bg-indigo-600 border-indigo-500' : 'bg-slate-800/50 hover:bg-slate-800 border-white/5',
            blue: isActive ? 'bg-blue-600 border-blue-500' : 'bg-slate-800/50 hover:bg-slate-800 border-white/5',
            amber: isActive ? 'bg-amber-600 border-amber-500' : 'bg-slate-800/50 hover:bg-slate-800 border-white/5',
            purple: isActive ? 'bg-purple-600 border-purple-500' : 'bg-slate-800/50 hover:bg-slate-800 border-white/5',
            emerald: isActive ? 'bg-emerald-600 border-emerald-500' : 'bg-slate-800/50 hover:bg-slate-800 border-white/5',
          };
          const textColors = {
            indigo: isActive ? 'text-white' : 'text-indigo-400',
            blue: isActive ? 'text-white' : 'text-blue-400',
            amber: isActive ? 'text-white' : 'text-amber-400',
            purple: isActive ? 'text-white' : 'text-purple-400',
            emerald: isActive ? 'text-white' : 'text-emerald-400',
          };

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`p-4 rounded-xl border transition-all duration-200 text-left flex flex-col justify-between h-24 ${bgColors[tab.color]}`}
            >
              <span className={`text-sm font-semibold ${isActive ? 'text-white/80' : 'text-slate-400'}`}>
                {tab.label}
              </span>
              <div className={`text-3xl font-light ${textColors[tab.color]}`}>
                {tab.count}
              </div>
            </button>
          );
        })}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'report' ? (
          /* Full Screen Report View */
          <div className="h-full bg-slate-900 border border-emerald-500/20 rounded-xl p-8 overflow-auto">
            <h3 className="text-2xl font-light text-emerald-400 flex items-center gap-3 mb-8 pb-4 border-b border-emerald-500/20">
              <CheckCircle2 className="w-8 h-8" />
              Executive Compliance Report
            </h3>
            <div className="text-slate-300 prose prose-invert max-w-4xl mx-auto whitespace-pre-wrap font-sans leading-relaxed">
              {complianceReport}
            </div>
          </div>
        ) : (
          /* Split View for PDF + Context Sidebar */
          <div className="h-full grid grid-cols-3 gap-6">
            {/* Document Viewer */}
            <div className="col-span-2 bg-slate-900 border border-white/10 rounded-xl overflow-hidden flex flex-col relative">
              {['clauses', 'obligations', 'risks'].includes(activeTab) && (
                <div className="absolute top-4 right-4 z-30">
                  <span className="text-xs bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-full border border-indigo-500/20 shadow-lg">
                    Click any item to highlight it in the document
                  </span>
                </div>
              )}
              <div className="flex-1 p-8 overflow-auto text-slate-300 space-y-6 text-sm leading-relaxed relative font-mono">
                {(() => {
                  const text = extracted.full_text || extracted.raw_text || "No text could be extracted from this document.";
                  if (activeTab === 'report' || !activeHighlight) return text;

                  let index = -1;
                  let matchLength = 0;
                  try {
                    const searchStr = activeHighlight.substring(0, 40);
                    const safeText = searchStr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    const regexStr = safeText.replace(/\s+/g, '\\s+');
                    const regex = new RegExp(regexStr, 'i');
                    
                    const match = text.match(regex);
                    if (match) {
                      index = match.index;
                      matchLength = Math.min(activeHighlight.length + 100, text.length - index);
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

            {/* Dynamic Sidebar */}
            <div className="col-span-1 overflow-auto pr-2">
              
              {/* CLAUSES TAB */}
              {activeTab === 'clauses' && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-white flex items-center gap-2 sticky top-0 bg-[#0f172a] pt-2 pb-4 z-10">
                    <CheckCircle2 className="w-5 h-5 text-indigo-400" />
                    Extracted Clauses
                  </h3>
                  {clauses.map((clause, i) => (
                    <div 
                      key={i} 
                      onClick={() => setActiveHighlight(clause.text)}
                      className={`p-4 rounded-xl border cursor-pointer transition-all duration-200 ${
                        activeHighlight === clause.text 
                          ? 'bg-indigo-900/40 border-indigo-500/50 shadow-[0_0_20px_rgba(99,102,241,0.1)]' 
                          : 'bg-slate-900 border-white/5 hover:bg-slate-800 hover:border-white/10'
                      }`}
                    >
                      <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider block mb-2">{clause.type}</span>
                      <p className="text-sm text-slate-300 line-clamp-4 leading-relaxed">{clause.text}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* OBLIGATIONS TAB */}
              {activeTab === 'obligations' && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-white flex items-center gap-2 sticky top-0 bg-[#0f172a] pt-2 pb-4 z-10">
                    <CheckCircle2 className="w-5 h-5 text-blue-400" />
                    Regulatory Obligations
                  </h3>
                  {obligations.length === 0 ? (
                    <p className="text-sm text-slate-500">No obligations found.</p>
                  ) : obligations.map((obs, i) => {
                    const obsText = obs.Text || obs.text;
                    return (
                      <div 
                        key={i} 
                        onClick={() => setActiveHighlight(obsText)}
                        className={`p-4 rounded-xl border cursor-pointer transition-all duration-200 ${
                          activeHighlight === obsText 
                            ? 'bg-blue-900/40 border-blue-500/50 shadow-[0_0_20px_rgba(59,130,246,0.1)]' 
                            : 'bg-slate-900 border-blue-500/20 hover:border-blue-500/40'
                        }`}
                      >
                        <p className="text-sm text-slate-200 leading-relaxed mb-3">{obsText}</p>
                        {(obs.Reasoning || obs.reasoning) && (
                          <div className="mb-3 bg-blue-950/40 p-3 rounded-lg border border-blue-500/20">
                            <p className="text-xs font-semibold text-blue-400 mb-1 flex items-center gap-1.5 uppercase tracking-wide">
                              <span className="text-[14px]">🤖</span> XAI Reasoning
                            </p>
                            <p className="text-xs text-blue-200/80 leading-relaxed italic">"{obs.Reasoning || obs.reasoning}"</p>
                          </div>
                        )}
                        <div className="flex flex-wrap gap-2">
                        <span className={`text-[10px] font-semibold px-2.5 py-1 rounded-full uppercase tracking-wider ${
                          (obs.Severity || obs.severity) === 'Critical' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                          (obs.Severity || obs.severity) === 'High' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
                          (obs.Severity || obs.severity) === 'Medium' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                          'bg-slate-800 text-slate-400 border border-slate-700'
                        }`}>
                          {obs.Severity || obs.severity || 'Medium'}
                        </span>
                        <span className="text-[10px] px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                          Due: {obs.Deadline || obs.deadline || 'No deadline'}
                        </span>
                      </div>
                    </div>
                    );
                  })}
                </div>
              )}

              {/* RISKS TAB */}
              {activeTab === 'risks' && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-white flex items-center gap-2 sticky top-0 bg-[#0f172a] pt-2 pb-4 z-10">
                    <AlertTriangle className="w-5 h-5 text-amber-400" />
                    Identified Risks
                  </h3>
                  {risks.length > 0 ? risks.map((risk, i) => (
                    <div 
                      key={i} 
                      onClick={() => setActiveHighlight(risk.desc)}
                      className={`flex gap-4 items-start p-4 rounded-xl border cursor-pointer transition-all duration-200 ${
                        activeHighlight === risk.desc
                          ? 'bg-amber-900/20 border-amber-500/50 shadow-[0_0_20px_rgba(245,158,11,0.1)]'
                          : risk.severity === 'High' ? 'bg-slate-900 border-red-500/30 hover:border-red-500/50' 
                          : risk.severity === 'Medium' ? 'bg-slate-900 border-amber-500/30 hover:border-amber-500/50' 
                          : 'bg-slate-900 border-yellow-500/30 hover:border-yellow-500/50'
                      }`}
                    >
                      <div className={`mt-1.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                        risk.severity === 'High' ? 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.8)]' : 
                        risk.severity === 'Medium' ? 'bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.8)]' : 'bg-yellow-500 shadow-[0_0_10px_rgba(234,179,8,0.8)]'
                      }`} />
                      <div>
                        <p className={`text-sm font-semibold mb-1 ${
                          risk.severity === 'High' ? 'text-red-400' : 
                          risk.severity === 'Medium' ? 'text-amber-400' : 'text-yellow-400'
                        }`}>{risk.type}</p>
                        <p className="text-sm text-slate-400 leading-relaxed mb-2">{risk.desc}</p>
                        {risk.reasoning && (
                          <div className={`p-3 rounded-lg border ${
                            risk.severity === 'High' ? 'bg-red-950/30 border-red-500/20' : 
                            risk.severity === 'Medium' ? 'bg-amber-950/30 border-amber-500/20' : 'bg-yellow-950/30 border-yellow-500/20'
                          }`}>
                            <p className={`text-xs font-semibold mb-1 flex items-center gap-1.5 uppercase tracking-wide ${
                              risk.severity === 'High' ? 'text-red-400/80' : 
                              risk.severity === 'Medium' ? 'text-amber-400/80' : 'text-yellow-400/80'
                            }`}>
                              <span className="text-[14px]">🤖</span> XAI Reasoning
                            </p>
                            <p className={`text-xs leading-relaxed italic ${
                              risk.severity === 'High' ? 'text-red-200/70' : 
                              risk.severity === 'Medium' ? 'text-amber-200/70' : 'text-yellow-200/70'
                            }`}>"{risk.reasoning}"</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )) : (
                    <div className="bg-emerald-500/10 border border-emerald-500/30 p-5 rounded-xl flex items-start gap-3">
                      <CheckCircle2 className="w-6 h-6 text-emerald-400 flex-shrink-0" />
                      <div>
                        <p className="text-base font-semibold text-emerald-400">No Critical Risks Identified</p>
                        <p className="text-sm text-emerald-500/80 mt-1 leading-relaxed">All essential clauses appear to be present and structured properly in this document.</p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* IMPACTS TAB */}
              {activeTab === 'impacts' && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-white flex items-center gap-2 sticky top-0 bg-[#0f172a] pt-2 pb-4 z-10">
                    <CheckCircle2 className="w-5 h-5 text-purple-400" />
                    Impact Assessment
                  </h3>
                  {impacts.length === 0 ? (
                    <p className="text-sm text-slate-500">No impact assessments found.</p>
                  ) : impacts.map((imp, i) => (
                    <div key={i} className="bg-slate-900 p-5 rounded-xl border border-purple-500/20">
                      <p className="text-xs font-bold uppercase tracking-wider text-purple-400 mb-2">Affected Departments</p>
                      <p className="text-sm text-slate-300 mb-4 bg-purple-500/5 p-3 rounded-lg border border-purple-500/10">
                        {Array.isArray(imp.Departments) 
                          ? imp.Departments.map(d => typeof d === 'string' ? d : (d.Name || d.Department || JSON.stringify(d))).join(', ') 
                          : (typeof imp.Departments === 'string' ? imp.Departments : JSON.stringify(imp.Departments || 'None'))}
                      </p>
                      <p className="text-xs font-bold uppercase tracking-wider text-purple-400 mb-2">Action Items</p>
                      <ul className="text-sm text-slate-400 space-y-2">
                        {(Array.isArray(imp["Action Items"]) ? imp["Action Items"] : []).map((item, j) => (
                          <li key={j} className="flex gap-2 items-start">
                            <span className="text-purple-500 mt-1">•</span>
                            <span>
                              {typeof item === 'string' ? item : (
                                <>
                                  {item.Policy && <span className="font-semibold text-slate-300">{item.Policy}: </span>}
                                  {item.Description || item.Action || JSON.stringify(item)}
                                </>
                              )}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}

            </div>
          </div>
        )}
      </div>
    </div>
  );
}
