/**
 * ImportStructureDialog - Dialog for importing a structure file
 */

import { useState, useCallback } from 'react';
import { Modal } from './Modal';
import { useQVClient } from '../../hooks/useQVClient';

interface ImportStructureDialogProps {
  isOpen: boolean;
  projectRoot: string;
  onClose: () => void;
  onSuccess: (structureId: string) => void;
}

export function ImportStructureDialog({ 
  isOpen,
  projectRoot,
  onClose, 
  onSuccess,
}: ImportStructureDialogProps) {
  const qv = useQVClient();
  
  const [sourceFile, setSourceFile] = useState('');
  const [structureName, setStructureName] = useState('');
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const handleBrowse = useCallback(async () => {
    if (window.qv?.openFile) {
      const path = await window.qv.openFile({
        title: 'Select Structure File',
        filters: [
          { name: 'Structure Files', extensions: ['cif', 'json', 'in', 'xsf', 'xyz', 'poscar', 'vasp'] },
          { name: 'CIF Files', extensions: ['cif'] },
          { name: 'QE Input Files', extensions: ['in'] },
          { name: 'All Files', extensions: ['*'] },
        ],
      });
      if (path) {
        setSourceFile(path);
        // Auto-fill structure name from filename if empty
        if (!structureName) {
          const fileName = path.split('/').pop() || path.split('\\').pop() || '';
          const baseName = fileName.replace(/\.[^/.]+$/, ''); // Remove extension
          setStructureName(baseName);
        }
      }
    }
  }, [structureName]);
  
  const handleImport = useCallback(async () => {
    if (!sourceFile) {
      setError('Please select a structure file');
      return;
    }
    
    if (!projectRoot) {
      setError('No project loaded');
      return;
    }
    
    setIsImporting(true);
    setError(null);
    
    const response = await qv.call('import_structure', {
      project_root: projectRoot,
      source_file: sourceFile,
      name: structureName || undefined,
    });
    
    setIsImporting(false);
    
    if (response.ok && response.data) {
      onSuccess(response.data.structure_id);
      handleClose();
    } else {
      setError(response.error?.message || 'Failed to import structure');
    }
  }, [qv, projectRoot, sourceFile, structureName, onSuccess]);
  
  const handleClose = useCallback(() => {
    setSourceFile('');
    setStructureName('');
    setError(null);
    onClose();
  }, [onClose]);
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Import Structure"
      size="medium"
      footer={
        <>
          <button className="btn btn--secondary" onClick={handleClose} data-testid="qv-btn-cancel-import-structure">
            Cancel
          </button>
          <button
            className={`btn btn--primary ${isImporting ? 'btn--loading' : ''}`}
            onClick={handleImport}
            disabled={isImporting || !sourceFile}
            data-testid="qv-btn-confirm-import-structure"
          >
            Import
          </button>
        </>
      }
    >
      <div className="modal-form" data-testid="qv-import-structure-dialog">
        <div className="form-group">
          <label className="form-label form-label--required">
            Structure File
          </label>
          <div className="form-input-group">
            <input
              type="text"
              className="form-input form-input--mono"
              value={sourceFile}
              onChange={(e) => setSourceFile(e.target.value)}
              placeholder="Select a CIF, XSF, or QE input file..."
              data-testid="qv-import-structure-file"
            />
            <button className="form-button" onClick={handleBrowse} data-testid="qv-import-structure-browse">
              📂
            </button>
          </div>
          <span className="form-hint">
            Supported: CIF, XSF, XYZ, POSCAR, QE input (.in), QV JSON
          </span>
        </div>
        
        <div className="form-group">
          <label className="form-label">
            Structure Name
          </label>
          <input
            type="text"
            className="form-input"
            value={structureName}
            onChange={(e) => setStructureName(e.target.value)}
            placeholder="Silicon bulk"
            data-testid="qv-import-structure-name"
          />
          <span className="form-hint">
            Optional. Defaults to the filename.
          </span>
        </div>
        
        {error && (
          <div className="form-error">
            ⚠️ {error}
          </div>
        )}
      </div>
    </Modal>
  );
}

