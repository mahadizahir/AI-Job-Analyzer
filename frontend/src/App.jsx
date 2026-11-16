
import { useEffect, useState } from "react";
import "./App.css";

function App() {
  // Job states
  const [jobs, setJobs] = useState([]);
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [visibleCount, setVisibleCount] = useState(10);

  // Resume states
  const [resumeFile, setResumeFile] = useState(null);
  const [detectedSkills, setDetectedSkills] = useState([]);
  const [recommendedJobs, setRecommendedJobs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [analysisComplete, setAnalysisComplete] = useState(false);

  // Job preference
  const [jobType, setJobType] = useState("all");
  const [analyzedJobType, setAnalyzedJobType] = useState("all");

  // Fetch available jobs from SQLite through FastAPI
  useEffect(() => {
    async function fetchJobs() {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/jobs"
        );

        if (!response.ok) {
          throw new Error("Failed to fetch jobs");
        }

        const data = await response.json();
        setJobs(data);

      } catch (err) {
        setError(err.message);

      } finally {
        setLoading(false);
      }
    }

    fetchJobs();
  }, []);

  // Search existing job titles
  const filteredJobs = jobs.filter((job) =>
    (job.job_title || "")
      .toLowerCase()
      .includes(keyword.toLowerCase())
  );

  function handleSearch(event) {
    setKeyword(event.target.value);
    setVisibleCount(10);
  }

  // Reset previous resume results
  function resetAnalysis() {
    setDetectedSkills([]);
    setRecommendedJobs([]);
    setUploadError("");
    setAnalysisComplete(false);
  }

  // Upload PDF for Groq and ML analysis
  async function handleResumeUpload() {
    if (!resumeFile) {
      setUploadError("Please select a PDF resume.");
      return;
    }

    setUploading(true);
    resetAnalysis();

    const formData = new FormData();
    formData.append("file", resumeFile);
    formData.append("job_type", jobType);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/upload-resume",
        {
          method: "POST",
          body: formData
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Resume analysis failed"
        );
      }

      setDetectedSkills(data.detected_skills || []);
      setRecommendedJobs(data.recommended_jobs || []);
      setAnalyzedJobType(data.selected_job_type || jobType);
      setAnalysisComplete(true);

    } catch (err) {
      setUploadError(err.message);

    } finally {
      setUploading(false);
    }
  }

  // Show job type labels
  function getJobTypeLabel(type) {
    if (type === "internship") {
      return "Internship";
    }

    if (type === "entry") {
      return "Entry-Level / Fresh Graduate";
    }

    if (type === "unclassified") {
      return "Unclassified";
    }

    return "All Jobs";
  }

  // Render optional application information
  function JobApplicationInfo({ job }) {
    return (
      <div style={{ marginTop: "16px" }}>
        {job.location && (
          <p>
            <strong>Location:</strong>{" "}
            {job.location}
          </p>
        )}

        {job.application_url ? (
          <div>
            {job.date_verified && (
              <p
                style={{
                  color: "#64748b",
                  fontSize: "14px"
                }}
              >
                Application link last checked:{" "}
                {job.date_verified}
              </p>
            )}

            <a
              href={job.application_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-block",
                marginTop: "8px",
                padding: "11px 18px",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                borderRadius: "8px",
                textDecoration: "none",
                fontWeight: "600"
              }}
            >
              Apply on Job Website ↗
            </a>
          </div>
        ) : (
          <p
            style={{
              color: "#64748b",
              fontSize: "14px"
            }}
          >
            Application link not yet verified.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="container">

      <h1>AI Job Recommendation System</h1>

      <p>
        Discover job opportunities that match your skills.
      </p>

      {/* Search job titles */}
      <input
        type="text"
        placeholder="Search job titles..."
        value={keyword}
        onChange={handleSearch}
      />

      {/* Resume Upload */}
      <section className="resume-section">
        <h2>AI Resume Analysis</h2>

        <p>
          Upload your PDF resume to identify technical
          skills and discover relevant jobs.
        </p>

        {/* Job Type Preference */}
        <div style={{ marginBottom: "20px" }}>
          <label
            htmlFor="job-type"
            style={{
              display: "block",
              fontWeight: "600",
              marginBottom: "8px"
            }}
          >
            Job Type Preference
          </label>

          <select
            id="job-type"
            value={jobType}
            disabled={uploading}
            onChange={(event) => {
              setJobType(event.target.value);
              resetAnalysis();
            }}
            style={{
              width: "100%",
              maxWidth: "380px",
              padding: "12px",
              border: "1px solid #cbd5e1",
              borderRadius: "8px",
              fontSize: "16px",
              backgroundColor: "#ffffff",
              color: "#1e293b"
            }}
          >
            <option value="all">
              All Jobs
            </option>

            <option value="internship">
              Internship
            </option>

            <option value="entry">
              Entry-Level / Fresh Graduate
            </option>
          </select>
        </div>

        {/* PDF File Input */}
        <input
          type="file"
          accept=".pdf,application/pdf"
          disabled={uploading}
          onChange={(event) => {
            setResumeFile(event.target.files[0] || null);
            resetAnalysis();
          }}
        />

        <button
          onClick={handleResumeUpload}
          disabled={!resumeFile || uploading}
        >
          {uploading
            ? "Analyzing Resume..."
            : "Analyze Resume"}
        </button>

        {uploadError && (
          <p className="error-message">
            {uploadError}
          </p>
        )}

        {/* Groq Detected Skills */}
        {analysisComplete && (
          <div className="resume-result">
            <h3>AI-Detected Technical Skills</h3>

            {detectedSkills.length > 0 ? (
              <div className="skills-list">
                {detectedSkills.map((skill) => (
                  <span
                    className="skill-tag"
                    key={skill}
                  >
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p>No technical skills detected.</p>
            )}
          </div>
        )}
      </section>

      {/* AI Job Recommendations */}
      {analysisComplete && (
        <section className="recommendations-section">

          <h2>Top AI Job Recommendations</h2>

          <p>
            Selected preference:{" "}
            <strong>
              {getJobTypeLabel(analyzedJobType)}
            </strong>
          </p>

          <p>
            Jobs ranked by semantic similarity to your
            detected skills. Scores are not hiring
            probabilities. Vacancy availability is
            not automatically verified.
          </p>

          {recommendedJobs.length > 0 ? (
            recommendedJobs.map((job, index) => (
              <div
                className="recommendation-card"
                key={`${job.company_name}-${job.job_title}-${index}`}
              >
                <h3>
                  #{index + 1} - {job.job_title}
                </h3>

                <p>
                  <strong>Company:</strong>{" "}
                  {job.company_name}
                </p>

                <p>
                  <strong>Job Type:</strong>{" "}
                  {getJobTypeLabel(job.job_type)}
                </p>

                <p>
                  <strong>Similarity Score:</strong>{" "}
                  {Number(job.similarity_score).toFixed(4)}
                </p>

                {/* Matching Skills */}
                <p>
                  <strong>Matching Skills:</strong>
                </p>

                {job.matched_skills?.length > 0 ? (
                  <div className="matching-skills">
                    {job.matched_skills.map((skill) => (
                      <span
                        className="matching-skill-tag"
                        key={skill}
                      >
                        ✓ {skill}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="no-matching-skills">
                    No exact skill-name matches found.
                  </p>
                )}

                {/* Groq Explanation */}
                {job.explanation && (
                  <div>
                    <p>
                      <strong>
                        Why This Job May Match:
                      </strong>
                    </p>

                    <p>{job.explanation}</p>
                  </div>
                )}

                {/* Application link and location */}
                <JobApplicationInfo job={job} />
              </div>
            ))
          ) : (
            <p>
              No jobs were identified for this preference.
              Try All Jobs or another category.
            </p>
          )}
        </section>
      )}

      {/* All Available Jobs */}
      {loading && <p>Loading jobs...</p>}

      {error && (
        <p className="error-message">
          Error: {error}
        </p>
      )}

      {!loading && !error && (
        <div className="jobs-list">

          <h2>
            Available Jobs ({filteredJobs.length})
          </h2>

          {filteredJobs
            .slice(0, visibleCount)
            .map((job) => (
              <div
                className="job-card"
                key={job.id}
              >
                <h3>{job.job_title}</h3>

                <p>
                  <strong>Company:</strong>{" "}
                  {job.company_name}
                </p>

                <p>
                  {(job.description || "").length > 200
                    ? job.description.slice(0, 200) + "..."
                    : job.description}
                </p>

                <JobApplicationInfo job={job} />
              </div>
            ))}

          {filteredJobs.length === 0 && (
            <p>No matching jobs found.</p>
          )}

          {/* Load More */}
          {visibleCount < filteredJobs.length && (
            <button
              className="load-more-btn"
              onClick={() =>
                setVisibleCount(
                  (previous) => previous + 10
                )
              }
            >
              Load More Jobs
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
