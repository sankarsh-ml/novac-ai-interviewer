function QwenDifficultySplit({ hasValidTotalQuestions, difficultySplit, total, disabled, onChange }) {
  return (
    <section className="qwen-panel">
      <p>Qwen will generate interview questions automatically using the job description, required skills, and candidate resume/project details.</p>
      {!hasValidTotalQuestions && (
        <p className="qwen-step-note">Enter a valid Total Questions value to set the Easy, Medium, and Hard split.</p>
      )}
      {hasValidTotalQuestions && (
        <>
          <div className="qwen-split-grid">
            {["easy", "medium", "hard"].map((difficulty) => (
              <label key={difficulty}>
                {difficulty.charAt(0).toUpperCase() + difficulty.slice(1)} Questions
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={difficultySplit[difficulty]}
                  disabled={disabled}
                  onChange={(event) => onChange({ ...difficultySplit, [difficulty]: event.target.value })}
                />
              </label>
            ))}
          </div>
          <strong>Total Qwen Questions: {total}</strong>
        </>
      )}
    </section>
  );
}

export default QwenDifficultySplit;
