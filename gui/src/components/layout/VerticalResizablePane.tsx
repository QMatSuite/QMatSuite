/**
 * VerticalResizablePane - A container with a draggable horizontal resize handle
 * 
 * Allows users to resize the pane height by dragging the bottom edge.
 */

import { useState, useCallback, useRef, useEffect, ReactNode } from 'react';
import './VerticalResizablePane.css';

interface VerticalResizablePaneProps {
  children: ReactNode;
  /** Default height in pixels or percentage string */
  defaultHeight?: number | string;
  /** Minimum height in pixels */
  minHeight?: number;
  /** Maximum height in pixels */
  maxHeight?: number;
  /** Storage key for persisting height */
  storageKey?: string;
  /** Additional class name */
  className?: string;
}

export function VerticalResizablePane({
  children,
  defaultHeight = 300,
  minHeight = 150,
  maxHeight = 600,
  storageKey,
  className = '',
}: VerticalResizablePaneProps) {
  // Load saved height from localStorage
  const getSavedHeight = () => {
    if (storageKey) {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= minHeight && parsed <= maxHeight) {
          return parsed;
        }
      }
    }
    return typeof defaultHeight === 'number' ? defaultHeight : 300;
  };
  
  const [height, setHeight] = useState(getSavedHeight);
  const [isResizing, setIsResizing] = useState(false);
  const paneRef = useRef<HTMLDivElement>(null);
  
  // Handle resize drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    
    const startY = e.clientY;
    const startHeight = height;
    
    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaY = moveEvent.clientY - startY;
      const newHeight = Math.max(minHeight, Math.min(maxHeight, startHeight + deltaY));
      setHeight(newHeight);
    };
    
    const handleMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [height, minHeight, maxHeight]);
  
  // Save height to localStorage when it changes
  useEffect(() => {
    if (storageKey) {
      localStorage.setItem(storageKey, height.toString());
    }
  }, [height, storageKey]);
  
  return (
    <div 
      ref={paneRef}
      className={`vertical-resizable-pane ${isResizing ? 'vertical-resizable-pane--resizing' : ''} ${className}`}
      style={{ 
        height: `${height}px`,
        flexShrink: 0,
      }}
    >
      <div className="vertical-resizable-pane__content">
        {children}
      </div>
      
      {/* Resize Handle */}
      <div 
        className="vertical-resizable-pane__handle"
        onMouseDown={handleMouseDown}
        title="Drag to resize"
      />
    </div>
  );
}

