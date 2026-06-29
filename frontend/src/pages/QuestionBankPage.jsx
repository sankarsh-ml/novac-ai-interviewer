import { useEffect, useState } from "react";
import "../styles/QuestionBankPage.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const SAMPLE_CSV = `question,expected_answer,difficulty,area_of_interest,tags,job_role
Explain the difference between SQL and MongoDB.,SQL is relational while MongoDB is NoSQL.,medium,Databases,"SQL,MongoDB,NoSQL",Backend Developer
What is overfitting in machine learning?,Overfitting happens when a model learns noise and performs poorly on unseen data.,easy,Machine Learning,"ML,Overfitting",AI Engineer
How does JWT authentication work?,JWT uses signed tokens to verify identity without server-side sessions.,hard,Web Security,"JWT,Auth,Security",Full Stack Developer`;

const SAMPLE_TXT = `Question: Explain the difference between SQL and MongoDB.
Expected Answer: SQL is relational and stores data in structured tables, while MongoDB is NoSQL and stores flexible JSON-like documents.
Difficulty: Medium
Area of Interest: Databases
Tags: SQL, MongoDB, NoSQL
Job Role: Backend Developer

---

Question: What is overfitting in machine learning?
Expected Answer: Overfitting happens when a model learns noise in training data and performs poorly on unseen data.
Difficulty: Easy
Area of Interest: Machine Learning
Tags: ML, Overfitting, Model Evaluation
Job Role: AI Engineer

---

Question: How does JWT authentication work?
Expected Answer: JWT uses signed tokens to verify user identity without storing server-side sessions.
Difficulty: Hard
Area of Interest: Web Security
Tags: JWT, Authentication, Security
Job Role: Full Stack Developer`;

const SAMPLE_TXT_PREVIEW = `Question: Explain the difference between SQL and MongoDB.
Expected Answer: SQL is relational and stores data in structured tables, while MongoDB is NoSQL and stores flexible JSON-like documents.
Difficulty: Medium
Area of Interest: Databases
Tags: SQL, MongoDB, NoSQL
Job Role: Backend Developer

---

