/**
 * ResizablePane - A container with a draggable resize handle
 * 
 * Allows users to resize the pane by dragging the right edge, similar to VS Code's sidebar.
 * 
 * Width Behavior:
 * - Width is set via inline style: `width: ${width}px` (pixels)
 * - Uses `flexShrink: 0` to prevent flex container from shrinking it below the set width
 * - Width is clamped between minWidth and maxWidth props during drag
 * - Saved width is persisted to localStorage using storageKey
 * - The component respects the provided minWidth/maxWidth props; no internal hardcoded minimums
 */

import { useState, useCallback, useRef, useEffect, ReactNode, useImperativeHandle, forwardRef } from 'react';
import './ResizablePane.css';

export interface ResizablePaneRef {
  collapse: () => void;
  expand: () => void;
  toggle: () => void;
  getWidth: () => number;
  setWidth: (newWidth: number) => void;
}

interface ResizablePaneProps {
  children: ReactNode;
  /** Default width in pixels */
  defaultWidth?: number;
  /** Minimum width in pixels */
  minWidth?: number;
  /** Maximum width in pixels */
  maxWidth?: number;
  /** Storage key for persisting width */
  storageKey?: string;
  /** Position of the resize handle */
  resizePosition?: 'left' | 'right';
  /** Additional class name */
  className?: string;
  /** Collapsed width (defaults to minWidth) */
  collapsedWidth?: number;
}

export const ResizablePane = forwardRef<ResizablePaneRef, ResizablePaneProps>(({
  children,
  defaultWidth = 400,
  minWidth = 280,
  maxWidth = 600,
  storageKey,
  resizePosition = 'right',
  className = '',
  collapsedWidth,
}, ref) => {
  // Load saved width from localStorage
  const getSavedWidth = () => {
    if (storageKey) {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= minWidth && parsed <= maxWidth) {
          return parsed;
        }
      }
    }
    return defaultWidth;
  };
  
  const [width, setWidth] = useState(getSavedWidth);
  const [isResizing, setIsResizing] = useState(false);
  const [expandedWidth, setExpandedWidth] = useState(getSavedWidth);
  const paneRef = useRef<HTMLDivElement>(null);
  const collapsedW = collapsedWidth ?? minWidth;
  
  // Expose collapse/expand methods via ref
  useImperativeHandle(ref, () => ({
    collapse: () => {
      if (width > collapsedW) {
        setExpandedWidth(width);
        setWidth(collapsedW);
      }
    },
    expand: () => {
      setWidth(expandedWidth);
    },
    toggle: () => {
      if (width <= collapsedW) {
        setWidth(expandedWidth);
      } else {
        setExpandedWidth(width);
        setWidth(collapsedW);
      }
    },
    getWidth: () => width,
    setWidth: (newWidth: number) => {
      const clampedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
      setWidth(clampedWidth);
      if (clampedWidth > collapsedW) {
        setExpandedWidth(clampedWidth);
      }
    },
  }), [width, collapsedW, expandedWidth, minWidth, maxWidth]);
  
  // Handle resize drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    
    const startX = e.clientX;
    const startWidth = width;
    
    const handleMouseMove = (moveEvent: MouseEvent) => {
      let deltaX = moveEvent.clientX - startX;
      if (resizePosition === 'left') {
        deltaX = -deltaX;
      }
      const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth + deltaX));
      setWidth(newWidth);
    };
    
    const handleMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [width, minWidth, maxWidth, resizePosition]);
  
  // Save width to localStorage when it changes
  useEffect(() => {
    if (storageKey) {
      localStorage.setItem(storageKey, width.toString());
    }
  }, [width, storageKey]);
  
  return (
    <div 
      ref={paneRef}
      className={`resizable-pane ${isResizing ? 'resizable-pane--resizing' : ''} ${className}`}
      style={{ 
        width: `${width}px`,
        flexShrink: 0,
      }}
    >
      <div className="resizable-pane__content">
        {children}
      </div>
      
      {/* Resize Handle */}
      <div 
        className={`resizable-pane__handle resizable-pane__handle--${resizePosition}`}
        onMouseDown={handleMouseDown}
        title="Drag to resize"
      />
    </div>
  );
});

