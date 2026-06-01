import React, { useState, useEffect } from 'react';
import { Upload, File, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { useStore } from '../store/useStore';
import ContractViewer from './ContractViewer';

export default function ContractDashboard() {
  const { contracts, setContracts, activeContract, setActiveContract } = useStore();
  const [uploading, setUploading] = useState(false);

  // Mock fetching contracts
  useEffect(() => {
    if (contracts.length === 0) {
      setContracts([
        { id: 1, filename: "NDA_BankOfAmerica_TechCorp.pdf", status: "completed", uploaded_at: "2026-05-01T10:00:00Z" },
        { id: 2, filename: "MasterServiceAgreement_Vendor.pdf", status: "processing", uploaded_at: "2026-05-02T09:30:00Z" }
      ]);
    }
  }, []);

  const handleUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    setUploading(true);
    // Simulate API call
    setTimeout(() => {
      const newContract = {
        id: Date.now(),
        filename: file.name,
        status: "completed",
        uploaded_at: new Date().toISOString()
      };
      setContracts([newContract, ...contracts]);
      setUploading(false);
    }, 2000);
  };

  if (activeContract) {
    return <ContractViewer contract={activeContract} onBack={() => setActiveContract(null)} />;
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-light text-white">Contract Intelligence</h2>
          <p className="text-slate-400 mt-1">Upload and analyze multi-modal banking contracts</p>
        </div>
        
        <label className="cursor-pointer relative group">
          <input type="file" className="hidden" accept=".pdf" onChange={handleUpload} disabled={uploading} />
          <div className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg flex items-center gap-2 transition-all shadow-lg shadow-indigo-500/25">
            <Upload className="w-5 h-5" />
            <span className="font-medium">{uploading ? 'Analyzing...' : 'Upload Contract'}</span>
          </div>
        </label>
      </div>

      <div className="bg-slate-900/80 backdrop-blur border border-white/5 rounded-xl overflow-hidden shadow-2xl">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/5 bg-slate-800/50">
              <th className="p-4 text-sm font-semibold text-slate-300">Document Name</th>
              <th className="p-4 text-sm font-semibold text-slate-300">Upload Date</th>
              <th className="p-4 text-sm font-semibold text-slate-300">Status</th>
              <th className="p-4 text-sm font-semibold text-slate-300">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {contracts.map(contract => (
              <tr key={contract.id} className="hover:bg-white/5 transition-colors group">
                <td className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-slate-800 rounded-lg">
                    <File className="w-5 h-5 text-indigo-400" />
                  </div>
                  <span className="text-slate-200 font-medium">{contract.filename}</span>
                </td>
                <td className="p-4 text-slate-400 text-sm">
                  {new Date(contract.uploaded_at).toLocaleDateString()}
                </td>
                <td className="p-4">
                  {contract.status === 'completed' ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-medium border border-emerald-500/20">
                      <CheckCircle className="w-3.5 h-3.5" /> Reviewed
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 text-xs font-medium border border-amber-500/20">
                      <Clock className="w-3.5 h-3.5 animate-pulse" /> Processing LayoutLMv3
                    </span>
                  )}
                </td>
                <td className="p-4">
                  <button 
                    onClick={() => setActiveContract(contract)}
                    disabled={contract.status !== 'completed'}
                    className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                      contract.status === 'completed' 
                        ? 'bg-slate-800 text-white hover:bg-slate-700' 
                        : 'bg-slate-800/50 text-slate-500 cursor-not-allowed'
                    }`}
                  >
                    View Analysis
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
