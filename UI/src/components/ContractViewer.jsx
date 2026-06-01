import React, { useState } from 'react';
import { ArrowLeft, AlertTriangle, ShieldCheck, CheckCircle2 } from 'lucide-react';

export default function ContractViewer({ contract, onBack }) {
  const [showXai, setShowXai] = useState(false);

  // Mock analysis data
  const clauses = [
    { type: "Governing Law", text: "This Agreement shall be governed by the laws of India.", confidence: 0.98 },
    { type: "Termination", text: "Either party may terminate this Agreement upon 30 days written notice.", confidence: 0.95 },
    { type: "Confidentiality", text: "Receiving Party shall hold Confidential Information in strict confidence.", confidence: 0.99 }
  ];

  const risks = [
    { type: "Missing Clause", desc: "No specific Data Privacy (DPDP Act) clause detected.", severity: "High" },
    { type: "Ambiguous Term", desc: "Termination without cause period is unusually short (30 days).", severity: "Medium" }
  ];

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
          <button 
            onClick={() => setShowXai(!showXai)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
              showXai ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            {showXai ? 'Hide XAI overlay' : 'Show SHAP Explanations'}
          </button>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-3 gap-6 overflow-hidden">
        {/* PDF Document Viewer (Mocked) */}
        <div className="col-span-2 bg-slate-900 border border-white/10 rounded-xl overflow-hidden flex flex-col">
          <div className="p-4 bg-slate-800/50 border-b border-white/5 flex items-center justify-between">
            <h3 className="font-medium text-slate-200">{contract.filename}</h3>
            <span className="text-xs text-slate-500">Page 1 of 12</span>
          </div>
          <div className="flex-1 p-8 overflow-auto text-slate-300 space-y-6 text-sm leading-relaxed relative">
            
            {showXai && (
              <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-[1px] p-8 z-10 pointer-events-none">
                <div className="bg-purple-500/20 border border-purple-500/30 p-4 rounded-lg inline-block">
                  <p className="text-purple-300 font-mono text-xs mb-2">SHAP Values (Legal-BERT)</p>
                  <p>
                    This Agreement shall be governed by the laws of <span className="bg-emerald-500/40 px-1 rounded text-emerald-100">India</span>.
                    Either party may <span className="bg-emerald-500/20 px-1 rounded">terminate</span> this Agreement upon <span className="bg-emerald-500/60 px-1 rounded text-emerald-100">30 days</span> written notice.
                  </p>
                </div>
              </div>
            )}

            <p className="font-bold text-lg mb-4 text-white">MASTER SERVICE AGREEMENT</p>
            <p>This Master Service Agreement ("Agreement") is entered into as of the Effective Date...</p>
            
            <div className={`p-2 -mx-2 rounded ${showXai ? '' : 'bg-indigo-500/10 border-l-2 border-indigo-500'}`}>
              <p className="font-semibold text-slate-200">1. Governing Law</p>
              <p>This Agreement shall be governed by the laws of India.</p>
            </div>

            <p>The parties agree to the following terms and conditions regarding the services to be provided...</p>
            
            <div className={`p-2 -mx-2 rounded ${showXai ? '' : 'bg-indigo-500/10 border-l-2 border-indigo-500'}`}>
              <p className="font-semibold text-slate-200">2. Termination</p>
              <p>Either party may terminate this Agreement upon 30 days written notice.</p>
            </div>

            <p>...</p>
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
                <div key={i} className="bg-slate-800/50 p-3 rounded-lg border border-white/5">
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">{clause.type}</span>
                    <span className="text-[10px] text-slate-500 bg-slate-900 px-2 py-0.5 rounded">
                      {(clause.confidence * 100).toFixed(0)}% conf.
                    </span>
                  </div>
                  <p className="text-sm text-slate-300">{clause.text}</p>
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
              {risks.map((risk, i) => (
                <div key={i} className="flex gap-3 items-start bg-slate-950/50 p-3 rounded-lg">
                  <div className={`mt-0.5 w-2 h-2 rounded-full ${risk.severity === 'High' ? 'bg-red-500' : 'bg-amber-500'}`} />
                  <div>
                    <p className="text-sm font-medium text-slate-200">{risk.type}</p>
                    <p className="text-xs text-slate-400 mt-1">{risk.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
