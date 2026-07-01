function InterviewTimerConfig({ interviewDate, interviewTime, questionCount, isQwenMode, disabled, onDateChange, onTimeChange, onQuestionCountChange }) {
  return (
    <section className="configure-controls">
      <input type="date" value={interviewDate} disabled={disabled} onChange={(event) => onDateChange(event.target.value)} />
      <input type="time" value={interviewTime} disabled={disabled} onChange={(event) => onTimeChange(event.target.value)} />
      <input
        type="number"
        min="1"
        placeholder={isQwenMode ? "Total Questions" : "Number of Questions"}
        value={questionCount}
        disabled={disabled}
        onChange={(event) => onQuestionCountChange(event.target.value)}
      />
    </section>
  );
}

export default InterviewTimerConfig;
