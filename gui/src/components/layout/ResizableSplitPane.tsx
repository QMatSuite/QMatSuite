/**
 * ResizableSplitPane - Vertical split pane with draggable divider
 * 
 * Provides a resizable split between two panels (top and bottom).
 * Persists divider position in localStorage.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import './ResizableSplitPane.css';

interface ResizableSplitPaneProps {
  top: React.ReactNode;
  bottom: React.ReactNode;
  storageKey?: string;
  defaultTopHeight?: number;
  minTopHeight?: number;
  minBottomHeight?: number;
  dividerHeight?: number;
  className?: string;
}

export function ResizableSplitPane({
  top,
  bottom,
  storageKey = 'qv.splitPane.height',
  defaultTopHeight = 260,
  minTopHeight = 180,
  minBottomHeight = 360,
  dividerHeight = 6,
  className = '',
}: ResizableSplitPaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [topHeight, setTopHeight] = useState<number>(() => {
    // Load from localStorage if available
    if (typeof window !== 'undefined' && storageKey) {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= minTopHeight) {
          return parsed;
        }
      }
    }
    return defaultTopHeight;
  });
  
  const [isDragging, setIsDragging] = useState(false);
  const dragStartY = useRef<number>(0);
  const dragStartHeight = useRef<number>(0);
  
  // Save to localStorage when height changes
  useEffect(() => {
    if (storageKey && typeof window !== 'undefined') {
      localStorage.setItem(storageKey, topHeight.toString());
    }
  }, [topHeight, storageKey]);
  
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStartY.current = e.clientY;
    dragStartHeight.current = topHeight;
    
    // Add global mouse move and up handlers
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      
      const containerRect = containerRef.current.getBoundingClientRect();
      const containerHeight = containerRect.height;
      const deltaY = e.clientY - dragStartY.current;
      const newHeight = dragStartHeight.current + deltaY;
      
      // Clamp between min and max
      const maxHeight = containerHeight - minBottomHeight - dividerHeight;
      const clampedHeight = Math.max(minTopHeight, Math.min(maxHeight, newHeight));
      
      setTopHeight(clampedHeight);
    };
    
    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [topHeight, minTopHeight, minBottomHeight, dividerHeight]);
  
  return (
    <div 
      ref={containerRef}
      className={`resizable-split-pane ${className}`}
      style={{
        display: 'grid',
        gridTemplateRows: `${topHeight}px ${dividerHeight}px 1fr`,
        height: '100%',
        minHeight: 0,
        overflow: 'hidden',
      }}
    >
      {/* Top panel */}
      <div className="resizable-split-pane__top">
        {top}
      </div>
      
      {/* Divider */}
      <div 
        className={`resizable-split-pane__divider ${isDragging ? 'resizable-split-pane__divider--dragging' : ''}`}
        onMouseDown={handleMouseDown}
        style={{
          cursor: 'row-resize',
          userSelect: 'none',
          backgroundColor: isDragging ? 'var(--accent-primary)' : 'var(--border-subtle)',
          transition: isDragging ? 'none' : 'background-color 0.2s',
        }}
      >
        <div className="resizable-split-pane__divider-handle" />
      </div>
      
      {/* Bottom panel */}
      <div className="resizable-split-pane__bottom">
        {bottom}
      </div>
    </div>
  );
}
