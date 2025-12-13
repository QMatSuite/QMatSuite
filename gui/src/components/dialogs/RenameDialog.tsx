/**
 * RenameDialog - Dialog for renaming structures or calculations
 */

import { useState, useCallback, useEffect } from 'react';
import { Modal } from './Modal';
import './RenameDialog.css';

interface RenameDialogProps {
  isOpen: boolean;
  onClose: () => void;
  /** Title for the dialog (e.g., "Rename Structure") */
  title: string;
  currentName: string;
  /** Called when rename is confirmed. Returns true on success. */
  onRename: (newName: string) => Promise<boolean>;
  /** Optional loading state controlled by parent */
  isLoading?: boolean;
}

export function RenameDialog({
  isOpen,
  onClose,
  title,
  currentName,
  onRename,
  isLoading = false,
}: RenameDialogProps) {
  const [newName, setNewName] = useState(currentName);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const loading = isLoading || isSubmitting;
  
  // Reset state when dialog opens
  useEffect(() => {
    if (isOpen) {
      setNewName(currentName);
      setError(null);
    }
  }, [isOpen, currentName]);
  
  const handleSubmit = useCallback(async () => {
    if (!newName.trim() || newName === currentName) {
      return;
    }
    
    setIsSubmitting(true);
    setError(null);
    
    try {
      const success = await onRename(newName.trim());
      if (success) {
        onClose();
      } else {
        setError('Failed to rename. Please try again.');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Rename failed');
    } finally {
      setIsSubmitting(false);
    }
  }, [newName, currentName, onRename, onClose]);
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="small"
      footer={
        <div className="rename-dialog__footer">
          <button 
            className="dialog-btn dialog-btn--secondary"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </button>
          <button 
            className="dialog-btn dialog-btn--primary"
            onClick={handleSubmit}
            disabled={loading || !newName.trim() || newName === currentName}
          >
            {loading ? 'Renaming...' : 'Rename'}
          </button>
        </div>
      }
    >
      <div className="rename-dialog">
        <p className="rename-dialog__info">
          Enter a new name for <strong>{currentName}</strong>
        </p>
        
        <div className="rename-dialog__field">
          <label className="rename-dialog__label">New Name</label>
          <input
            type="text"
            className="rename-dialog__input"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Enter new name"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !loading) {
                handleSubmit();
              }
            }}
          />
        </div>
        
        {error && (
          <div className="rename-dialog__error">
            <span className="error-icon">⚠️</span>
            {error}
          </div>
        )}
      </div>
    </Modal>
  );
}
