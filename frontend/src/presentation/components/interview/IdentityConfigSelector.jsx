function IdentityConfigSelector({ identityMode, resumePhotoAvailable, hasGeneratedLink, onChange }) {
  return (
    <section className="identity-panel">
      <div>
        <span>Identity Verification:</span>
        <p>If ID verification is disabled, the candidate will skip document upload and proceed directly to face verification using the photo extracted from their resume.</p>
      </div>
      <div className="identity-options" role="radiogroup" aria-label="Identity Verification">
        <label className={identityMode === "government_id" ? "active" : ""}>
          <input
            type="radio"
            name="identity-verification"
            value="government_id"
            checked={identityMode === "government_id"}
            disabled={hasGeneratedLink}
            onChange={() => onChange("government_id")}
          />
          Require Indian Government ID Verification
        </label>
        <label className={identityMode === "resume_photo" ? "active" : ""}>
          <input
            type="radio"
            name="identity-verification"
            value="resume_photo"
            checked={identityMode === "resume_photo"}
            disabled={hasGeneratedLink || !resumePhotoAvailable}
            onChange={() => resumePhotoAvailable && onChange("resume_photo")}
          />
          Skip ID Verification and use Resume Photo
        </label>
      </div>
      {!resumePhotoAvailable && (
        <p className="identity-warning">No resume photo was found for this candidate. Indian Government ID verification is required.</p>
      )}
    </section>
  );
}

export default IdentityConfigSelector;
