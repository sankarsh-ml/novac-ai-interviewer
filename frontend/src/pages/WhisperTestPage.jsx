import { useState } from "react";

import "../styles/WhisperTestPage.css";


function WhisperTestPage({ onBack }) {
  const [audioFile, setAudioFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!audioFile) {
      setError("Please choose an audio file.");
      return;
    }

    setIsSubmitting(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("audio", audioFile, audioFile.name);

      const response = await fetch("http://127.0.0.1:8000/test-whisper", {
        method: "POST",
        body: formData,
      });
      const data = await response.json().catch(() => null);

      if (!response.ok || !data?.success) {
        throw new Error(data?.message || `Whisper test failed. HTTP ${response.status}`);
      }

      setResult(data);
    } catch (requestError) {
      setError(requestError.message || "Whisper test failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="whisper-test-page">
      <section className="whisper-test-panel">
        <button className="back-button" type="button" onClick={onBack}>
          Back
        </button>

        <header className="whisper-test-header">
          <p className="eyebrow">Developer Tool</p>
          <h1>Whisper Test</h1>
        </header>

        <div className="whisper-test-form">
          <input
            className="whisper-file-input"
            type="file"
            accept="audio/*,.webm,.wav,.mp3,.m4a,.ogg"
            onChange={(event) => setAudioFile(event.target.files?.[0] || null)}
          />
          <button className="whisper-test-button" type="button" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Testing Whisper..." : "Test Whisper"}
          </button>
        </div>

        {error && <p className="whisper-error">{error}</p>}

        {result && (
          <section className="whisper-result">
            <h2>Transcript</h2>
            <p>{result.transcript || "No transcript returned."}</p>
            <div className="whisper-paths">
              <p><strong>Audio file path:</strong> {result.audio_file_path}</p>
              <p><strong>Transcript file path:</strong> {result.transcript_file_path}</p>
            </div>
          </section>
        )}
      </section>
    </main>
  );
}


export default WhisperTestPage;
