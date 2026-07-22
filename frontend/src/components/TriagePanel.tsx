import React, { useState, useEffect } from 'react';
import { Send, FileCheck2, AlertCircle, CheckCircle2, FileX, AlertTriangle } from 'lucide-react';

interface ChecklistItem {
  criterion: string;
  status: string;
  rationale: string;
  citation: string;
}

interface TriagePanelProps {
  caseKey: string;
  summary: string;
  communicationDraft: string;
  checklistItems: ChecklistItem[];
  onTriageComplete: (updatedCase: any) => void;
  onBackToVerification: () => void;
}

export const TriagePanel: React.FC<TriagePanelProps> = ({
  caseKey,
  summary,
  communicationDraft,
  checklistItems,
  onTriageComplete,
  onBackToVerification
}) => {
  const [draftText, setDraftText] = useState(communicationDraft);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' | 'warning' } | null>(null);

  // Auto-append missing checklist criteria to the correspondence draft
  useEffect(() => {
    let initialText = communicationDraft || '';
    
    // Find all ABSENT or UNCLEAR items
    const missingGaps = checklistItems
      .filter(item => item.status === 'ABSENT' || item.status === 'UNCLEAR')
      .map(item => `- Missing verification for: "${item.criterion}"`);

    if (missingGaps.length > 0) {
      const gapSection = `\n\nREQUIRED EVIDENCE GAPS DETECTED:\n${missingGaps.join('\n')}\n\nPlease submit the missing documentation listed above to complete prior authorization review.`;
      
      // Append only if it doesn't already contain the GAPS string
      if (!initialText.includes('REQUIRED EVIDENCE GAPS DETECTED')) {
        initialText += gapSection;
      }
    }
    
    setDraftText(initialText);
  }, [communicationDraft, checklistItems]);

  const handleTriageAction = async (route: string, status: string) => {
    setLoading(true);
    setMsg(null);

    try {
      const response = await fetch('/api/cases/triage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_key: caseKey,
          route: route,
          status: status,
          communication_draft: draftText
        })
      });

      if (!response.ok) {
        throw new Error('Failed to record triage decision.');
      }

      const result = await response.json();
      onTriageComplete(result.data);
      
      if (status === 'APPROVED') {
        setMsg({ text: `Successfully routed case to ${route}. Status set to Pending Review.`, type: 'success' });
      } else if (status === 'REQUEST MORE INFO') {
        setMsg({ text: `Correspondence saved. Case queued in Information Request.`, type: 'warning' });
      } else {
        setMsg({ text: `Case escalated to Medical Director.`, type: 'error' });
      }
    } catch (err: any) {
      setMsg({ text: err.message || 'An error occurred during routing.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // Simple Markdown to HTML parser for summary brief
  const parseMarkdown = (mdText: string) => {
    if (!mdText) return <p className="text-slate-400 italic">No summary generated yet.</p>;
    
    const lines = mdText.split('\n');
    return lines.map((line, idx) => {
      if (line.startsWith('### ')) {
        return <h4 key={idx} className="text-sm font-bold text-indigo-400 mt-4 mb-2 uppercase tracking-wide">{line.replace('### ', '')}</h4>;
      }
      if (line.startsWith('- **')) {
        const parts = line.replace('- **', '').split('**');
        return (
          <div key={idx} className="text-xs text-slate-300 ml-4 mb-1">
            • <strong className="text-slate-100">{parts[0]}</strong>{parts[1] || ''}
          </div>
        );
      }
      if (line.startsWith('- ')) {
        return <div key={idx} className="text-xs text-slate-300 ml-4 mb-1">• {line.replace('- ', '')}</div>;
      }
      return <p key={idx} className="text-xs text-slate-300 mb-1 leading-relaxed">{line}</p>;
    });
  };

  return (
    <div className="transition-all duration-300">
      <div className="dashboard-card p-6 space-y-6">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-xs">
            3
          </div>
          <h2 className="text-lg font-bold text-slate-100">Triage & Summary Actions</h2>
        </div>

        {/* Narrative and Draft Stacked Vertically to prevent squishing */}
        <div className="space-y-6">
          {/* Summary Brief */}
          <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-4 flex flex-col h-[220px]">
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 pb-1.5 border-b border-slate-800/80 flex items-center gap-1.5">
              <FileCheck2 className="w-4 h-4 text-indigo-400" />
              Clinical Summary Brief
            </div>
            <div className="overflow-y-auto flex-1 pr-1 text-slate-300 space-y-2">
              {parseMarkdown(summary)}
            </div>
          </div>

          {/* Missing Checklist Items */}
          {checklistItems.filter(item => item.status === 'ABSENT' || item.status === 'UNCLEAR').length > 0 && (
            <div className="bg-rose-950/20 border border-rose-900/50 rounded-xl p-4">
              <div className="text-xs font-bold text-rose-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />
                Missing Required Evidence
              </div>
              <ul className="space-y-2">
                {checklistItems
                  .filter(item => item.status === 'ABSENT' || item.status === 'UNCLEAR')
                  .map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-rose-300/90 bg-rose-950/30 p-2 rounded border border-rose-900/30">
                      <div className="mt-0.5"><AlertCircle className="w-3.5 h-3.5 text-rose-500" /></div>
                      <div>
                        <span className="font-semibold text-rose-200">{item.criterion}</span>
                        <div className="text-rose-400/80 mt-1 italic text-[10px]">{item.rationale}</div>
                      </div>
                    </li>
                  ))}
              </ul>
            </div>
          )}

          {/* Letter Draft */}
          <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-4 flex flex-col h-[280px]">
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 pb-1.5 border-b border-slate-800/80 flex items-center gap-1.5">
              <Send className="w-4 h-4 text-indigo-400" />
              Provider Outreach Letter Draft
            </div>
            <textarea
              value={draftText}
              onChange={(e) => setDraftText(e.target.value)}
              className="flex-1 w-full bg-slate-900/60 border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-200 leading-relaxed focus:outline-none focus:border-indigo-500 resize-none overflow-y-auto"
              placeholder="Edit the neutral outreach letter here..."
            />
          </div>
        </div>

        {/* Status Notification */}
        {msg && (
          <div className={`p-3 rounded-lg text-xs font-semibold flex items-center gap-2 ${
            msg.type === 'success' 
              ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
              : msg.type === 'warning'
                ? 'bg-amber-500/10 border border-amber-500/30 text-amber-400'
                : 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
          }`}>
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{msg.text}</span>
          </div>
        )}

        {/* Triage Action Buttons - Stacked for better presentation */}
        <div className="space-y-3 pt-2 border-t border-slate-800/50">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Operational Routing Decision
          </h3>
          
          <div className="flex flex-col gap-3">
            {/* Route to Nurse */}
            <button
              onClick={() => handleTriageAction('Nurse Review', 'PENDING')}
              disabled={loading}
              className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-semibold py-3 px-4 rounded-xl text-xs shadow-lg shadow-emerald-600/10 transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Route to Nurse Review Queue</span>
            </button>

            {/* Request Info / Reject */}
            <button
              onClick={() => handleTriageAction('Information Request', 'REQUEST MORE INFO')}
              disabled={loading}
              className="bg-slate-950 border border-rose-500/50 hover:bg-rose-500/5 disabled:opacity-50 text-rose-400 font-semibold py-3 px-4 rounded-xl text-xs transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer"
            >
              <FileX className="w-4 h-4" />
              <span>Request More Info / Reject Case</span>
            </button>

            {/* Escalate to Medical Director */}
            <button
              onClick={() => handleTriageAction('Medical Director', 'PENDING')}
              disabled={loading}
              className="bg-amber-500 hover:bg-amber-655 disabled:opacity-50 text-slate-955 font-bold py-3 px-4 rounded-xl text-xs shadow-lg shadow-amber-500/10 transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer"
            >
              <AlertTriangle className="w-4 h-4" />
              <span>Escalate to Medical Director</span>
            </button>
          </div>
        </div>

        {/* Navigation back */}
        <div className="flex pt-2">
          <button
            onClick={onBackToVerification}
            className="flex-1 bg-slate-900 border border-slate-700/60 hover:bg-slate-800 text-slate-300 font-semibold py-2.5 px-4 rounded-xl text-xs transition-all duration-200 cursor-pointer"
          >
            ⬅️ Back to Policy Checklists
          </button>
        </div>
      </div>
    </div>
  );
};

