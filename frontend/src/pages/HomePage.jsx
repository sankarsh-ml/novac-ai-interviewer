import "../styles/HomePage.css";


function HomePage({ onOpenAdmin }) {
  return (
    <main className="home-page">
      <section className="home-content">
        <p className="eyebrow">Resume Text Extractor</p>
        <h1>AI Resume Screener</h1>
        <p className="subtitle">Upload resumes and prepare them for ATS screening</p>

        <div className="role-grid">
          <button className="role-card" type="button" onClick={onOpenAdmin}>
            <span className="role-letter admin">A</span>
            <span>Admin</span>
          </button>
        </div>
      </section>
    </main>
  );
}


export default HomePage;
