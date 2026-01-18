/**
 * ScanSummary - Shows parameter scan summary for a calculation.
 * 
 * MVP: Shows which steps have scans and total combinations (naive upper bound).
 */

import { useMemo } from 'react';
import type { CalculationDetailResult } from '../../types/qv';
import { countScanCombinations } from '../../utils/scanUtils';
import './ScanSummary.css';

interface ScanSummaryProps {
  calculationDetail: CalculationDetailResult | null;
  stepDetails: Map<string, { parameter_scan?: Record<string, { values: unknown[] }> }>; // step_id -> step detail
}

export function ScanSummary({
  calculationDetail,
  stepDetails,
}: ScanSummaryProps) {
  // Collect scan info from all steps
  const scanInfo = useMemo(() => {
    if (!calculationDetail) {
      return { stepsWithScans: [], totalCombinations: 0 };
    }
    
    const stepsWithScans: Array<{ stepId: string; stepType: string; scanIds: string[] }> = [];
    let totalCombinations = 0;
    
    for (const step of calculationDetail.steps || []) {
      const stepDetail = stepDetails.get(step.id);
      if (stepDetail?.parameter_scan && Object.keys(stepDetail.parameter_scan).length > 0) {
        const scanIds = Object.keys(stepDetail.parameter_scan);
        stepsWithScans.push({
          stepId: step.id,
          stepType: step.type || 'unknown',
          scanIds,
        });
        // Naive product (upper bound - doesn't account for job scoping)
        totalCombinations += countScanCombinations(stepDetail.parameter_scan);
      }
    }
    
    return { stepsWithScans, totalCombinations };
  }, [calculationDetail, stepDetails]);
  
  if (scanInfo.stepsWithScans.length === 0) {
    return null; // No scans, don't show summary
  }
  
  return (
    <div className="scan-summary">
      <div className="scan-summary__header">
        <span className="scan-summary__title">📊 Parameter Scan Summary</span>
      </div>
      
      <div className="scan-summary__content">
        <div className="scan-summary__steps">
          <span className="scan-summary__label">Steps with scans:</span>
          <div className="scan-summary__step-list">
            {scanInfo.stepsWithScans.map(({ stepId, stepType, scanIds }) => (
              <div key={stepId} className="scan-summary__step-item">
                <span className="scan-summary__step-type">{stepType}</span>
                <span className="scan-summary__step-scans">
                  ({scanIds.length} scan{scanIds.length !== 1 ? 's' : ''})
                </span>
              </div>
            ))}
          </div>
        </div>
        
        <div className="scan-summary__combinations">
          <span className="scan-summary__label">Total combinations (upper bound):</span>
          <span className="scan-summary__count">{scanInfo.totalCombinations}</span>
        </div>
        
        {scanInfo.totalCombinations > 10 && (
          <div className="scan-summary__warning">
            <span className="scan-summary__warning-icon">⚠️</span>
            <span className="scan-summary__warning-text">
              More than 10 combinations. User responsibility to verify this is intended.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

