/**
 * CalculationAnalysisTab - Analysis tab content
 * 
 * Shows SCF/DOS/Bands analysis for the selected calculation.
 * Reuses CalculationAnalysisPanel logic but adapted for tab context.
 */

import { CalculationAnalysisPanel } from './CalculationAnalysisPanel';
import type { CalculationInfo, CalculationDetailResult } from '../../types/qms';
import './CalculationAnalysisTab.css';

interface CalculationAnalysisTabProps {
  projectRoot: string;
  calculation: CalculationInfo | CalculationDetailResult | null;
}

export function CalculationAnalysisTab({ projectRoot, calculation }: CalculationAnalysisTabProps) {
  if (!calculation) {
    return (
      <div className="calculation-analysis-tab calculation-analysis-tab--empty">
        <p>No calculation selected</p>
      </div>
    );
  }
  
  return (
    <div className="calculation-analysis-tab">
      <CalculationAnalysisPanel
        projectRoot={projectRoot}
        calculation={calculation}
      />
    </div>
  );
}

