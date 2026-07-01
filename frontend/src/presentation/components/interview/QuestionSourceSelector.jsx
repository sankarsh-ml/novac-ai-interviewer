function QuestionSourceSelector({
  isQuestionBankMode,
  isQwenMode,
  questionBankCount,
  hasGeneratedLink,
  onSelectQuestionBank,
  onSelectQwen,
}) {
  return (
    <section className="question-source-panel">
      <span>Question Source:</span>
      <div className="source-toggle" role="radiogroup" aria-label="Question Source">
        <label className={isQuestionBankMode ? "active" : ""}>
          <input
            type="radio"
            name="question-source"
            value="question_bank"
            checked={isQuestionBankMode}
            disabled={hasGeneratedLink || questionBankCount === 0}
            onChange={onSelectQuestionBank}
          />
          Select from Question Bank
        </label>
        <label className={isQwenMode ? "active" : ""}>
          <input
            type="radio"
            name="question-source"
            value="qwen_generated"
            checked={isQwenMode}
            disabled={hasGeneratedLink}
            onChange={onSelectQwen}
          />
          Generate with Qwen
        </label>
      </div>
    </section>
  );
}

export default QuestionSourceSelector;
