import React from 'react';

interface DemographicsCardProps {
  patientData: {
    member_id?: string;
    provider_id?: string;
    cpt_code?: string;
    icd_code?: string;
    first_name?: string;
    last_name?: string;
    dob?: string;
    [key: string]: any;
  };
  classification?: {
    type?: string;
    urgency?: string;
    reason?: string;
  };
}

export const DemographicsCard: React.FC<DemographicsCardProps> = ({ patientData, classification }) => {
  // Safe helper to extract details
  const memberId = patientData.member_id || 'N/A';
  const providerId = patientData.provider_id || 'N/A';
  const cptCode = patientData.cpt_code || 'N/A';
  const icdCode = patientData.icd_code || 'N/A';
  const firstName = patientData.first_name || 'Unknown';
  const lastName = patientData.last_name || 'Unknown';
  const dob = patientData.dob || 'N/A';

  const serviceType = classification?.type || 'N/A';
  const urgency = classification?.urgency || 'ROUTINE';

  // Badges color coding
  const getServiceBadgeColor = (type: string) => {
    switch (type.toUpperCase()) {
      case 'IMAGING':
        return 'bg-sky-500/15 text-sky-400 border-sky-500/30';
      case 'DRUG':
        return 'bg-purple-500/15 text-purple-400 border-purple-500/30';
      case 'SURGERY':
        return 'bg-rose-500/15 text-rose-400 border-rose-500/30';
      default:
        return 'bg-slate-500/15 text-slate-400 border-slate-500/30';
    }
  };

  return (
    <div className="dashboard-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold tracking-wider text-slate-400 uppercase">
          Active Case Context
        </h3>
        <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getServiceBadgeColor(serviceType)}`}>
          {serviceType}
        </span>
      </div>

      <div className="border-t border-slate-800 pt-3 space-y-3">
        {/* Patient Identity Badge */}
        <div>
          <div className="text-xs text-slate-500">Patient Identity</div>
          <div className="text-base font-bold text-slate-100">{firstName} {lastName}</div>
          <div className="flex justify-between text-xs text-slate-400 mt-1">
            <span>DOB: <strong className="text-slate-200">{dob}</strong></span>
            <span>ID: <strong className="text-slate-200">{memberId}</strong></span>
          </div>
        </div>

        {/* Provider Details */}
        <div className="border-t border-slate-800/50 pt-2">
          <div className="text-xs text-slate-500">Billing Provider</div>
          <div className="flex justify-between text-xs text-slate-300 mt-1">
            <span>NPI: <strong className="text-slate-100">{providerId}</strong></span>
            <span>Urgency: <strong className="text-slate-100">{urgency}</strong></span>
          </div>
        </div>

        {/* Clinical Metadata */}
        <div className="border-t border-slate-800/50 pt-2">
          <div className="text-xs text-slate-500 mb-1.5">Clinical Codes</div>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-mono bg-slate-800/80 border border-slate-700/50 px-2 py-0.5 rounded text-slate-300">
              CPT: {cptCode}
            </span>
            <span className="text-xs font-mono bg-slate-800/80 border border-slate-700/50 px-2 py-0.5 rounded text-slate-300">
              ICD-10: {icdCode}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
