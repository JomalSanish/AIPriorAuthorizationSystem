import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { IngestionPanel } from './components/IngestionPanel';
import { DemographicsCard } from './components/DemographicsCard';
import { PolicyChecklist } from './components/PolicyChecklist';
import { TriagePanel } from './components/TriagePanel';
import { ComplianceDrawer } from './components/ComplianceDrawer';

interface CaseSummary {
  request_id: string;
  review_status: string;
  routing_queue: string;
  patient_data: {
    member_id: string;
    cpt_code: string;
  };
}

interface CaseState {
  request_id: string;
  patient_data: {
    member_id: string;
    provider_id: string;
    cpt_code: string;
    icd_code: string;
    raw_text: string;
    missing_fields: string[];
    duplicate_suspected: boolean;
    documents: any[];
    [key: string]: any;
  };
  classification: {
    type?: string;
    urgency?: string;
    reason?: string;
  };
  evidence: any[];
  gap_analysis: {
    status: string;
    reasoning: string;
    checklist_items: any[];
    missing_info: string[];
  };
  artifacts: {
    summary?: string;
    communication_draft?: string;
    compliance_hash?: string;
    audit_timestamp?: string;
    audit_model?: string;
  };
  review_status: string;
  routing_queue: string;
  audit_trail: string[];
  current_policy_rules: string[];
  current_required_docs: string[];
}

