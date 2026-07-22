import React, { useState, useRef, useEffect } from 'react';
import { Upload, CheckCircle2 } from 'lucide-react';

interface IngestionPanelProps {
  onIngestSuccess: (data: any, key: string) => void;
  activePatientData?: any;
}

export const IngestionPanel: React.FC<IngestionPanelProps> = ({ onIngestSuccess, activePatientData }) => {
  const [memberId, setMemberId] = useState('');
  const [providerId, setProviderId] = useState('');
  const [cptCode, setCptCode] = useState('');
  const [icdCode, setIcdCode] = useState('');

  // Prefill fields when active patient data updates
  useEffect(() => {
    if (activePatientData) {
      setMemberId(activePatientData.member_id || '');
      setProviderId(activePatientData.provider_id || '');
      setCptCode(activePatientData.cpt_code || '');
      setIcdCode(activePatientData.icd_code || '');
    } else {
      setMemberId('');
      setProviderId('');
      setCptCode('');
      setIcdCode('');
      setFiles([]);
      setErrorMsg('');
      setUploadProgress(0);
    }
  }, [activePatientData]);

  
  const [files, setFiles] = useState<File[]>([]);
  const [isDragActive, setIsDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [loadingPipeline, setLoadingPipeline] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      simulateUpload(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      simulateUpload(Array.from(e.target.files));
    }
  };

  const simulateUpload = (selectedFiles: File[]) => {
    setFiles((prev) => [...prev, ...selectedFiles]);
    setIsUploading(true);
    setUploadProgress(0);
    setErrorMsg('');

    // Simulate progress bar increase
    const interval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsUploading(false);
          return 100;
        }
        return prev + 10;
      });
    }, 100);
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleRunPipeline = async () => {
    if (files.length === 0 && !cptCode) {
      setErrorMsg('Please upload a document or at least provide a CPT Code to analyze.');
      return;
    }

    setLoadingPipeline(true);
    setErrorMsg('');
    
    const formData = new FormData();
    formData.append('member_id', memberId);
    formData.append('provider_id', providerId);
    formData.append('cpt_code', cptCode);
    formData.append('icd_code', icdCode);
    files.forEach((f) => {
      formData.append('files', f);
    });

    try {
      const response = await fetch('/api/cases/ingest', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Pipeline execution failed.');
      }

      const result = await response.json();
      onIngestSuccess(result.data, result.key);
    } catch (err: any) {
      setErrorMsg(err.message || 'An error occurred during analysis.');
    } finally {
      setLoadingPipeline(false);
    }
  };

  return (
    <div className="relative transition-all duration-300">
      <div className="dashboard-card p-6 space-y-6">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-xs">
            1
          </div>
          <h2 className="text-lg font-bold text-slate-100">Document Ingestion</h2>
        </div>

        {/* Drag and Drop Zone */}
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={triggerFileSelect}
          className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200 ${
            isDragActive 
              ? 'border-indigo-400 bg-indigo-500/5' 
              : files.length > 0
                ? 'border-emerald-500/50 bg-emerald-500/5' 
                : 'border-slate-700 hover:border-indigo-500/50 hover:bg-slate-800/10'
          }`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
            accept=".pdf,.txt,.json"
            multiple
          />
          
          <div className="flex flex-col items-center justify-center space-y-2">
            <Upload className="w-10 h-10 text-slate-500" />
            <div className="text-sm font-semibold text-slate-300">Drag & drop provider submission files</div>
            <div className="text-xs text-slate-500">Supports multiple PDF, TXT or JSON payload</div>
          </div>
        </div>

        {/* Selected Files List */}
        {files.length > 0 && (
          <div className="space-y-2">
            {files.map((f, idx) => (
              <div key={idx} className="flex items-center gap-3 bg-slate-900/50 border border-emerald-500/20 p-2 rounded-lg">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <div className="flex-1 text-sm font-semibold text-slate-200">{f.name}</div>
                <div className="text-xs text-slate-400">{(f.size / 1024).toFixed(1)} KB</div>
                <button 
                  onClick={(e) => { 
                    e.stopPropagation(); 
                    const url = URL.createObjectURL(f);
                    window.open(url, '_blank');
                  }}
                  className="text-xs text-indigo-400 hover:text-indigo-300 ml-2 cursor-pointer"
                >
                  Preview
                </button>
                <button 
                  onClick={(e) => { e.stopPropagation(); setFiles(files.filter((_, i) => i !== idx)); }}
                  className="text-xs text-rose-400 hover:text-rose-300 ml-2 cursor-pointer"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Upload Progress Bar */}
        {isUploading && (
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-semibold text-indigo-400">
              <span>Ingesting document...</span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
              <div 
                className="bg-indigo-500 h-1.5 rounded-full transition-all duration-200" 
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Manual Override Fields */}
        <div className="space-y-4 pt-2 border-t border-slate-800/50">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Demographic Manual Overrides
          </h3>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Member ID</label>
              <input
                type="text"
                placeholder="e.g. M88231"
                value={memberId}
                onChange={(e) => setMemberId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/60 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Billing NPI</label>
              <input
                type="text"
                placeholder="e.g. P-9004"
                value={providerId}
                onChange={(e) => setProviderId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/60 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">CPT Code</label>
              <input
                type="text"
                placeholder="e.g. 72148"
                value={cptCode}
                onChange={(e) => setCptCode(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/60 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">ICD-10 Code</label>
              <input
                type="text"
                placeholder="e.g. M54.5"
                value={icdCode}
                onChange={(e) => setIcdCode(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/60 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-400 text-xs font-medium">
            {errorMsg}
          </div>
        )}

        {/* Run Pipeline Button */}
        <button
          onClick={handleRunPipeline}
          disabled={loadingPipeline}
          className="w-full bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 disabled:opacity-50 text-white font-semibold py-2.5 px-4 rounded-xl shadow-lg shadow-indigo-500/10 transition-all duration-200 flex items-center justify-center gap-2 mt-2"
        >
          {loadingPipeline ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Analyzing Provider Case...</span>
            </>
          ) : (
            <span>🚀 Run Agentic Analysis Pipeline</span>
          )}
        </button>
      </div>
    </div>
  );
};
