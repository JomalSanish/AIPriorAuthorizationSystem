import React from 'react';

interface SplitViewProps {
  clinicalNotes: string;
  selectedCriterion: {
    criterion: string;
    status: string;
    rationale: string;
    citation: string;
  } | null;
  evidence: Array<{
    prerequisite: string;
    text: string;
    citation: string;
    score: number;
  }>;
}

export const SplitView: React.FC<SplitViewProps> = ({ clinicalNotes, selectedCriterion, evidence }) => {
  if (!selectedCriterion) {
    return (
      <div className="h-64 border border-slate-800 rounded-xl bg-slate-900/20 flex items-center justify-center text-slate-500 text-sm">
        Click on any checklist item to inspect note passages & guidelines side-by-side
      </div>
    );
  }

  // Find the evidence passage text for the selected criterion
  const matchedEvidence = evidence.find(
    (ev) => ev.prerequisite.toLowerCase() === selectedCriterion.criterion.toLowerCase()
  ) || evidence.find(
    (ev) => ev.prerequisite.toLowerCase().includes(selectedCriterion.criterion.toLowerCase()) ||
            selectedCriterion.criterion.toLowerCase().includes(ev.prerequisite.toLowerCase())
  );

  const rawCriteriaText = selectedCriterion.criterion;
  const passageToHighlight = matchedEvidence ? matchedEvidence.text : '';

  // Function to render notes with highlighted passage
  const renderHighlightedNotes = () => {
    if (!clinicalNotes) return <span className="text-slate-500">No clinical notes available.</span>;
    if (!passageToHighlight) {
      return (
        <div className="space-y-3">
          <p className="text-slate-300 whitespace-pre-wrap">{clinicalNotes}</p>
          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400 text-xs">
            ⚠️ No matching passage found in clinical notes for this criteria.
          </div>
        </div>
      );
    }

    // Try finding direct match
    const index = clinicalNotes.toLowerCase().indexOf(passageToHighlight.toLowerCase());
    if (index === -1) {
      // Direct substring match failed (due to formatting or edits)
      return (
        <div className="space-y-3">
          <p className="text-slate-300 whitespace-pre-wrap">{clinicalNotes}</p>
          <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-lg space-y-1">
            <div className="text-xs font-semibold text-indigo-400">Isolated Evidence Passage:</div>
            <p className="text-xs text-slate-200 italic font-medium">"{passageToHighlight}"</p>
          </div>
        </div>
      );
    }

    const before = clinicalNotes.substring(0, index);
    const match = clinicalNotes.substring(index, index + passageToHighlight.length);
    const after = clinicalNotes.substring(index + passageToHighlight.length);

    return (
      <p className="text-slate-300 whitespace-pre-wrap">
        {before}
        <span className="highlight-yellow">{match}</span>
        {after}
      </p>
    );
  };

  return (
    <div className="grid grid-cols-2 gap-4 border border-slate-800 rounded-xl overflow-hidden bg-slate-950/40 min-h-[300px]">
      {/* Left Panel: Clinical Notes highlight */}
      <div className="p-4 border-r border-slate-800 flex flex-col h-[400px]">
        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 pb-1.5 border-b border-slate-800">
          📄 Submitted Note Verification
        </div>
        <div className="overflow-y-auto flex-1 text-sm leading-relaxed pr-1">
          {renderHighlightedNotes()}
        </div>
      </div>

      {/* Right Panel: Policy requirement criteria */}
      <div className="p-4 flex flex-col h-[400px] bg-slate-900/10">
        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 pb-1.5 border-b border-slate-800">
          📜 Guideline Criteria Context
        </div>
        <div className="overflow-y-auto flex-1 text-sm space-y-4 pr-1">
          <div className="space-y-1">
            <div className="text-xs font-semibold text-slate-500">Requirement Target:</div>
            <p className="text-slate-200 font-medium leading-relaxed bg-slate-900/40 p-3 rounded-lg border border-slate-800/80">
              {rawCriteriaText}
            </p>
          </div>
          
          <div className="space-y-1">
            <div className="text-xs font-semibold text-slate-500">LLM Audit Analysis:</div>
            <p className="text-slate-300 text-xs leading-relaxed bg-indigo-950/10 border border-indigo-900/30 p-3 rounded-lg">
              {selectedCriterion.rationale}
            </p>
          </div>

          <div className="flex justify-between items-center text-xs text-slate-500 pt-2">
            <span>Citation: <strong className="text-indigo-400">{selectedCriterion.citation || 'Mock Policy Guide'}</strong></span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${
              selectedCriterion.status === 'PRESENT' 
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
                : selectedCriterion.status === 'ABSENT'
                  ? 'bg-rose-500/10 text-rose-400 border-rose-500/25'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/25'
            }`}>
              {selectedCriterion.status}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
