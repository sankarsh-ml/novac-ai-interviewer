import "@presentation/styles/HomePage.css";

function HRHomePage({
  onOpenCurrentJobs,
  onOpenAddJob,
  onBack,
}) {
  return (
    <main className="home-page">
      <section className="home-content">

        <p className="eyebrow">Admin Panel</p>

        <h1>HR Dashboard</h1>

        <p className="subtitle">
          Manage jobs and applications
        </p>

        <div className="role-grid">

          <button
            className="role-card"
            onClick={onOpenCurrentJobs}
          >
            <span className="role-letter">J</span>
            <span>Current Jobs</span>
          </button>

          <button
            className="role-card"
            onClick={onOpenAddJob}
          >
            <span className="role-letter admin">+</span>
            <span>Add Job</span>
          </button>

        </div><br></br>
          <button
          className="back-button"
          onClick={onBack}
        >
          Back
        </button>
      </section>
    </main>
  );
}

export default HRHomePage;