function CandidateActions({ onSelect, onReject }) {
  return (
    <div className="decision-actions">
      <button className="hr-button table-action-button" onClick={onSelect}>
        Select
      </button>
      <button className="delete-button table-action-button" onClick={onReject}>
        Reject
      </button>
    </div>
  );
}

export default CandidateActions;
