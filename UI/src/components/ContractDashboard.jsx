import React, { useState, useEffect } from 'react';
import { Upload, File, AlertTriangle, CheckCircle, Clock, Trash2, RefreshCw } from 'lucide-react';
import { useStore } from '../store/useStore';
import ContractViewer from './ContractViewer';
import api from '../api';

export default function ContractDashboard() {
  const { contracts, setContracts, activeContract, setActiveContract } = useStore();
  const [uploading, setUploading] = useState(false);

  // Fetch real contracts from backend, with polling for processing contracts
  const fetchContracts = async () => {
    try {
      const response = await api.get('/contracts/');
      setContracts(response.data);
    } catch (error) {
      console.error('Error fetching contracts:', error);
    }
  };

  useEffect(() => {
    fetchContracts();
  }, []);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await api.post('/contracts/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      // Immediately add the 'processing' contract to UI
      setContracts([response.data, ...contracts]);
    } catch (error) {
      console.error('Error uploading contract:', error);
      alert('Failed to upload contract. Please try again.');
    } finally {
      // Free the UI instantly for more uploads
      setUploading(false);
      // Reset the file input
      e.target.value = null;
    }
  };

  const handleDelete = async (contractId) => {
    if (!window.confirm("Are you sure you want to permanently delete this contract?")) return;
    
    try {
      await api.delete(`/contracts/${contractId}`);
      setContracts(contracts.filter(c => c.id !== contractId));
    } catch (error) {
      console.error('Error deleting contract:', error);
      alert('Failed to delete contract.');
    }
  };

  const calculateDuration = (start, end) => {
    if (!end) return '-';
    const startDate = new Date(start.endsWith('Z') ? start : start + 'Z');
    const endDate = new Date(end.endsWith('Z') ? end : end + 'Z');
    const diff = Math.floor((endDate - startDate) / 1000);
    if (diff < 60) return `${diff}s`;
    return `${Math.floor(diff / 60)}m ${diff % 60}s`;
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
        <div className="flex items-center gap-4">
          <button 
            onClick={fetchContracts}
            className="px-4 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-lg flex items-center gap-2 transition-all border border-white/10"
            title="Refresh grid"
          >
            <RefreshCw className="w-5 h-5" />
            <span className="font-medium hidden sm:inline">Refresh</span>
          </button>
          <label className="cursor-pointer relative group">
            <input type="file" className="hidden" accept=".pdf" onChange={handleUpload} disabled={uploading} />
            <div className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg flex items-center gap-2 transition-all shadow-lg shadow-indigo-500/25">
              <Upload className="w-5 h-5" />
              <span className="font-medium">{uploading ? 'Uploading...' : 'Upload Contract'}</span>
            </div>
          </label>
        </div>
      </div>

      <div className="bg-slate-900/80 backdrop-blur border border-white/5 rounded-xl overflow-hidden shadow-2xl">
        <table className="w-full text-left border-collapse table-fixed">
          <thead>
            <tr className="border-b border-white/5 bg-slate-800/50">
              <th className="p-4 text-sm font-semibold text-slate-300 w-full">Document Name</th>
              <th className="p-4 text-sm font-semibold text-slate-300 w-40">Upload Date</th>
              <th className="p-4 text-sm font-semibold text-slate-300 w-32">Review Time</th>
              <th className="p-4 text-sm font-semibold text-slate-300 w-48">Status</th>
              <th className="p-4 text-sm font-semibold text-slate-300 w-40">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {contracts.map(contract => (
              <tr key={contract.id} className="hover:bg-white/5 transition-colors group">
                <td className="p-4 flex items-center gap-3 overflow-hidden">
                  <div className="p-2 bg-slate-800 rounded-lg shrink-0">
                    <File className="w-5 h-5 text-indigo-400" />
                  </div>
                  <span className="text-slate-200 font-medium break-all">{contract.filename}</span>
                </td>
                <td className="p-4 text-slate-400 text-sm">
                  {(() => {
                    const date = new Date(contract.uploaded_at.endsWith('Z') ? contract.uploaded_at : contract.uploaded_at + 'Z');
                    return (
                      <>
                        <div>{date.toLocaleDateString()}</div>
                        <div className="text-xs text-slate-500 mt-0.5">{date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
                      </>
                    );
                  })()}
                </td>
                <td className="p-4 text-slate-400 text-sm font-mono">
                  {calculateDuration(contract.uploaded_at, contract.completed_at)}
                </td>
                <td className="p-4">
                  {contract.status === 'completed' ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-medium border border-emerald-500/20">
                      <CheckCircle className="w-3.5 h-3.5" /> Reviewed
                    </span>
                  ) : contract.status === 'failed' ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-500/10 text-red-400 text-xs font-medium border border-red-500/20">
                      <AlertTriangle className="w-3.5 h-3.5" /> Failed
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 text-xs font-medium border border-amber-500/20">
                      <Clock className="w-3.5 h-3.5 animate-pulse" /> Review in progress
                    </span>
                  )}
                </td>
                <td className="p-4">
                  <div className="flex items-center gap-2">
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
                    <button 
                      onClick={() => handleDelete(contract.id)}
                      className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                      title="Delete Contract"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