function AppContent() {
  const navigate = useNavigate();
  const location = useLocation();

  const [casesList, setCasesList] = useState<Record<string, CaseSummary>>({});
  const [activeCaseKey, setActiveCaseKey] = useState<string>('PA-72148-A (Approved MRI)');
  const [activeCase, setActiveCase] = useState<CaseState | null>(null);
  
  const [loading, setLoading] = useState(false);

  // Fetch navigation cases list on load
  const fetchCasesList = async () => {
    try {
      const res = await fetch('/api/cases');
      if (res.ok) {
        const data = await res.json();
        setCasesList(data.cases);
      }
    } catch (err) {
      console.error('Error fetching cases list:', err);
    }
  };

  // Fetch full details of active case
  const fetchActiveCaseDetails = async (key: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/cases/${encodeURIComponent(key)}`);
      if (res.ok) {
        const data: CaseState = await res.json();
        setActiveCase(data);
        
        // Sync stepper wizard position based on case properties
        if (data.review_status === 'APPROVED' || data.review_status === 'REJECTED' || data.review_status === 'REQUEST MORE INFO') {
          navigate('/triage');
        } else if (data.patient_data?.cpt_code) {
          navigate('/policy');
        } else {
          navigate('/ingest');
        }
      }
    } catch (err) {
      console.error('Error fetching active case details:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCasesList();
  }, []);

  useEffect(() => {
    if (activeCaseKey && activeCaseKey !== '+ Create New Case') {
      fetchActiveCaseDetails(activeCaseKey);
    } else if (activeCaseKey === '+ Create New Case') {
      // Empty mock state for creation flow
      setActiveCase({
        request_id: '',
        patient_data: {
          member_id: '',
          provider_id: '',
          cpt_code: '',
          icd_code: '',
          raw_text: '',
          missing_fields: [],
          duplicate_suspected: false,
          documents: []
        },
        classification: {},
        evidence: [],
        gap_analysis: {
          status: 'PENDING',
          reasoning: '',
          checklist_items: [],
          missing_info: []
        },
        artifacts: {},
        review_status: 'PENDING',
        routing_queue: 'Intake',
        audit_trail: [],
        current_policy_rules: [],
        current_required_docs: []
      });
      navigate('/ingest');
    }
  }, [activeCaseKey]);

  // Intake agent completed callback
  const handleIngestSuccess = (data: CaseState, key: string) => {
    setActiveCase(data);
    fetchCasesList();
    setActiveCaseKey(key);
    navigate('/policy');
  };

  // Gap analysis agent run
  const triggerGapAnalysis = async () => {
    if (!activeCaseKey || activeCaseKey === '+ Create New Case') return;
    setLoading(true);
    try {
      const res = await fetch('/api/cases/gap-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_key: activeCaseKey })
      });
      if (res.ok) {
        const data = await res.json();
        setActiveCase(data);
      }
    } catch (err) {
      console.error('Error running gap agent:', err);
    } finally {
      setLoading(false);
    }
  };

  // Trigger gap analysis automatically if Policy is active and checklist is empty
  useEffect(() => {
    if (location.pathname === '/policy' && activeCase && (!activeCase.gap_analysis?.checklist_items || activeCase.gap_analysis.checklist_items.length === 0)) {
      triggerGapAnalysis();
    }
  }, [location.pathname, activeCase]);

  // Summary agent run when proceeding to Triage
  const handleProceedToTriage = async () => {
    if (!activeCaseKey || activeCaseKey === '+ Create New Case') return;
    setLoading(true);
    try {
      const res = await fetch('/api/cases/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_key: activeCaseKey })
      });
      if (res.ok) {
        const data = await res.json();
        setActiveCase(data);
        navigate('/triage');
      }
    } catch (err) {
      console.error('Error running summary agent:', err);
    } finally {
      setLoading(false);
    }
  };

  // Triage completed callback
  const handleTriageComplete = (updatedCase: CaseState) => {
    setActiveCase(updatedCase);
    fetchCasesList();
  };

  let currentStep = 1;
  if (location.pathname === '/policy') currentStep = 2;
  if (location.pathname === '/triage') currentStep = 3;

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f1f5f9] pb-32">
      {loading && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex flex-col items-center justify-center space-y-3">
          <div className="w-10 h-10 border-4 border-indigo-500/30 border-t-indigo-400 rounded-full animate-spin" />
          <span className="text-xs font-semibold text-slate-300">Running Multi-Agent pipeline...</span>
        </div>
      )}

      {/* Top Navbar Header */}
      <header className="sticky top-0 z-40 bg-[#0b0d13]/70 backdrop-blur-md border-b border-slate-800/80 px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <div>
            <h1 className="text-xl md:text-2xl font-extrabold tracking-tight bg-gradient-to-r from-purple-400 via-indigo-400 to-sky-400 bg-clip-text text-transparent">
              🩺 Prior Authorization Evidence Dashboard
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Multi-Agentic Medical Policy Compliance Validation Engine
            </p>
          </div>

          {/* Stepper Graphic */}
          <div className="flex items-center gap-2 bg-slate-950/40 border border-slate-800 px-4 py-2 rounded-xl text-xs">
            <span className={`font-semibold transition-colors duration-200 ${currentStep === 1 ? 'text-indigo-400' : 'text-slate-500'}`}>
              1. Ingest Docs
            </span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-700" />
            <span className={`font-semibold transition-colors duration-200 ${currentStep === 2 ? 'text-indigo-400' : 'text-slate-500'}`}>
              2. Policy Verification
            </span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-700" />
            <span className={`font-semibold transition-colors duration-200 ${currentStep === 3 ? 'text-indigo-400' : 'text-slate-500'}`}>
              3. Human Triage
            </span>
          </div>
        </div>
      </header>

      {/* Horizontal Progress Bar */}
      <div className="w-full bg-slate-900 h-1">
        <div 
          className="bg-gradient-to-r from-purple-500 via-indigo-500 to-sky-500 h-1 transition-all duration-300"
          style={{ width: `${(currentStep / 3) * 100}%` }}
        />
      </div>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* COLUMN 1: Sidebar - Case Navigation Controls & Demographics (Left 30% - maps to lg:col-span-4) */}
          <div className="lg:col-span-4 space-y-6">
            <div className="dashboard-card p-5 space-y-4">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                Case Navigation Controls
              </h3>
              
              <div className="space-y-3">
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 mb-1">Select Review Session</label>
                  <select
                    value={activeCaseKey}
                    onChange={(e) => setActiveCaseKey(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-2 text-xs font-medium text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    {Object.keys(casesList).map((key) => (
                      <option key={key} value={key}>{key}</option>
                    ))}
                    <option value="+ Create New Case">+ Create New Case</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Demographics details badge panel (always unlocked post-population) */}
            {activeCase && (activeCase.request_id || activeCase.patient_data?.raw_text) && (
              <DemographicsCard 
                patientData={activeCase.patient_data}
                classification={activeCase.classification}
              />
            )}
          </div>

          {/* COLUMN 2: Main Content (Right 70% - maps to lg:col-span-8) */}
          <div className="lg:col-span-8">
            <Routes>
              <Route path="/ingest" element={
                <IngestionPanel 
                  onIngestSuccess={handleIngestSuccess}
                  activePatientData={activeCase?.patient_data}
                />
              } />
              
              <Route path="/policy" element={
                activeCase ? (
                  <PolicyChecklist 
                    checklistItems={activeCase.gap_analysis?.checklist_items || []}
                    overallStatus={activeCase.gap_analysis?.status || 'PENDING'}
                    clinicalNotes={activeCase.patient_data?.raw_text || ''}
                    evidence={activeCase.evidence || []}
                    onProceedToTriage={handleProceedToTriage}
                    onBackToUpload={() => navigate('/ingest')}
                    requiredDocs={activeCase.current_required_docs || []}
                  />
                ) : (
                  <div className="dashboard-card p-6 text-center text-slate-500 text-sm">
                    Awaiting active case initialization...
                  </div>
                )
              } />

              <Route path="/triage" element={
                activeCase ? (
                  <TriagePanel 
                    caseKey={activeCaseKey}
                    summary={activeCase.artifacts?.summary || ''}
                    communicationDraft={activeCase.artifacts?.communication_draft || ''}
                    checklistItems={activeCase.gap_analysis?.checklist_items || []}
                    onTriageComplete={handleTriageComplete}
                    onBackToVerification={() => navigate('/policy')}
                  />
                ) : (
                  <div className="dashboard-card p-6 text-center text-slate-500 text-sm">
                    Awaiting active case summary data...
                  </div>
                )
              } />

              <Route path="*" element={<Navigate to="/ingest" replace />} />
            </Routes>
          </div>
        </div>
      </main>

      {/* Collapsible compliance drawer ledger */}
      {activeCase && (
        <ComplianceDrawer 
          auditTrail={activeCase.audit_trail || []}
          complianceHash={activeCase.artifacts?.compliance_hash}
          auditModel={activeCase.artifacts?.audit_model}
          auditTimestamp={activeCase.artifacts?.audit_timestamp}
        />
      )}
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
