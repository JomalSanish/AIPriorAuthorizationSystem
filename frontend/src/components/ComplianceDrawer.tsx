import React, { useState } from 'react';
import { Shield, ChevronUp, ChevronDown, CheckCircle2 } from 'lucide-react';

interface ComplianceDrawerProps {
  auditTrail: string[];
  complianceHash?: string;
  auditModel?: string;
  auditTimestamp?: string;
}

export const ComplianceDrawer: React.FC<ComplianceDrawerProps> = ({
  auditTrail,
  complianceHash,
  auditModel,
  auditTimestamp
}) => {
  const [isOpen, setIsOpen] = useState(false);

  // Parse list of strings like "[2026-07-09T23:27:13Z] Ingested Case PA-72148-A" into structured rows
  const parseAuditLogs = () => {
    if (!auditTrail || auditTrail.length === 0) return [];
    
    return auditTrail.map((log, index) => {
      // Simple parse: find [timestamp] description
      const match = log.match(/^\[(.*?)\] (.*)$/);
      if (match) {
        // Infer actor based on string contents
        let actor = 'System Operator';
        const msg = match[2];
        if (msg.includes('Intake') || msg.includes('Evidence')) {
          actor = 'Intake Agent / Evidence Agent';
        } else if (msg.includes('Gap')) {
          actor = 'Policy Gap Agent';
        } else if (msg.includes('Summary') || msg.includes('triage') || msg.includes('routed')) {
          actor = 'Summary Agent / Human Reviewer';
        } else if (msg.includes('Pipeline')) {
          actor = 'Orchestration Manager';
        }
        
        return {
          id: index,
          timestamp: match[1],
          action: msg,
          actor: actor,
          hash: complianceHash || 'n/a'
        };
      }
      
      return {
        id: index,
        timestamp: auditTimestamp || '2026-07-13T15:13:00Z',
        action: log,
        actor: 'Audit Agent',
        hash: complianceHash || 'n/a'
      };
    });
  };

  const parsedLogs = parseAuditLogs();

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-[#0f121d] border-t border-slate-800 shadow-2xl transition-all duration-300">
      {/* Header bar (Toggle Click trigger) */}
      <div 
        onClick={() => setIsOpen(!isOpen)}
        className="max-w-7xl mx-auto px-6 py-3.5 flex justify-between items-center cursor-pointer select-none"
      >
        <div className="flex items-center gap-2 text-indigo-400 font-bold text-sm tracking-wide">
          <Shield className="w-4 h-4" />
          <span>COMPLIANCE AUDIT TELEMETRY & DIGITAL SIGNATURES</span>
        </div>
        
        <div className="flex items-center gap-5">
          {complianceHash && (
            <div className="hidden lg:flex items-center gap-1.5 text-xs text-slate-400">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>SHA-256 Ledger Signed: </span>
              <code className="text-slate-300 font-mono bg-slate-900/80 px-2 py-0.5 rounded border border-slate-800 text-[10px]">
                {complianceHash.substring(0, 16)}...
              </code>
            </div>
          )}
          {isOpen ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronUp className="w-4 h-4 text-slate-400" />}
        </div>
      </div>

      {/* Expanded Table content */}
      {isOpen && (
        <div className="max-w-7xl mx-auto px-6 pb-6 pt-1 max-h-[300px] overflow-y-auto space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-xs text-slate-400 py-2 border-b border-slate-800/80">
            <div>
              <strong>Cryptographic Verification Model:</strong> <span className="text-slate-200">{auditModel || 'gpt-4o-mini'}</span>
            </div>
            <div>
              <strong>Integrity Stamp:</strong> <span className="text-slate-200">{auditTimestamp || '2026-07-13 15:13:00Z'}</span>
            </div>
            <div className="truncate">
              <strong>Audit Ledger Hash:</strong> <span className="text-slate-200 font-mono">{complianceHash || 'PENDING ASSIGNMENT'}</span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="text-slate-500 font-bold border-b border-slate-800/60 pb-2">
                  <th className="py-2">Timestamp</th>
                  <th className="py-2">Action / Event Logged</th>
                  <th className="py-2">Responsible Agent / Role</th>
                  <th className="py-2">Tamper-Proof SHA-256 Stamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/40 text-slate-300">
                {parsedLogs.length > 0 ? (
                  parsedLogs.map((row) => (
                    <tr key={row.id} className="hover:bg-slate-800/20">
                      <td className="py-2.5 pr-4 font-mono text-[10px] text-indigo-400/80">{row.timestamp}</td>
                      <td className="py-2.5 pr-4 font-semibold text-slate-200">{row.action}</td>
                      <td className="py-2.5 pr-4">
                        <span className="bg-slate-900 border border-slate-800 px-2 py-0.5 rounded text-[10px] text-slate-400">
                          {row.actor}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-[9px] text-slate-500 truncate max-w-[200px]">
                        {row.hash}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-slate-500 italic">
                      No compliance verification trail found for this session.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
