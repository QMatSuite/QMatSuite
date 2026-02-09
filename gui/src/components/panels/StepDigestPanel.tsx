interface StepDigestPanelProps {
  loading: boolean;
  error: string | null;
  digest: Record<string, unknown> | null;
  digestSha: string | null;
  engine?: string | null;
}

export function StepDigestPanel({
  loading,
  error,
  digest,
  digestSha,
  engine,
}: StepDigestPanelProps) {
  if (loading) {
    return <div className="analysis-digest analysis-surface__placeholder">Loading step digest...</div>;
  }

  if (error) {
    return <div className="analysis-digest analysis-surface__error">{error}</div>;
  }

  if (!digest) {
    return (
      <div className="analysis-digest analysis-surface__placeholder">
        No digest was recorded for this step.
      </div>
    );
  }

  return (
    <div className="analysis-digest">
      <div className="analysis-digest__header">
        <span>Step Digest</span>
        {engine ? <span className="analysis-digest__engine">{engine}</span> : null}
      </div>
      <div className="analysis-digest__meta">
        <code>{digestSha ?? 'no-digest-sha'}</code>
      </div>
      <table className="analysis-digest__table">
        <tbody>
          {Object.entries(digest).map(([key, value]) => (
            <tr key={key}>
              <th>{key}</th>
              <td>{formatDigestValue(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatDigestValue(value: unknown): string {
  if (value === null || value === undefined) {
    return 'null';
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (typeof value === 'string') {
    return value;
  }
  return JSON.stringify(value);
}
