import { useEffect, useState } from "react";
import "../styles/QuestionBankPage.css";

function QuestionBankPage({
  job,
  onBack
}) {

  const [mode, setMode] =
    useState(null);

  const [count, setCount] =
    useState(0);

  const [questions, setQuestions] =
    useState([]);

  const [file, setFile] =
    useState(null);

  const [successMessage, setSuccessMessage] =
    useState("");
  const [savedQuestions, setSavedQuestions] =
    useState([]);
  const [isLoadingBank, setIsLoadingBank] =
    useState(false);

  useEffect(() => {
    fetchQuestionBank();
  }, [job?.id]);

  const fetchQuestionBank = async () => {
    if (!job?.id) {
      return;
    }

    setIsLoadingBank(true);

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/hr/jobs/${encodeURIComponent(job.id)}/question-bank`
      );
      const data = await response.json();
      setSavedQuestions(Array.isArray(data.questions) ? data.questions : []);
    } catch (error) {
      console.error("Failed to fetch question bank:", error);
      setSavedQuestions([]);
    } finally {
      setIsLoadingBank(false);
    }
  };


  const createFields = () => {

    const arr = [];

    for (
      let i = 0;
      i < count;
      i++
    ) {
      arr.push({
        question: "",
        expected_answer: "",
        difficulty: "Medium",
        category: ""
      });
    }

    setQuestions(arr);
    setSuccessMessage("");
  };


  const updateQuestion = (
    index,
    field,
    value
  ) => {

    const updated =
      [...questions];

    updated[index][field] =
      value;

    setQuestions(updated);
  };


  const saveQuestions =
    async () => {

      try {

        const response =
          await fetch(
            "http://127.0.0.1:8000/api/hr/question-bank/save",
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json"
              },
              body: JSON.stringify({
                job_id: job.id,
                questions
              })
            }
          );

        const data =
          await response.json();

        setSuccessMessage(
          "Question bank saved successfully."
        );

        setQuestions([]);
        setCount(0);
        fetchQuestionBank();

      } catch (error) {

        console.error(error);

        setSuccessMessage(
          "Failed to save question bank."
        );
      }
    };


  const uploadFile =
    async () => {

      if (!file) return;

      try {

        const formData =
          new FormData();

        formData.append(
          "job_id",
          job.id
        );

        formData.append(
          "file",
          file
        );

        const response =
          await fetch(
            "http://127.0.0.1:8000/api/hr/question-bank/upload",
            {
              method: "POST",
              body: formData
            }
          );

        const data =
          await response.json();

        setSuccessMessage(
          `${data.questions_saved} questions saved successfully.`
        );

        setFile(null);
        fetchQuestionBank();

      } catch (error) {

        console.error(error);

        setSuccessMessage(
          "Failed to upload question file."
        );
      }
    };


  return (

    <main className="hr-page">

      <div className="question-bank-container">

        <button
          className="back-button"
          onClick={onBack}
        >
          Back
        </button>

        <h1 className="question-bank-title">
          Question Bank - {job.title}
        </h1>

        <div className="question-note">

          <h3>
            Upload Instructions
          </h3>

          <p>
            Supported file formats:
          </p>

          <strong>
            Format 1 (Recommended)
          </strong>

          <pre>
{`Q: What is React?
A: JavaScript library

Q: What is FastAPI?
A: Python framework`}
          </pre>

          <strong>
            Format 2
          </strong>

          <pre>
{`1) What is React?
ANS:= JavaScript library

2) What is FastAPI?
ANS:= Python framework`}
          </pre>

        </div>

        <div className="question-bank-buttons">

          <button
            className="question-bank-btn"
            onClick={() =>
              setMode("file")
            }
          >
            Upload Text File
          </button>

          <button
            className="question-bank-btn"
            onClick={() =>
              setMode("manual")
            }
          >
            Create Manually
          </button>

        </div>

        {mode === "file" && (

          <div className="question-card">

            <input
              type="file"
              accept=".txt"
              onChange={(e) =>
                setFile(
                  e.target.files[0]
                )
              }
            />

            <button
              className="question-bank-btn"
              onClick={uploadFile}
            >
              Upload
            </button>

          </div>

        )}

        {mode === "manual" && (

          <div>

            <input
              className="question-count"
              type="number"
              placeholder="Number of Questions"
              value={count}
              onChange={(e) =>
                setCount(
                  Number(
                    e.target.value
                  )
                )
              }
            />

            <button
              className="question-bank-btn"
              onClick={createFields}
            >
              Generate Questions
            </button>

            {questions.map(
              (
                item,
                index
              ) => (

                <div
                  className="question-card"
                  key={index}
                >

                  <input
                    className="question-input"
                    placeholder={`Question ${index + 1}`}
                    value={
                      item.question
                    }
                    onChange={(e) =>
                      updateQuestion(
                        index,
                        "question",
                        e.target.value
                      )
                    }
                  />

                  <textarea
                    className="question-answer"
                    placeholder="Expected Answer"
                    value={
                      item.expected_answer
                    }
                    onChange={(e) =>
                      updateQuestion(
                        index,
                        "expected_answer",
                        e.target.value
                      )
                    }
                  />

                  <select
                    className="question-input"
                    value={item.difficulty || "Medium"}
                    onChange={(e) =>
                      updateQuestion(
                        index,
                        "difficulty",
                        e.target.value
                      )
                    }
                  >
                    <option value="Easy">Easy</option>
                    <option value="Medium">Medium</option>
                    <option value="Hard">Hard</option>
                  </select>

                  <input
                    className="question-input"
                    placeholder="Skill / Category / Topic"
                    value={item.category || ""}
                    onChange={(e) =>
                      updateQuestion(
                        index,
                        "category",
                        e.target.value
                      )
                    }
                  />

                </div>

              )
            )}

            {questions.length > 0 && (

              <button
                className="question-bank-btn"
                onClick={saveQuestions}
              >
                Save Question Bank
              </button>

            )}

          </div>

        )}

        {successMessage && (

          <div className="success-message">
            {successMessage}
          </div>

        )}

        <section className="question-bank-view">
          <h2>Uploaded Question Bank</h2>
          {isLoadingBank ? (
            <p>Loading question bank...</p>
          ) : savedQuestions.length ? (
            <div className="question-bank-list">
              {savedQuestions.map((item, index) => (
                <article className="question-bank-review-card" key={`${item.id || index}-${item.question}`}>
                  <div className="question-bank-review-heading">
                    <span>Question {index + 1}</span>
                    <strong>{item.difficulty || "Medium"}</strong>
                  </div>
                  <p>{item.question}</p>
                  <small>Category: {item.category || item.skill || item.topic || "Not specified"}</small>
                  <div className="expected-answer-box">
                    <span>Expected Answer</span>
                    <p>{item.expected_answer || item.expectedAnswer || "Not provided"}</p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p>No question bank uploaded.</p>
          )}
        </section>

      </div>

    </main>

  );
}

export default QuestionBankPage;
