import { useCallback, useEffect, useState } from 'react';

import { useQVClient } from '../../hooks/useQVClient';
import { normalizeProjectRoot } from '../../utils/pathUtils';

interface RawFileViewerProps {
  projectRoot: string;
  calculation: string;
  stepId: string;
}

interface RawArtifact {
  path_relative_to_raw: string;
  kind: string;
  size_bytes: number;
  mtime: number;
  is_default_candidate: boolean;
}

export function RawFileViewer({ projectRoot, calculation, stepId }: RawFileViewerProps) {
  const qv = useQVClient();
  const [files, setFiles] = useState<RawArtifact[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState<string>('');
  const [truncated, setTruncated] = useState(false);
  const [totalBytes, setTotalBytes] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);

  const loadFiles = useCallback(async () => {
    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot || !calculation || !stepId) {
      return;
    }

    setLoadingFiles(true);
    setError(null);
    try {
      const response = await qv.call('list_raw_files', {
        project_root: normalizedRoot,
        calculation,
        step: stepId,
      });

      if (!response.ok || !response.data) {
        setFiles([]);
        setSelectedFile(null);
        setError(response.error?.message ?? 'Failed to list raw files');
        return;
      }

      const nextArtifacts = response.data.artifacts ?? [];
      setFiles(nextArtifacts);
      if (nextArtifacts.length === 0) {
        setSelectedFile(null);
        return;
      }
      const preferred = nextArtifacts.find((item) => item.is_default_candidate);
      setSelectedFile(preferred?.path_relative_to_raw ?? nextArtifacts[0].path_relative_to_raw);
    } catch (err) {
      setFiles([]);
      setSelectedFile(null);
      setError(err instanceof Error ? err.message : 'Failed to list raw files');
    } finally {
      setLoadingFiles(false);
    }
  }, [calculation, projectRoot, qv, stepId]);

  const loadContent = useCallback(
    async (filename: string) => {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedRoot || !calculation || !stepId) {
        return;
      }

      setLoadingContent(true);
      setError(null);
      try {
        const response = await qv.call('read_raw_file', {
          project_root: normalizedRoot,
          calculation,
          step: stepId,
          filename,
          head_lines: 1000,
          tail_lines: 100,
        });

        if (!response.ok || !response.data) {
          setContent('');
          setError(response.error?.message ?? 'Failed to read raw file');
          return;
        }

        setContent(response.data.content ?? '');
        setTruncated(Boolean(response.data.truncated));
        setTotalBytes(response.data.total_bytes ?? null);
      } catch (err) {
        setContent('');
        setError(err instanceof Error ? err.message : 'Failed to read raw file');
      } finally {
        setLoadingContent(false);
      }
    },
    [calculation, projectRoot, qv, stepId],
  );

  useEffect(() => {
    setContent('');
    setTotalBytes(null);
    setTruncated(false);
    loadFiles();
  }, [loadFiles]);

  useEffect(() => {
    if (!selectedFile) {
      setContent('');
      setTotalBytes(null);
      setTruncated(false);
      return;
    }
    loadContent(selectedFile);
  }, [loadContent, selectedFile]);

  if (loadingFiles && files.length === 0) {
    return <div className="analysis-surface__placeholder">Loading raw files...</div>;
  }

  if (files.length === 0) {
    return (
      <div className="analysis-surface__placeholder">
        No raw text files are available for this step.
      </div>
    );
  }

  return (
    <div className="analysis-raw-viewer">
      <div className="analysis-raw-viewer__toolbar">
        <label htmlFor="analysis-raw-file-select">Raw File</label>
        <select
          id="analysis-raw-file-select"
          value={selectedFile ?? ''}
          onChange={(event) => setSelectedFile(event.target.value)}
        >
          {files.map((artifact) => (
            <option key={artifact.path_relative_to_raw} value={artifact.path_relative_to_raw}>
              {artifact.path_relative_to_raw}
            </option>
          ))}
        </select>
        {totalBytes !== null && (
          <span className="analysis-raw-viewer__meta">
            {formatBytes(totalBytes)}{truncated ? ' (truncated)' : ''}
          </span>
        )}
      </div>
      <div className="analysis-raw-viewer__content">
        {error ? (
          <div className="analysis-surface__error">{error}</div>
        ) : loadingContent ? (
          <div className="analysis-surface__placeholder">Loading file content...</div>
        ) : (
          <pre>{content || '(empty file)'}</pre>
        )}
      </div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
