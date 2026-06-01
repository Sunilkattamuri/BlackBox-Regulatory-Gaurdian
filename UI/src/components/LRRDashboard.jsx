import React, { useEffect } from 'react';
import { RefreshCw, ExternalLink, Activity, ArrowRight } from 'lucide-react';
import { useStore } from '../store/useStore';

export default function LRRDashboard() {
  const { lrrUpdates, setLrrUpdates } = useStore();

  useEffect(() => {
    if (lrrUpdates.length === 0) {
      setLrrUpdates([
        {
          id: 1,
          title: "Master Direction - Classification, Valuation and Operation of Investment Portfolio of Commercial Banks",
          source: "RBI",
          published_date: new Date().toISOString(),
          summary: "Updated guidelines on how commercial banks should classify and value their investment portfolios.",
          obligations: [
            { policy: "Investment Valuation Policy", impact: "High", action: "Update valuation models for Q3." }
          ]
        },
        {
          id: 2,
          title: "Guidelines on Default Loss Guarantee (DLG) in Digital Lending",
          source: "RBI",
          published_date: new Date(Date.now() - 86400000).toISOString(), // Yesterday
          summary: "Regulatory framework for DLG arrangements in digital lending.",
          obligations: [
            { policy: "Digital Lending Policy", impact: "Medium", action: "Review DLG agreements with fintech partners." }
          ]
        }
      ]);
    }
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-light text-white">Regulatory Lifecycle Management</h2>
          <p className="text-slate-400 mt-1">Continuous monitoring of RBI notifications and policy mapping</p>
        </div>
        
        <button className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg flex items-center gap-2 transition-all border border-white/10 shadow-lg">
          <RefreshCw className="w-4 h-4" />
          <span className="font-medium text-sm">Sync Feeds</span>
        </button>
      </div>

      <div className="grid gap-6">
        {lrrUpdates.map(update => (
          <div key={update.id} className="bg-slate-900 border border-white/10 rounded-xl overflow-hidden shadow-xl transition-all hover:border-indigo-500/30 group">
            <div className="p-6 border-b border-white/5">
              <div className="flex justify-between items-start gap-4">
                <div>
                  <div className="flex items-center gap-3 mb-3">
                    <span className="px-2.5 py-1 bg-indigo-500/20 text-indigo-300 text-xs font-bold rounded uppercase tracking-wider border border-indigo-500/20">
                      {update.source}
                    </span>
                    <span className="text-sm text-slate-500 flex items-center gap-1">
                      <Activity className="w-3.5 h-3.5" />
                      {new Date(update.published_date).toLocaleDateString()}
                    </span>
                  </div>
                  <h3 className="text-xl font-medium text-white mb-2 leading-snug">{update.title}</h3>
                  <p className="text-slate-400 text-sm leading-relaxed">{update.summary}</p>
                </div>
                <button className="p-2 text-slate-500 hover:text-indigo-400 bg-slate-800 rounded-lg transition-colors shrink-0">
                  <ExternalLink className="w-5 h-5" />
                </button>
              </div>
            </div>
            
            <div className="bg-slate-950 p-6">
              <h4 className="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-wider">Automated Policy Impact Mapping</h4>
              <div className="space-y-3">
                {update.obligations.map((ob, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-white/5">
                    <div className="flex items-center gap-4">
                      <div className={`px-2 py-1 rounded text-xs font-bold border ${
                        ob.impact === 'High' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 
                        ob.impact === 'Medium' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 
                        'bg-blue-500/10 text-blue-400 border-blue-500/20'
                      }`}>
                        {ob.impact} IMPACT
                      </div>
                      <span className="text-sm font-medium text-slate-200">{ob.policy}</span>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      <ArrowRight className="w-4 h-4 text-slate-600" />
                      <span className="text-sm text-slate-400">{ob.action}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
