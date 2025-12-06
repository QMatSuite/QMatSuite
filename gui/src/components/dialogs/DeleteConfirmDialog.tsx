/**
 * DeleteConfirmDialog - Confirmation dialog for deleting resources
 */

import { useState, useCallback, useEffect } from 'react';
import { Modal } from './Modal';
import './DeleteConfirmDialog.css';

interface DeleteConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  /** Type of resource being deleted (e.g., "Structure" or "Workflow") */
  resourceType: string;
  /** Name of the resource being deleted */
  resourceName: string;
  /** Warning message to display (e.g., dependency info) */
  warningMessage?: string;
  /** List of items that depend on this resource */
  dependencies?: string[];
  /** Callback when delete is confirmed. force=true bypasses dependencies */
  onConfirm: (force: boolean) => Promise<boolean>;
  /** Optional loading state controlled by parent */
  isLoading?: boolean;
  /** Whether to show the force delete option */
  forceDeleteOption?: boolean;
}

export function DeleteConfirmDialog({
  isOpen,
  onClose,
  resourceType,
  resourceName,
  warningMessage,
  dependencies,
  onConfirm,
  isLoading = false,
  forceDeleteOption = false,
}: DeleteConfirmDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forceDelete, setForceDelete] = useState(false);
  
  const loading = isLoading || isDeleting;
  const hasDependencies = dependencies && dependencies.length > 0;
  
  // Reset state when dialog opens
  useEffect(() => {
    if (isOpen) {
      setError(null);
      setForceDelete(false);
    }
  }, [isOpen]);
  
  const handleDelete = useCallback(async () => {
    setIsDeleting(true);
    setError(null);
    
    try {
      const success = await onConfirm(forceDelete);
      if (success) {
        onClose();
      } else {
        setError('Failed to delete. Please try again.');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    } finally {
      setIsDeleting(false);
    }
  }, [onConfirm, forceDelete, onClose]);
  
  // Determine if delete should be disabled
  const deleteDisabled = loading || (hasDependencies && !forceDelete);
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Delete ${resourceType}?`}
      size="small"
      footer={
        <div className="delete-dialog__footer">
          <button 
            className="dialog-btn dialog-btn--secondary"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </button>
          <button 
            className="dialog-btn dialog-btn--danger"
            onClick={handleDelete}
            disabled={deleteDisabled}
          >
            {loading ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      }
    >
      <div className="delete-dialog">
        <div className="delete-dialog__warning-icon">⚠️</div>
        
        <p className="delete-dialog__message">
          Are you sure you want to delete <strong>{resourceName}</strong>?
        </p>
        
        <p className="delete-dialog__info">
          This will move the {resourceType.toLowerCase()} to the trash folder.
        </p>
        
        {warningMessage && (
          <p className="delete-dialog__info delete-dialog__info--warning">
            {warningMessage}
          </p>
        )}
        
        {hasDependencies && (
          <div className="delete-dialog__dependencies">
            <div className="dependencies-header">
              <span className="dependencies-icon">⚠️</span>
              <span>This {resourceType.toLowerCase()} is used by:</span>
            </div>
            <ul className="dependencies-list">
              {dependencies.map((name, i) => (
                <li key={i}>{name}</li>
              ))}
            </ul>
          </div>
        )}
        
        {forceDeleteOption && (
          <label className="force-delete-option">
            <input
              type="checkbox"
              checked={forceDelete}
              onChange={(e) => setForceDelete(e.target.checked)}
            />
            <span>Delete anyway (may break dependent workflows)</span>
          </label>
        )}
        
        {error && (
          <div className="delete-dialog__error">
            <span className="error-icon">⚠️</span>
            {error}
          </div>
        )}
      </div>
    </Modal>
  );
}
