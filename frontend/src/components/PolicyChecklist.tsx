import { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, FileText, Shield } from 'lucide-react';
import { SplitView } from './SplitView';

interface ChecklistItem {
  criterion: string;
  status: string;
  rationale: string;
  citation: string;
}

interface PolicyChecklistProps {
  checklistItems: ChecklistItem[];
  overallStatus: string;
  clinicalNotes: string;
  evidence: any[];
  onProceedToTriage: () => void;
  onBackToUpload: () => void;
  requiredDocs: string[];
}

export const PolicyChecklist: React.FC<PolicyChecklistProps> = ({
  checklistItems,
  overallStatus,
  clinicalNotes,
  evidence,
  onProceedToTriage,
  onBackToUpload,
  requiredDocs
}) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [verifiedDocs, setVerifiedDocs] = useState<Set<string>>(new Set());

  // Auto-verify required documents from active case clinical note text, evidence citations & gap checklist status
  useEffect(() => {
    const verified = new Set<string>();
    const uploadedDocs = evidence.map(ev => ev.citation?.toLowerCase() || '');
    const noteText = clinicalNotes ? clinicalNotes.toLowerCase() : '';

    requiredDocs.forEach(reqDoc => {
      // Check if it's marked PRESENT in the gap checklist items
      const isPresentInChecklist = checklistItems.some(
        item => item.criterion.toLowerCase() === reqDoc.toLowerCase() && 
                item.status.toUpperCase() === 'PRESENT'
      );

      // Look for document type hints in citations or notes (e.g. "radiology", "therapy logs")
      const isDocPresent = isPresentInChecklist ||
                           uploadedDocs.some(uploaded => uploaded.includes(reqDoc.toLowerCase())) ||
                           noteText.includes(reqDoc.toLowerCase()) ||
                           (reqDoc.toLowerCase().includes('radiology') && noteText.includes('mri')) ||
                           (reqDoc.toLowerCase().includes('physical therapy') && noteText.includes('physical therapy'));

      if (isDocPresent) {
        verified.add(reqDoc);
      }
    });

    setVerifiedDocs(verified);
  }, [requiredDocs, evidence, clinicalNotes, checklistItems]);


  const toggleDocVerified = (doc: string) => {
    const updated = new Set(verifiedDocs);
    if (updated.has(doc)) {
      updated.delete(doc);
    } else {
      updated.add(doc);
    }
    setVerifiedDocs(updated);
  };

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'PRESENT':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            🟢 PRESENT
          </span>
        );
      case 'ABSENT':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
            🔴 ABSENT
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            🟡 UNCLEAR
          </span>
        );
    }
  };

  const handleAccordionToggle = (index: number) => {
    if (expandedIndex === index) {
      setExpandedIndex(null);
    } else {
      setExpandedIndex(index);
    }
  };

  const selectedCriterion = expandedIndex !== null ? checklistItems[expandedIndex] : null;

  return (
    <div className="transition-all duration-300 space-y-6">
      {/* Policy Card Header */}
      <div className="dashboard-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-xs">
              2
            </div>
            <h2 className="text-lg font-bold text-slate-100">RAG Verification & Gaps</h2>
          </div>
          <div className="text-sm font-semibold">
            Status: <span className="text-indigo-400">{overallStatus || 'PENDING'}</span>
          </div>
        </div>

        {/* Accordions */}
        <div className="space-y-3">
          {checklistItems && checklistItems.length > 0 ? (
            checklistItems.map((item, index) => {
              const isExpanded = expandedIndex === index;
              return (
                <div 
                  key={index}
                  className={`border rounded-xl transition-all duration-200 ${
                    isExpanded 
                      ? 'border-indigo-500/50 bg-slate-900/40' 
                      : item.status === 'ABSENT' 
                        ? 'border-rose-500/20 hover:border-rose-500/40 bg-slate-900/10' 
                        : 'border-slate-800 hover:border-slate-700 bg-slate-900/10'
                  }`}
                >
                  {/* Title Bar */}
                  <div 
                    onClick={() => handleAccordionToggle(index)}
                    className="flex justify-between items-center p-4 cursor-pointer select-none"
                  >
                    <span className="text-sm font-semibold text-slate-200 flex-1 pr-4">
                      {item.criterion}
                    </span>
                    <div className="flex items-center gap-3">
                      {getStatusBadge(item.status)}
                      {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    </div>
                  </div>

                  {/* Collapsible Panel */}
                  {isExpanded && (
                    <div className="p-4 border-t border-slate-800/80 bg-slate-950/20 space-y-3">
                      <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Step-by-Step Reasoning
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed font-mono">
                        {item.rationale}
                      </p>
                      {item.citation && (
                        <div className="text-[10px] text-slate-500 flex items-center gap-1">
                          <FileText className="w-3 h-3 text-slate-600" />
                          Source Document: <strong className="text-slate-400">{item.citation}</strong>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="text-center py-6 text-slate-500 text-sm">
              No policy guidelines checklist available. Run the analysis first.
            </div>
          )}
        </div>
      </div>

      {/* Required Documentation Status Card */}
      {requiredDocs && requiredDocs.length > 0 && (
        <div className="dashboard-card p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-indigo-400 animate-pulse" />
            <h2 className="text-sm font-bold text-slate-200 tracking-wide uppercase">
              Required Documentation Checklist
            </h2>
          </div>
          <div className="divide-y divide-slate-800/40">
            {requiredDocs.map((doc, idx) => {
              const isVerified = verifiedDocs.has(doc);
              return (
                <div key={idx} className="flex items-center justify-between py-3">
                  <label className="flex items-center gap-3 cursor-pointer text-xs font-semibold text-slate-300 hover:text-slate-100 select-none">
                    <input
                      type="checkbox"
                      checked={isVerified}
                      onChange={() => toggleDocVerified(doc)}
                      className="w-4 h-4 rounded border-slate-700 bg-slate-950 text-indigo-500 focus:ring-0 focus:ring-offset-0 focus:outline-none"
                    />
                    <span className={isVerified ? 'text-slate-300 line-through' : 'text-slate-200'}>
                      {doc}
                    </span>
                  </label>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                    isVerified
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/25'
                      : 'bg-rose-500/10 text-rose-400 border border-rose-500/25'
                  }`}>
                    {isVerified ? 'VERIFIED' : 'MISSING'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}


      {/* Navigation Buttons */}
      <div className="flex justify-between gap-4 pt-2">
        <button
          onClick={onBackToUpload}
          className="flex-1 bg-slate-900 border border-slate-700/60 hover:bg-slate-800 text-slate-300 font-semibold py-2 px-4 rounded-xl transition-all duration-200"
        >
          ⬅️ Back to Ingestion
        </button>
        <button
          onClick={onProceedToTriage}
          className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-xl shadow-lg shadow-indigo-600/10 transition-all duration-200"
        >
          Proceed to Route ➡️
        </button>
      </div>
    </div>
  );
};