Question: What is overfitting in machine learning?
Expected Answer: Overfitting happens when a model learns noise in training data and performs poorly on unseen data.
Difficulty: Easy
Area of Interest: Machine Learning
Tags: ML, Overfitting
Job Role: AI Engineer`;

const SAMPLE_JSON = `[
  {
    "question": "Explain the difference between SQL and MongoDB.",
    "expected_answer": "SQL is relational while MongoDB is NoSQL.",
    "difficulty": "medium",
    "area_of_interest": "Databases",
    "tags": ["SQL", "MongoDB", "NoSQL"],
    "job_role": "Backend Developer"
  }
]`;

const FORMAT_FIELDS = [
  {
    field: "question",
    required: "Yes",
    description: "The interview question text",
    example: "Explain SQL vs MongoDB"
  },
  {
    field: "expected_answer",
    required: "Yes",
    description: "Ideal answer used for evaluation",
    example: "SQL is relational, MongoDB is NoSQL"
  },
  {
    field: "difficulty",
    required: "Yes",
    description: "easy, medium, or hard",
    example: "medium"
  },
  {
    field: "area_of_interest",
    required: "Yes",
    description: "Topic/domain of the question",
    example: "Databases"
  },
  {
    field: "tags",
    required: "No",
    description: "Comma-separated tags",
    example: "SQL, MongoDB, NoSQL"
  },
  {
    field: "job_role",
    required: "No",
    description: "Relevant job role",
    example: "Backend Developer"
  }
];

function QuestionBankPage({
  job,
  onBack,
  readOnly = false
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
  const [difficultyFilter, setDifficultyFilter] =
    useState("all");
  const [areaFilter, setAreaFilter] =
    useState("all");
  const [jobRoleFilter, setJobRoleFilter] =
    useState("all");
  const [searchTerm, setSearchTerm] =
    useState("");
  const [editingQuestionId, setEditingQuestionId] =
    useState("");
  const [editingQuestion, setEditingQuestion] =
    useState(null);

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
        `${API_BASE_URL}/api/hr/jobs/${encodeURIComponent(job.id)}/question-bank`
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
        difficulty: "medium",
        area_of_interest: "General",
        tags: "",
        job_role: "",
        score_weight: 1,
        source: "manual"
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
        const normalizedQuestions = questions.map((item) => ({
          ...item,
          difficulty: normalizeDifficulty(item.difficulty),
          area_of_interest: item.area_of_interest || item.category || "General",
          tags: splitTags(item.tags),
          score_weight: Number(item.score_weight) || 1,
        }));

        const response =
          await fetch(
            `${API_BASE_URL}/api/hr/question-bank/questions`,
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json"
              },
              body: JSON.stringify({
                job_id: job.id,
                questions: [
                  ...savedQuestions,
                  ...normalizedQuestions
                ]
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
        setMode(null);
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
            `${API_BASE_URL}/api/hr/question-bank/parse-upload`,
            {
              method: "POST",
              body: formData
            }
          );

        const data =
          await response.json();

        setMode("manual");
        setQuestions((data.questions || []).map((item) => ({
          question: item.question || "",
          expected_answer: item.expected_answer || item.expectedAnswer || "N/A",
          difficulty: normalizeDifficulty(item.difficulty),
          area_of_interest: item.area_of_interest || item.areaOfInterest || item.category || "General",
          tags: Array.isArray(item.tags) ? item.tags.join(", ") : item.tags || "",
          job_role: item.job_role || "",
          score_weight: item.score_weight || 1,
          source: "uploaded_file"
        })));
        setSuccessMessage("Review parsed questions, fill missing metadata, then save.");
        setFile(null);

      } catch (error) {

        console.error(error);

        setSuccessMessage(
          "Failed to upload question file."
        );
      }
    };

  const areas = Array.from(new Set(savedQuestions.map((item) => item.area_of_interest || item.areaOfInterest || item.category || "General"))).sort();
  const jobRoles = Array.from(new Set(savedQuestions.map((item) => item.job_role || item.jobRole || "").filter(Boolean))).sort();
  const filteredSavedQuestions = savedQuestions.filter((item) => {
    const difficulty = normalizeDifficulty(item.difficulty);
    const area = item.area_of_interest || item.areaOfInterest || item.category || "General";
    const jobRole = item.job_role || item.jobRole || "";
    const search = searchTerm.trim().toLowerCase();
    const tags = Array.isArray(item.tags) ? item.tags.join(" ") : String(item.tags || "");
    const haystack = [
      item.question,
      item.expected_answer || item.expectedAnswer,
      area,
      tags,
      jobRole
    ].join(" ").toLowerCase();

    return (
      (difficultyFilter === "all" || difficulty === difficultyFilter) &&
      (areaFilter === "all" || area === areaFilter) &&
      (jobRoleFilter === "all" || jobRole === jobRoleFilter) &&
      (!search || haystack.includes(search))
    );
  });

  const startEditQuestion = (question) => {
    setEditingQuestionId(getQuestionId(question));
    setEditingQuestion({
      question: question.question || "",
      expected_answer: question.expected_answer || question.expectedAnswer || "N/A",
      difficulty: normalizeDifficulty(question.difficulty),
      area_of_interest: question.area_of_interest || question.areaOfInterest || question.category || "General",
      tags: Array.isArray(question.tags) ? question.tags.join(", ") : question.tags || "",
      job_role: question.job_role || question.jobRole || "",
      score_weight: question.score_weight || 1,
      source: question.source || "manual"
    });
    setSuccessMessage("");
  };

  const updateEditingQuestion = (field, value) => {
    setEditingQuestion((current) => ({
      ...(current || {}),
      [field]: value
    }));
  };

  const saveEditedQuestion = async () => {
    if (!editingQuestionId || !editingQuestion?.question?.trim()) {
      setSuccessMessage("Question text is required.");
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/hr/question-bank/questions/${encodeURIComponent(editingQuestionId)}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            job_id: job.id,
            ...editingQuestion,
            difficulty: normalizeDifficulty(editingQuestion.difficulty),
            area_of_interest: editingQuestion.area_of_interest || "General",
            tags: splitTags(editingQuestion.tags),
            score_weight: Number(editingQuestion.score_weight) || 1
          })
        }
      );
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.detail || data.message || "Failed to update question.");
      }

      setSuccessMessage("Question updated successfully.");
      setEditingQuestionId("");
      setEditingQuestion(null);
      fetchQuestionBank();
    } catch (error) {
      console.error(error);
      setSuccessMessage(error.message || "Failed to update question.");
    }
  };

  const deleteQuestion = async (question) => {
    const questionId = getQuestionId(question);

    if (!questionId || !window.confirm("Delete this question?")) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/hr/question-bank/questions/${encodeURIComponent(questionId)}?job_id=${encodeURIComponent(job.id)}`,
        {
          method: "DELETE"
        }
      );
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.detail || data.message || "Failed to delete question.");
      }

      setSuccessMessage("Question deleted successfully.");
      if (editingQuestionId === questionId) {
        setEditingQuestionId("");
        setEditingQuestion(null);
      }
      fetchQuestionBank();
    } catch (error) {
      console.error(error);
      setSuccessMessage(error.message || "Failed to delete question.");
    }
  };

  const clearQuestionBank = async () => {
    if (!window.confirm("Clear the entire question bank for this job?")) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/hr/question-bank?job_id=${encodeURIComponent(job.id)}`,
        {
          method: "DELETE"
        }
      );
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.detail || data.message || "Failed to clear question bank.");
      }

      setSuccessMessage("Question bank cleared successfully.");
      setEditingQuestionId("");
      setEditingQuestion(null);
      fetchQuestionBank();
    } catch (error) {
      console.error(error);
      setSuccessMessage(error.message || "Failed to clear question bank.");
    }
  };

  const downloadSampleCsv = () => {
    downloadTextFile(SAMPLE_CSV, "novac_question_bank_sample.csv", "text/csv;charset=utf-8");
  };

  const downloadSampleTxt = () => {
    downloadTextFile(SAMPLE_TXT, "novac_question_bank_sample.txt", "text/plain;charset=utf-8");
  };

  const downloadTextFile = (content, filename, type) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
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
          {readOnly ? "View Question Bank" : "Question Bank"} - {job.title}
        </h1>

        {!readOnly && (
        <>

        <section className="question-note">

          <div className="instruction-header">
            <div>
              <h3>Recommended Upload Format</h3>
              <p>Use the labelled TXT format when questions or answers contain commas.</p>
            </div>
            <div className="instruction-actions">
              <button
                className="question-bank-btn"
                type="button"
                onClick={downloadSampleTxt}
              >
                Download Sample TXT
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={downloadSampleCsv}
              >
                Download Sample CSV
              </button>
            </div>
          </div>

          <div className="instruction-summary-grid">
            <InstructionCard title="Supported Formats" items={["CSV", "JSON", "TXT", "TSV"]} />
            <InstructionCard title="Required Fields" items={["Question", "Expected Answer", "Difficulty", "Area of Interest"]} />
            <InstructionCard title="Optional Fields" items={["Tags", "Job Role"]} />
            <InstructionCard title="Difficulty Values" items={["Easy", "Medium", "Hard"]} />
          </div>

          <div className="format-table-card">
            <h4>Expected Upload Format</h4>
            <div className="format-table-wrapper">
              <table className="format-table">
                <thead>
                  <tr>
                    <th>Field Name</th>
                    <th>Required</th>
                    <th>Description</th>
                    <th>Example</th>
                  </tr>
                </thead>
                <tbody>
                  {FORMAT_FIELDS.map((field) => (
                    <tr key={field.field}>
                      <td><code>{field.field}</code></td>
                      <td>
                        <span className={`requirement-badge ${field.required === "Yes" ? "required" : "optional"}`}>
                          {field.required}
                        </span>
                      </td>
                      <td>{field.description}</td>
                      <td>{field.example}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="sample-preview-grid">
            <div className="sample-preview-card">
              <h4>Labelled TXT Sample</h4>
              <pre className="sample-code"><code>{SAMPLE_TXT_PREVIEW}</code></pre>
            </div>
            <div className="sample-preview-card">
              <h4>Advanced CSV Sample</h4>
              <pre className="sample-code"><code>{SAMPLE_CSV}</code></pre>
            </div>
            <div className="sample-preview-card">
              <h4>Advanced JSON Sample</h4>
              <pre className="sample-code"><code>{SAMPLE_JSON}</code></pre>
            </div>
          </div>

          <div className="instruction-notes">
            <span>Separate each question using <code>---</code>.</span>
            <span>Difficulty can be Easy, Medium, or Hard.</span>
            <span>Tags are optional.</span>
            <span>Save the file as <code>.txt</code> and upload it.</span>
            <span>CSV, JSON, and TSV are still supported advanced formats.</span>
          </div>

        </section>

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
              accept=".txt,.csv,.tsv,.json"
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
                    value={normalizeDifficulty(item.difficulty)}
                    onChange={(e) =>
                      updateQuestion(
                        index,
                        "difficulty",
                        e.target.value
                      )
                    }
                  >
                    <option value="easy">Easy</option>
                    <option value="medium">Medium</option>
                    <option value="hard">Hard</option>
                  </select>

                  <input
                    className="question-input"
                    placeholder="Area of Interest / Topic"
                    value={item.area_of_interest || item.category || ""}
                    onChange={(e) =>
                      updateQuestion(
                        index,
                        "area_of_interest",
                        e.target.value
                      )
                    }
                  />

                  <input
                    className="question-input"
                    placeholder="Tags (comma separated)"
                    value={item.tags || ""}
                    onChange={(e) =>
                      updateQuestion(
                        index,
                        "tags",
                        e.target.value
                      )
                    }
                  />

                  <input
                    className="question-input"
                    placeholder="Job Role (optional)"
                    value={item.job_role || ""}
                    onChange={(e) =>
                      updateQuestion(
                        index,
                        "job_role",
                        e.target.value
                      )
                    }
                  />

                  <input
                    className="question-input"
                    type="number"
                    min="0.1"
                    step="0.1"
                    placeholder="Score Weight"
                    value={item.score_weight || 1}
                    onChange={(e) =>
                      updateQuestion(
                        index,
                        "score_weight",
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

        </>
        )}

        {successMessage && (

          <div className="success-message">
            {successMessage}
          </div>

        )}

        <section className="question-bank-view">
          <h2>{readOnly ? "Saved Question Bank" : "Uploaded Question Bank"}</h2>
          {isLoadingBank ? (
            <p>Loading question bank...</p>
          ) : savedQuestions.length ? (
            <>
              <div className="question-bank-filters">
                <input
                  className="question-input"
                  placeholder="Search questions, answers, tags, topics"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                />
                <select className="question-input" value={difficultyFilter} onChange={(event) => setDifficultyFilter(event.target.value)}>
                  <option value="all">All Difficulties</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
                <select className="question-input" value={areaFilter} onChange={(event) => setAreaFilter(event.target.value)}>
                  <option value="all">All Areas</option>
                  {areas.map((area) => (
                    <option value={area} key={area}>{area}</option>
                  ))}
                </select>
                {jobRoles.length > 0 && (
                  <select className="question-input" value={jobRoleFilter} onChange={(event) => setJobRoleFilter(event.target.value)}>
                    <option value="all">All Job Roles</option>
                    {jobRoles.map((role) => (
                      <option value={role} key={role}>{role}</option>
                    ))}
                  </select>
                )}
              </div>
              <div className="question-bank-toolbar">
                <button
                  className="danger-button"
                  type="button"
                  onClick={clearQuestionBank}
                >
                  Clear Question Bank
                </button>
              </div>
              <div className="question-bank-list">
                {filteredSavedQuestions.map((item, index) => (
                  <article className="question-bank-review-card" key={`${item.id || index}-${item.question}`}>
                    <div className="question-bank-review-heading">
                      <span>Question {index + 1}</span>
                      <strong>{formatDifficulty(item.difficulty)}</strong>
                    </div>
                    {editingQuestionId === getQuestionId(item) ? (
                      <div className="question-edit-form">
                        <input
                          className="question-input"
                          placeholder="Question"
                          value={editingQuestion?.question || ""}
                          onChange={(event) => updateEditingQuestion("question", event.target.value)}
                        />
                        <textarea
                          className="question-answer"
                          placeholder="Expected Answer"
                          value={editingQuestion?.expected_answer || ""}
                          onChange={(event) => updateEditingQuestion("expected_answer", event.target.value)}
                        />
                        <select
                          className="question-input"
                          value={normalizeDifficulty(editingQuestion?.difficulty)}
                          onChange={(event) => updateEditingQuestion("difficulty", event.target.value)}
                        >
                          <option value="easy">Easy</option>
                          <option value="medium">Medium</option>
                          <option value="hard">Hard</option>
                        </select>
                        <input
                          className="question-input"
                          placeholder="Area of Interest"
                          value={editingQuestion?.area_of_interest || ""}
                          onChange={(event) => updateEditingQuestion("area_of_interest", event.target.value)}
                        />
                        <input
                          className="question-input"
                          placeholder="Tags (comma separated)"
                          value={editingQuestion?.tags || ""}
                          onChange={(event) => updateEditingQuestion("tags", event.target.value)}
                        />
                        <input
                          className="question-input"
                          placeholder="Job Role"
                          value={editingQuestion?.job_role || ""}
                          onChange={(event) => updateEditingQuestion("job_role", event.target.value)}
                        />
                        <div className="question-card-actions">
                          <button className="question-bank-btn" type="button" onClick={saveEditedQuestion}>
                            Save
                          </button>
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => {
                              setEditingQuestionId("");
                              setEditingQuestion(null);
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p>{item.question}</p>
                        <div className="question-meta-row">
                          <span>{item.area_of_interest || item.areaOfInterest || item.category || "General"}</span>
                          {splitTags(item.tags).map((tag) => (
                            <span key={tag}>{tag}</span>
                          ))}
                          {(item.job_role || item.jobRole) && <span>{item.job_role || item.jobRole}</span>}
                        </div>
                        <div className="expected-answer-box">
                          <span>Expected Answer</span>
                          <p>{item.expected_answer || item.expectedAnswer || "Not provided"}</p>
                        </div>
                        <div className="question-card-actions">
                          <button className="secondary-button" type="button" onClick={() => startEditQuestion(item)}>
                            Edit
                          </button>
                          <button className="danger-button" type="button" onClick={() => deleteQuestion(item)}>
                            Delete
                          </button>
                        </div>
                      </>
                    )}
                  </article>
                ))}
                {!filteredSavedQuestions.length && <p>No questions match the selected filters.</p>}
              </div>
            </>
          ) : (
            <p>{readOnly ? "No saved question bank found." : "No question bank uploaded."}</p>
          )}
        </section>

      </div>

    </main>

  );
}

export default QuestionBankPage;


function InstructionCard({ title, items }) {
  return (
    <article className="instruction-card">
      <h4>{title}</h4>
      <div className="instruction-badges">
        {items.map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
    </article>
  );
}


function normalizeDifficulty(value) {
  const difficulty = String(value || "medium").trim().toLowerCase();
  return ["easy", "medium", "hard"].includes(difficulty) ? difficulty : "medium";
}


function formatDifficulty(value) {
  const difficulty = normalizeDifficulty(value);
  return difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
}


function getQuestionId(question) {
  return String(question?._id || question?.id || question?.question_id || "");
}


function splitTags(value) {
  if (Array.isArray(value)) {
    return value;
  }

  return String(value || "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}
