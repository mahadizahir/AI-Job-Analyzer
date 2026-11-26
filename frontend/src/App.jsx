import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

/* ==========================================
   DATA NORMALIZATION & CLASSIFICATION HELPERS
   ========================================== */

function normalizeLocation(location) {
  if (!location) {
    return "";
  }

  const expanded = location.trim().replace(/,\s*MY$/i, ", Malaysia");
  const parts = expanded
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);

  const uniqueParts = [];
  for (const part of parts) {
    if (
      uniqueParts.length === 0 ||
      uniqueParts[uniqueParts.length - 1].toLowerCase() !== part.toLowerCase()
    ) {
      uniqueParts.push(part);
    }
  }

  return uniqueParts.join(", ");
}

function normalizeUrl(url) {
  if (!url) {
    return "";
  }

  return url.trim().replace(/\/+$/, "").toLowerCase();
}

function getPostingSourceLabel(posting, targetUrl, index) {
  if (posting.posting_source) {
    return posting.posting_source;
  }

  if (targetUrl) {
    try {
      const hostname = new URL(targetUrl).hostname.replace(/^www\./, "");
      if (hostname) {
        return hostname;
      }
    } catch {
      // Fallback below
    }
  }

  return `Source #${index + 1}`;
}

function classifyRoleType(jobTitle) {
  const title = (jobTitle || "").toLowerCase();

  if (/\b(internship|intern|industrial training)\b/.test(title)) {
    return "internship";
  }

  if (/\b(senior|sr\.?|lead|principal|staff|manager|head|director)\b/.test(title)) {
    return "experienced";
  }

  if (/\b(junior|jr\.?|entry[\s-]?level|fresh[\s-]?graduate|freshers?|graduate|trainee)\b/.test(title)) {
    return "entry";
  }

  return "general";
}

function getRoleTypeBadge(type) {
  if (type === "internship") {
    return { label: "Internship", className: "badge badge-blue" };
  }
  if (type === "entry") {
    return { label: "Entry-Level / Grad", className: "badge badge-green" };
  }
  if (type === "experienced") {
    return { label: "Mid / Senior", className: "badge" };
  }
  return { label: "Standard Role", className: "badge" };
}

function getDeduplicatedPostings(job) {
  const rawPostings = (job.postings || []).filter(
    (posting) => posting.application_url || posting.posting_url
  );

  const uniqueMap = new Map();

  for (const posting of rawPostings) {
    const targetUrl = posting.application_url || posting.posting_url;
    const key = normalizeUrl(targetUrl);

    if (!uniqueMap.has(key)) {
      uniqueMap.set(key, posting);
    } else {
      const existing = uniqueMap.get(key);
      if (!existing.api_posting_id && posting.api_posting_id) {
        uniqueMap.set(key, posting);
      }
    }
  }

  if (uniqueMap.size > 0) {
    return Array.from(uniqueMap.values());
  }

  if (job.application_url) {
    return [
      {
        id: `legacy-${job.id}`,
        application_url: job.application_url,
        location: job.location,
        latest_checked_at: job.date_verified
      }
    ];
  }

  return [];
}

function getUniqueLocations(job, postings) {
  return Array.from(
    new Set(
      [
        ...postings.map((p) => normalizeLocation(p.location)),
        normalizeLocation(job.location)
      ].filter(Boolean)
    )
  );
}

function getFreshnessDate(job, postings) {
  const candidates = [];

  for (const p of postings) {
    if (p.source_posted_at) candidates.push(p.source_posted_at.slice(0, 10));
    else if (p.first_seen_at) candidates.push(p.first_seen_at.slice(0, 10));
    else if (p.latest_checked_at) candidates.push(p.latest_checked_at.slice(0, 10));
  }

  if (job.date_verified) {
    candidates.push(job.date_verified.slice(0, 10));
  }

  if (candidates.length === 0) {
    return "";
  }

  return candidates.sort().reverse()[0];
}

function toPercent(score) {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(score * 100)));
}

function getTierBadge(score) {
  const pct = toPercent(score);
  if (pct >= 65) {
    return { label: "Strong Match", className: "badge badge-green" };
  }
  return { label: "Good Match", className: "badge badge-blue" };
}

function formatRationaleText(explanation, jobTitle, companyName) {
  if (!explanation) return "";

  let cleaned = explanation.trim();

  if (jobTitle) {
    const escapedTitle = jobTitle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    cleaned = cleaned.replace(
      new RegExp(`\\s*(?:for|to|of)\\s+${escapedTitle}`, "gi"),
      ""
    );
  }

  if (companyName) {
    const escapedCompany = companyName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    cleaned = cleaned.replace(
      new RegExp(`\\s*(?:at|with|for)\\s+${escapedCompany}`, "gi"),
      ""
    );
  }

  cleaned = cleaned
    .replace(/\s+([.,;:])/g, "$1")
    .replace(/\s{2,}/g, " ")
    .trim();

  return cleaned;
}

/* ==========================================
   MINIMALIST SVG ICONS (1.75px STROKE)
   ========================================== */

function Icon({ name, size = 16 }) {
  const props = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.75",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  };

  switch (name) {
    case "logo":
      return (
        <svg {...props}>
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M2 12l10 5 10-5" />
        </svg>
      );
    case "dashboard":
      return (
        <svg {...props}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "file":
      return (
        <svg {...props}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
        </svg>
      );
    case "sparkles":
      return (
        <svg {...props}>
          <path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3z" />
        </svg>
      );
    case "briefcase":
      return (
        <svg {...props}>
          <rect x="2" y="7" width="20" height="14" rx="2" />
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
        </svg>
      );
    case "upload":
      return (
        <svg {...props}>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
      );
    case "search":
      return (
        <svg {...props}>
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      );
    case "menu":
      return (
        <svg {...props}>
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      );
    case "external":
      return (
        <svg {...props}>
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
          <polyline points="15 3 21 3 21 9" />
          <line x1="10" y1="14" x2="21" y2="3" />
        </svg>
      );
    case "check":
      return (
        <svg {...props}>
          <polyline points="20 6 9 17 4 12" />
        </svg>
      );
    default:
      return null;
  }
}

/* ==========================================
   REFINED JOB RECOMMENDATION CARD COMPONENT
   ========================================== */

function JobCard({
  job,
  rank = null,
  onGenerateExplanation = null,
  isGeneratingExplanation = false
}) {
  const postings = useMemo(() => getDeduplicatedPostings(job), [job]);
  const locations = useMemo(
    () => getUniqueLocations(job, postings),
    [job, postings]
  );
  const freshness = useMemo(
    () => getFreshnessDate(job, postings),
    [job, postings]
  );

  const inferredType =
    job.job_type && job.job_type !== "unclassified"
      ? job.job_type
      : classifyRoleType(job.job_title);
  const roleBadge = getRoleTypeBadge(inferredType);

  const workItems = (job.work_description || "")
    .split("\n")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);

  const hasScore = typeof job.similarity_score === "number";
  const matchPercent = hasScore ? toPercent(job.similarity_score) : null;
  const tierBadge = hasScore ? getTierBadge(job.similarity_score) : null;

  const hasBreakdown =
    typeof job.semantic_score === "number" &&
    typeof job.skill_overlap_score === "number";

  const contextPercent = hasBreakdown ? toPercent(job.semantic_score) : null;
  const skillsPercent = hasBreakdown
    ? toPercent(job.skill_overlap_score)
    : null;

  const scoreTooltip = hasBreakdown
    ? `Overall Match: ${matchPercent}% (75% Role Context: ${contextPercent}% + 25% Skill Overlap: ${skillsPercent}%)`
    : "Overall match score";

  const displayRationale = useMemo(
    () =>
      formatRationaleText(job.explanation, job.job_title, job.company_name),
    [job.explanation, job.job_title, job.company_name]
  );

  return (
    <article className="job-card">
      {/* 1. Job Header & 2. Match Score */}
      <div className="job-card-header">
        <div className="job-card-identity">
          <div className="job-title-row">
            {rank !== null && <span className="job-rank-tag">#{rank}</span>}
            <h3 className="job-title">{job.job_title}</h3>
          </div>

          <div className="job-meta-row">
            <span className="job-company">{job.company_name}</span>

            {locations.length > 0 && (
              <>
                <span className="meta-divider" aria-hidden="true">·</span>
                <span className="job-meta-item">{locations.join(", ")}</span>
              </>
            )}

            <span className="meta-divider" aria-hidden="true">·</span>
            <span className={roleBadge.className}>{roleBadge.label}</span>

            {tierBadge && (
              <>
                <span className="meta-divider" aria-hidden="true">·</span>
                <span className={tierBadge.className}>{tierBadge.label}</span>
              </>
            )}

            {freshness && (
              <>
                <span className="meta-divider" aria-hidden="true">·</span>
                <span className="job-meta-muted">Updated {freshness}</span>
              </>
            )}
          </div>
        </div>

        {hasScore && (
          <aside className="score-box" title={scoreTooltip} aria-label={scoreTooltip}>
            <div className="score-box-top">
              <span className="score-box-label">Match Score</span>
              <span className="score-box-value">{matchPercent}%</span>
            </div>
            <div className="score-progress-track">
              <div
                className="score-progress-fill"
                style={{ width: `${matchPercent}%` }}
              />
            </div>
            {hasBreakdown && (
              <div className="score-box-meta">
                <span>Context {contextPercent}%</span>
                <span aria-hidden="true">·</span>
                <span>Skills {skillsPercent}%</span>
              </div>
            )}
          </aside>
        )}
      </div>

      {/* 3. Skills Section */}
      {(Array.isArray(job.matched_skills) ||
        Array.isArray(job.missing_skills)) && (
        <div className="job-skills-grid">
          <div className="job-skills-col">
            <div className="job-section-label">Matched skills</div>
            {job.matched_skills?.length > 0 ? (
              <div className="skills-wrap">
                {job.matched_skills.map((skill) => (
                  <span className="skill-chip matched" key={skill}>
                    <Icon name="check" size={12} />
                    <span>{skill}</span>
                  </span>
                ))}
              </div>
            ) : (
              <span className="job-empty-hint">
                Aligned through broader role context
              </span>
            )}
          </div>

          <div className="job-skills-col">
            <div className="job-section-label">Skills to highlight or build</div>
            {job.missing_skills?.length > 0 ? (
              <div className="skills-wrap">
                {job.missing_skills.map((skill) => (
                  <span className="skill-chip missing" key={skill}>
                    <span className="skill-plus" aria-hidden="true">+</span>
                    <span>{skill}</span>
                  </span>
                ))}
              </div>
            ) : (
              <span className="job-empty-hint">
                No missing technical skills detected
              </span>
            )}
          </div>
        </div>
      )}

      {/* 4. AI Match Rationale */}
      {displayRationale ? (
        <div className="ai-rationale">
          <div className="ai-rationale-header">
            <Icon name="sparkles" size={13} />
            <span>AI Match Rationale</span>
          </div>
          <p className="ai-rationale-body">{displayRationale}</p>
        </div>
      ) : (
        hasScore &&
        onGenerateExplanation && (
          <div className="ai-rationale-action">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={isGeneratingExplanation}
              onClick={() => onGenerateExplanation(job)}
            >
              <Icon name="sparkles" size={13} />
              {isGeneratingExplanation
                ? "Generating rationale..."
                : "Generate AI Rationale"}
            </button>
          </div>
        )
      )}

      {/* Structured Responsibilities & 5. Job Description Accordion */}
      {(workItems.length > 0 || job.description) && (
        <div className="job-details-group">
          {workItems.length > 0 && (
            <div className="job-responsibilities">
              <div className="job-section-label">Key responsibilities</div>
              <ul className="work-list">
                {workItems.map((item, idx) => (
                  <li key={idx}>{item.replace(/^[-•*]\s*/, "")}</li>
                ))}
              </ul>
            </div>
          )}

          {job.description && (
            <details className="job-accordion">
              <summary className="job-accordion-trigger">
                <span>Full job description</span>
                <span className="job-accordion-chevron" aria-hidden="true">
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </span>
              </summary>
              <div className="job-accordion-panel">{job.description}</div>
            </details>
          )}
        </div>
      )}

      {/* 6. Compact Application Section */}
      <div className="job-apply-section">
        <div className="job-section-label">
          {postings.length > 1
            ? `Application channels (${postings.length})`
            : "Application channel"}
        </div>

        {postings.length > 0 ? (
          <div className="posting-list">
            {postings.map((posting, idx) => {
              const targetUrl =
                posting.application_url || posting.posting_url;
              const sourceLabel = getPostingSourceLabel(
                posting,
                targetUrl,
                idx
              );
              const cleanLoc = normalizeLocation(posting.location);
              const checkedDate = posting.latest_checked_at
                ? posting.latest_checked_at.slice(0, 10)
                : "";
              const isUnavailable =
                posting.latest_check_result === "closed" ||
                posting.latest_check_result === "broken";

              return (
                <div
                  className="posting-row"
                  key={posting.id ?? `${job.id}-posting-${idx}`}
                >
                  <div className="posting-meta">
                    <div className="posting-source-line">
                      <span className="posting-source">{sourceLabel}</span>
                      {locations.length > 1 && cleanLoc && (
                        <span className="posting-location">· {cleanLoc}</span>
                      )}
                    </div>

                    {(posting.latest_check_result || checkedDate) && (
                      <div
                        className={`posting-status ${
                          isUnavailable ? "unavailable" : ""
                        }`}
                      >
                        {posting.latest_check_result === "available" &&
                          "Verified active"}
                        {isUnavailable &&
                          `Status: ${posting.latest_check_result}`}
                        {checkedDate &&
                          `${
                            posting.latest_check_result ? " · " : ""
                          }Checked ${checkedDate}`}
                      </div>
                    )}
                  </div>

                  <a
                    href={targetUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`btn btn-sm job-apply-btn ${
                      isUnavailable ? "btn-secondary" : "btn-primary"
                    }`}
                  >
                    <span>Apply Now</span>
                    <Icon name="external" size={13} />
                  </a>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="posting-unverified">
            Direct application link has not been verified for this listing yet.
          </div>
        )}
      </div>
    </article>
  );
}

/* ==========================================
   MAIN APPLICATION
   ========================================== */

function App() {
  const [activeNav, setActiveNav] = useState("overview");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [jobs, setJobs] = useState([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [jobsError, setJobsError] = useState("");

  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [locationFilter, setLocationFilter] = useState("all");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [sortBy, setSortBy] = useState("newest");
  const [visibleCount, setVisibleCount] = useState(12);

  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [resumeFile, setResumeFile] = useState(null);
  const [jobTypePref, setJobTypePref] = useState("all");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [analysisResult, setAnalysisResult] = useState(null);
  const [tierFilter, setTierFilter] = useState("all");
  const [explainingJobId, setExplainingJobId] = useState(null);

  useEffect(() => {
    let active = true;

    async function loadJobs() {
      try {
        const res = await fetch(`${API_BASE}/jobs`);
        if (!res.ok) {
          throw new Error("Unable to load job listings from backend.");
        }
        const data = await res.json();
        if (active) {
          setJobs(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        if (active) {
          setJobsError(err.message);
        }
      } finally {
        if (active) {
          setLoadingJobs(false);
        }
      }
    }

    loadJobs();
    return () => {
      active = false;
    };
  }, []);

  const stats = useMemo(() => {
    let totalLinks = 0;
    let internshipCount = 0;
    let entryCount = 0;
    const locationCounts = new Map();

    for (const job of jobs) {
      const postings = getDeduplicatedPostings(job);
      totalLinks += postings.length;

      const roleType = classifyRoleType(job.job_title);
      if (roleType === "internship") internshipCount += 1;
      if (roleType === "entry") entryCount += 1;

      const locs = getUniqueLocations(job, postings);
      for (const loc of locs) {
        const region = loc.split(",")[0].trim();
        if (region) {
          locationCounts.set(region, (locationCounts.get(region) || 0) + 1);
        }
      }
    }

    const topLocations = Array.from(locationCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);

    const allLocations = Array.from(locationCounts.keys()).sort();

    return {
      totalJobs: jobs.length,
      totalLinks,
      internshipCount,
      entryCount,
      topLocations,
      allLocations
    };
  }, [jobs]);

  const matchedSkillSet = useMemo(() => {
    const set = new Set();
    if (!analysisResult?.recommendedJobs) return set;

    for (const job of analysisResult.recommendedJobs) {
      for (const skill of job.matched_skills || []) {
        set.add(skill.toLowerCase());
      }
    }
    return set;
  }, [analysisResult]);

  const recommendationTiers = useMemo(() => {
    const list = analysisResult?.recommendedJobs || [];
    const strong = list.filter((j) => toPercent(j.similarity_score) >= 65);
    const good = list.filter((j) => toPercent(j.similarity_score) < 65);

    const visible =
      tierFilter === "strong"
        ? strong
        : tierFilter === "good"
        ? good
        : list;

    return {
      allCount: list.length,
      strongCount: strong.length,
      goodCount: good.length,
      visible
    };
  }, [analysisResult, tierFilter]);

  const filteredJobs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();

    const list = jobs.filter((job) => {
      const postings = getDeduplicatedPostings(job);

      if (verifiedOnly && postings.length === 0) {
        return false;
      }

      if (roleFilter !== "all") {
        if (classifyRoleType(job.job_title) !== roleFilter) {
          return false;
        }
      }

      if (locationFilter !== "all") {
        const locs = getUniqueLocations(job, postings).join(" ").toLowerCase();
        if (!locs.includes(locationFilter.toLowerCase())) {
          return false;
        }
      }

      if (q) {
        const haystack = [
          job.job_title,
          job.company_name,
          ...getUniqueLocations(job, postings)
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();

        if (!haystack.includes(q)) {
          return false;
        }
      }

      return true;
    });

    if (sortBy === "company") {
      return [...list].sort((a, b) =>
        (a.company_name || "").localeCompare(b.company_name || "")
      );
    }

    if (sortBy === "links") {
      return [...list].sort(
        (a, b) =>
          getDeduplicatedPostings(b).length - getDeduplicatedPostings(a).length
      );
    }

    return [...list].sort((a, b) => (b.id || 0) - (a.id || 0));
  }, [jobs, searchQuery, roleFilter, locationFilter, verifiedOnly, sortBy]);

  function handleFileSelection(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Only PDF resumes (.pdf) are supported.");
      return;
    }
    setResumeFile(file);
    setUploadError("");
  }

  async function handleAnalyzeResume() {
    if (!resumeFile) {
      setUploadError("Please select a PDF resume first.");
      return;
    }

    setUploading(true);
    setUploadError("");
    setTierFilter("all");

    const formData = new FormData();
    formData.append("file", resumeFile);
    formData.append("job_type", jobTypePref);

    try {
      const res = await fetch(`${API_BASE}/upload-resume`, {
        method: "POST",
        body: formData
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Resume analysis failed.");
      }

      setAnalysisResult({
        filename: data.filename || resumeFile.name,
        totalPages: data.total_pages || 1,
        selectedJobType: data.selected_job_type || jobTypePref,
        detectedSkills: data.detected_skills || [],
        recommendedJobs: data.recommended_jobs || []
      });
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleGenerateExplanation(targetJob) {
    if (!analysisResult || explainingJobId !== null) return;

    setExplainingJobId(targetJob.id);

    try {
      const res = await fetch(`${API_BASE}/explain-match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          detected_skills: analysisResult.detectedSkills,
          job_title: targetJob.job_title,
          company_name: targetJob.company_name,
          description: targetJob.description || "",
          matched_skills: targetJob.matched_skills || []
        })
      });

      const data = await res.json();

      if (res.ok && data.explanation) {
        setAnalysisResult((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            recommendedJobs: prev.recommendedJobs.map((j) =>
              j.id === targetJob.id
                ? { ...j, explanation: data.explanation }
                : j
            )
          };
        });
      }
    } catch {
      // Silently ignore transient rationale errors
    } finally {
      setExplainingJobId(null);
    }
  }

  function navigateTo(view) {
    setActiveNav(view);
    setMobileMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const navItems = [
    { id: "overview", label: "Overview", icon: "dashboard" },
    {
      id: "analyzer",
      label: "Resume Analyzer",
      icon: "file",
      badge: analysisResult ? analysisResult.recommendedJobs.length : null
    },
    {
      id: "jobs",
      label: "Job Explorer",
      icon: "briefcase",
      badge: stats.totalJobs > 0 ? stats.totalJobs : null
    }
  ];

  const currentNavTitle =
    navItems.find((item) => item.id === activeNav)?.label || "Overview";

  return (
    <div className="app-shell">
      {mobileMenuOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      <aside className={`sidebar ${mobileMenuOpen ? "open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-mark">
            <Icon name="logo" size={16} />
          </div>
          <div className="brand-text">
            <span className="brand-title">CareerLens AI</span>
            <span className="brand-subtitle">Malaysian Tech Discovery</span>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-label">Workspace</div>
          <nav className="nav-list">
            {navItems.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`nav-item ${activeNav === item.id ? "active" : ""}`}
                onClick={() => navigateTo(item.id)}
              >
                <span className="nav-item-left">
                  <Icon name={item.icon} size={16} />
                  <span>{item.label}</span>
                </span>
                {item.badge !== null && item.badge !== undefined && (
                  <span className="nav-badge">{item.badge}</span>
                )}
              </button>
            ))}
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className="resume-mini-card">
            <div className="resume-mini-label">Active Resume</div>
            {analysisResult ? (
              <>
                <div
                  className="resume-mini-value"
                  title={analysisResult.filename}
                >
                  {analysisResult.filename}
                </div>
                <div className="resume-mini-meta">
                  {analysisResult.detectedSkills.length} skills extracted ·{" "}
                  {analysisResult.totalPages}p
                </div>
              </>
            ) : (
              <>
                <div className="resume-mini-value">No resume analyzed</div>
                <div className="resume-mini-meta">
                  Upload a PDF to unlock matches
                </div>
              </>
            )}
          </div>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="mobile-menu-btn"
              aria-label="Open navigation"
              onClick={() => setMobileMenuOpen(true)}
            >
              <Icon name="menu" size={17} />
            </button>

            <div className="topbar-breadcrumb">
              <span className="breadcrumb-root">AI Job Analyzer</span>
              <span className="breadcrumb-sep">/</span>
              <span className="breadcrumb-current">{currentNavTitle}</span>
            </div>
          </div>

          <div className="topbar-right">
            <span className="status-pill">
              <span
                className={`status-dot ${analysisResult ? "ready" : ""}`}
              />
              {analysisResult
                ? `${analysisResult.detectedSkills.length} Skills Indexed`
                : "Awaiting Resume"}
            </span>

            {activeNav !== "analyzer" && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => navigateTo("analyzer")}
              >
                <Icon name="upload" size={14} />
                {analysisResult ? "Re-analyze Resume" : "Upload Resume"}
              </button>
            )}
          </div>
        </header>

        <main className="page-content">
          {jobsError && (
            <div className="alert-error" style={{ marginBottom: "20px" }}>
              Backend connection error: {jobsError}
            </div>
          )}

          {activeNav === "overview" && (
            <div>
              <div className="page-header">
                <div>
                  <h1 className="page-title">Career Discovery Overview</h1>
                  <p className="page-description">
                    Real-time snapshot of indexed Malaysian IT roles, verified
                    application channels, and your resume match readiness.
                  </p>
                </div>
                <div style={{ display: "flex", gap: "10px" }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => navigateTo("jobs")}
                  >
                    Browse All Roles
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => navigateTo("analyzer")}
                  >
                    Analyze Resume
                  </button>
                </div>
              </div>

              <div className="kpi-grid">
                <div className="kpi-card">
                  <div className="kpi-top">
                    <span>Indexed IT Roles</span>
                    <Icon name="briefcase" size={15} />
                  </div>
                  <div className="kpi-value">
                    {loadingJobs ? "—" : stats.totalJobs}
                  </div>
                  <div className="kpi-footnote">
                    Curated Malaysian tech positions
                  </div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-top">
                    <span>Application Channels</span>
                    <Icon name="external" size={15} />
                  </div>
                  <div className="kpi-value">
                    {loadingJobs ? "—" : stats.totalLinks}
                  </div>
                  <div className="kpi-footnote">
                    Direct career portals & job boards
                  </div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-top">
                    <span>Internship & Grad Roles</span>
                    <Icon name="sparkles" size={15} />
                  </div>
                  <div className="kpi-value">
                    {loadingJobs
                      ? "—"
                      : stats.internshipCount + stats.entryCount}
                  </div>
                  <div className="kpi-footnote">
                    {stats.internshipCount} internships · {stats.entryCount}{" "}
                    entry-level
                  </div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-top">
                    <span>Extracted Resume Skills</span>
                    <Icon name="file" size={15} />
                  </div>
                  <div className="kpi-value">
                    {analysisResult
                      ? analysisResult.detectedSkills.length
                      : 0}
                  </div>
                  <div className="kpi-footnote">
                    {analysisResult
                      ? `From ${analysisResult.filename}`
                      : "Upload PDF to extract skills"}
                  </div>
                </div>
              </div>

              <div className="dashboard-grid">
                <div className="card">
                  <div className="card-header">
                    <div>
                      <h2 className="card-title">
                        {analysisResult
                          ? "Qualified AI Recommendations"
                          : "Recently Indexed Roles"}
                      </h2>
                      <p className="card-subtitle">
                        {analysisResult
                          ? `${analysisResult.recommendedJobs.length} roles matched above 50% threshold`
                          : "Latest software, AI, and engineering openings in SQLite"}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() =>
                        navigateTo(analysisResult ? "analyzer" : "jobs")
                      }
                    >
                      View all
                    </button>
                  </div>

                  {loadingJobs ? (
                    <div className="job-stack">
                      {[1, 2, 3].map((n) => (
                        <div
                          key={n}
                          className="skeleton"
                          style={{ height: "78px" }}
                        />
                      ))}
                    </div>
                  ) : analysisResult ? (
                    <div className="job-stack">
                      {analysisResult.recommendedJobs
                        .slice(0, 3)
                        .map((job, idx) => (
                          <div
                            key={job.id ?? idx}
                            className="posting-row"
                            style={{ backgroundColor: "var(--bg-surface)" }}
                          >
                            <div className="posting-meta">
                              <div className="posting-source">
                                #{idx + 1} · {job.job_title}
                              </div>
                              <div className="posting-status">
                                {job.company_name} ·{" "}
                                {toPercent(job.similarity_score)}% Match ·{" "}
                                {job.matched_skills?.length || 0} matched skills
                              </div>
                            </div>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => navigateTo("analyzer")}
                            >
                              Inspect
                            </button>
                          </div>
                        ))}
                    </div>
                  ) : (
                    <div className="job-stack">
                      {[...jobs]
                        .sort((a, b) => (b.id || 0) - (a.id || 0))
                        .slice(0, 4)
                        .map((job) => {
                          const postings = getDeduplicatedPostings(job);
                          const locs = getUniqueLocations(job, postings);
                          return (
                            <div
                              key={job.id}
                              className="posting-row"
                              style={{ backgroundColor: "var(--bg-surface)" }}
                            >
                              <div className="posting-meta">
                                <div className="posting-source">
                                  {job.job_title}
                                </div>
                                <div className="posting-status">
                                  {job.company_name}
                                  {locs[0] ? ` · ${locs[0]}` : ""}
                                </div>
                              </div>
                              <span className="badge">
                                {postings.length}{" "}
                                {postings.length === 1 ? "link" : "links"}
                              </span>
                            </div>
                          );
                        })}
                    </div>
                  )}
                </div>

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "20px"
                  }}
                >
                  <div className="card">
                    <div className="card-header">
                      <div>
                        <h2 className="card-title">Resume Profile Status</h2>
                        <p className="card-subtitle">
                          AI skill extraction + role matching
                        </p>
                      </div>
                    </div>

                    {analysisResult ? (
                      <div>
                        <p
                          style={{
                            margin: "0 0 12px",
                            fontSize: "13px",
                            color: "var(--text-secondary)"
                          }}
                        >
                          Analyzed <strong>{analysisResult.filename}</strong> (
                          {analysisResult.totalPages} pages) and detected{" "}
                          <strong>
                            {analysisResult.detectedSkills.length} technical
                            skills
                          </strong>
                          .
                        </p>
                        <div
                          className="skills-wrap"
                          style={{ marginBottom: "14px" }}
                        >
                          {analysisResult.detectedSkills
                            .slice(0, 10)
                            .map((skill) => (
                              <span
                                key={skill}
                                className={`skill-chip ${
                                  matchedSkillSet.has(skill.toLowerCase())
                                    ? "matched"
                                    : ""
                                }`}
                              >
                                {skill}
                              </span>
                            ))}
                          {analysisResult.detectedSkills.length > 10 && (
                            <span className="skill-chip">
                              +{analysisResult.detectedSkills.length - 10} more
                            </span>
                          )}
                        </div>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => navigateTo("analyzer")}
                        >
                          View All {analysisResult.recommendedJobs.length}{" "}
                          Qualified Matches
                        </button>
                      </div>
                    ) : (
                      <div>
                        <p
                          style={{
                            margin: "0 0 14px",
                            fontSize: "13px",
                            color: "var(--text-secondary)"
                          }}
                        >
                          Upload your PDF resume to extract your programming
                          languages, frameworks, and tools, then rank the best
                          matching roles.
                        </p>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => navigateTo("analyzer")}
                        >
                          <Icon name="upload" size={14} />
                          Upload PDF Resume
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="card">
                    <div className="card-header">
                      <div>
                        <h2 className="card-title">Top Hiring Locations</h2>
                        <p className="card-subtitle">
                          Distribution across indexed postings
                        </p>
                      </div>
                    </div>

                    {stats.topLocations.length > 0 ? (
                      <div className="hub-list">
                        {stats.topLocations.map(([city, count]) => {
                          const pct =
                            stats.totalJobs > 0
                              ? Math.round((count / stats.totalJobs) * 100)
                              : 0;
                          return (
                            <div className="hub-row" key={city}>
                              <div className="hub-row-header">
                                <span className="hub-name">{city}</span>
                                <span className="hub-count">{count} roles</span>
                              </div>
                              <div className="progress-track">
                                <div
                                  className="progress-fill"
                                  style={{ width: `${Math.max(8, pct)}%` }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p
                        style={{
                          margin: 0,
                          fontSize: "13px",
                          color: "var(--text-muted)"
                        }}
                      >
                        Location metadata will appear once jobs finish loading.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeNav === "analyzer" && (
            <div>
              <div className="page-header">
                <div>
                  <h1 className="page-title">AI Resume Analysis</h1>
                  <p className="page-description">
                    Extract technical competencies from your PDF resume and
                    surface all roles scoring 50% or higher across role context
                    and tech stack.
                  </p>
                </div>
              </div>

              <div className="analyzer-grid">
                <div className="card">
                  <div className="card-header">
                    <div>
                      <h2 className="card-title">Upload Resume PDF</h2>
                      <p className="card-subtitle">
                        Supports text-based PDF files up to 10 pages
                      </p>
                    </div>
                  </div>

                  <div
                    className={`dropzone ${isDragging ? "dragging" : ""}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDragging(true);
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDragging(false);
                      handleFileSelection(e.dataTransfer.files?.[0]);
                    }}
                  >
                    <div className="dropzone-icon">
                      <Icon name="upload" size={18} />
                    </div>
                    <div className="dropzone-title">
                      Click to choose a PDF or drag and drop
                    </div>
                    <div className="dropzone-hint">
                      Your resume is parsed locally and analyzed via Groq +
                      Sentence Transformers
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,application/pdf"
                      style={{ display: "none" }}
                      disabled={uploading}
                      onChange={(e) => handleFileSelection(e.target.files?.[0])}
                    />
                  </div>

                  {resumeFile && (
                    <div className="selected-file-bar">
                      <div style={{ minWidth: 0 }}>
                        <div
                          style={{
                            fontWeight: 600,
                            fontSize: "13px",
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis"
                          }}
                        >
                          {resumeFile.name}
                        </div>
                        <div
                          style={{
                            fontSize: "12px",
                            color: "var(--text-muted)"
                          }}
                        >
                          {(resumeFile.size / 1024).toFixed(1)} KB · Ready for
                          analysis
                        </div>
                      </div>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={uploading}
                        onClick={() => {
                          setResumeFile(null);
                          if (fileInputRef.current) {
                            fileInputRef.current.value = "";
                          }
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  )}

                  <div style={{ marginTop: "16px" }}>
                    <label
                      htmlFor="role-pref-select"
                      style={{
                        display: "block",
                        fontSize: "13px",
                        fontWeight: 600,
                        marginBottom: "6px"
                      }}
                    >
                      Target Role Preference
                    </label>
                    <select
                      id="role-pref-select"
                      className="select"
                      value={jobTypePref}
                      disabled={uploading}
                      onChange={(e) => setJobTypePref(e.target.value)}
                    >
                      <option value="all">All Roles</option>
                      <option value="internship">
                        Internship / Industrial Training
                      </option>
                      <option value="entry">
                        Entry-Level / Fresh Graduate
                      </option>
                    </select>
                  </div>

                  <div style={{ marginTop: "16px" }}>
                    <button
                      type="button"
                      className="btn btn-primary"
                      style={{ width: "100%", height: "40px" }}
                      disabled={!resumeFile || uploading}
                      onClick={handleAnalyzeResume}
                    >
                      {uploading
                        ? "Extracting Skills & Matching Roles..."
                        : "Run AI Resume Analysis"}
                    </button>
                  </div>

                  {uploadError && (
                    <div className="alert-error">{uploadError}</div>
                  )}
                </div>

                <div className="card">
                  <div className="card-header">
                    <div>
                      <h2 className="card-title">Extracted Technical Profile</h2>
                      <p className="card-subtitle">
                        {analysisResult
                          ? `${analysisResult.detectedSkills.length} skills identified from ${analysisResult.filename}`
                          : "Skills detected by AI will appear here"}
                      </p>
                    </div>
                    {analysisResult && (
                      <span className="badge badge-green">
                        {analysisResult.totalPages}{" "}
                        {analysisResult.totalPages === 1 ? "Page" : "Pages"}
                      </span>
                    )}
                  </div>

                  {uploading ? (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "10px"
                      }}
                    >
                      <div
                        className="skeleton"
                        style={{ height: "20px", width: "60%" }}
                      />
                      <div className="skeleton" style={{ height: "90px" }} />
                      <div
                        className="skeleton"
                        style={{ height: "36px", width: "45%" }}
                      />
                    </div>
                  ) : analysisResult ? (
                    <div>
                      {analysisResult.detectedSkills.length > 0 ? (
                        <>
                          <div className="skills-wrap">
                            {analysisResult.detectedSkills.map((skill) => {
                              const isMatched = matchedSkillSet.has(
                                skill.toLowerCase()
                              );
                              return (
                                <span
                                  key={skill}
                                  className={`skill-chip ${
                                    isMatched ? "matched" : ""
                                  }`}
                                  title={
                                    isMatched
                                      ? "Matched in your recommended jobs"
                                      : "Extracted from resume"
                                  }
                                >
                                  {isMatched && <Icon name="check" size={12} />}
                                  {skill}
                                </span>
                              );
                            })}
                          </div>

                          <p
                            style={{
                              marginTop: "14px",
                              fontSize: "12.5px",
                              color: "var(--text-muted)"
                            }}
                          >
                            Green badges indicate skills matched across your
                            qualified recommendations below.
                          </p>
                        </>
                      ) : (
                        <p style={{ color: "var(--text-muted)", margin: 0 }}>
                          No technical skills were detected in this PDF. Try
                          uploading a resume with a clearer skills or project
                          section.
                        </p>
                      )}
                    </div>
                  ) : (
                    <div
                      style={{
                        padding: "28px 16px",
                        textAlign: "center",
                        color: "var(--text-muted)",
                        backgroundColor: "#fafafa",
                        borderRadius: "var(--radius-md)",
                        border: "1px solid var(--border-subtle)"
                      }}
                    >
                      Upload a PDF resume on the left to inspect your extracted
                      skill profile and qualified matches.
                    </div>
                  )}
                </div>
              </div>

              {analysisResult && (
                <div style={{ marginTop: "28px" }}>
                  <div className="page-header">
                    <div>
                      <h2 className="page-title" style={{ fontSize: "18px" }}>
                        Qualified Opportunities (
                        {recommendationTiers.allCount})
                      </h2>
                      <p className="page-description">
                        Showing roles meeting the 50% match threshold (75% role
                        context + 25% skill overlap). Percentages reflect
                        profile alignment, not hiring probability.
                      </p>
                    </div>

                    {recommendationTiers.allCount > 0 && (
                      <div
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: "8px"
                        }}
                      >
                        <button
                          type="button"
                          className={`btn btn-sm ${
                            tierFilter === "all"
                              ? "btn-primary"
                              : "btn-secondary"
                          }`}
                          onClick={() => setTierFilter("all")}
                        >
                          All Matches ({recommendationTiers.allCount})
                        </button>
                        <button
                          type="button"
                          className={`btn btn-sm ${
                            tierFilter === "strong"
                              ? "btn-primary"
                              : "btn-secondary"
                          }`}
                          onClick={() => setTierFilter("strong")}
                        >
                          Strong 65%+ ({recommendationTiers.strongCount})
                        </button>
                        <button
                          type="button"
                          className={`btn btn-sm ${
                            tierFilter === "good"
                              ? "btn-primary"
                              : "btn-secondary"
                          }`}
                          onClick={() => setTierFilter("good")}
                        >
                          Good 50–64% ({recommendationTiers.goodCount})
                        </button>
                      </div>
                    )}
                  </div>

                  {recommendationTiers.visible.length > 0 ? (
                    <div className="job-stack">
                      {recommendationTiers.visible.map((job) => {
                        const globalRank =
                          analysisResult.recommendedJobs.findIndex(
                            (item) => item.id === job.id
                          ) + 1;
                        return (
                          <JobCard
                            key={job.id ?? `${job.company_name}-${globalRank}`}
                            job={job}
                            rank={globalRank > 0 ? globalRank : null}
                            onGenerateExplanation={handleGenerateExplanation}
                            isGeneratingExplanation={explainingJobId === job.id}
                          />
                        );
                      })}
                    </div>
                  ) : (
                    <div className="empty-state">
                      <h2 className="empty-state-title">
                        No matches in this score tier
                      </h2>
                      <p className="empty-state-desc">
                        Switch back to All Matches or adjust your Target Role
                        Preference above.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeNav === "jobs" && (
            <div>
              <div className="page-header">
                <div>
                  <h1 className="page-title">Job Explorer</h1>
                  <p className="page-description">
                    Search and filter all {stats.totalJobs} indexed Malaysian IT
                    roles and their verified application links.
                  </p>
                </div>
              </div>

              <div className="toolbar">
                <div className="search-input-wrap">
                  <span className="search-input-icon">
                    <Icon name="search" size={15} />
                  </span>
                  <input
                    type="text"
                    className="input"
                    placeholder="Search by title, company, or city..."
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setVisibleCount(12);
                    }}
                  />
                </div>

                <select
                  className="select"
                  aria-label="Filter by role level"
                  value={roleFilter}
                  onChange={(e) => {
                    setRoleFilter(e.target.value);
                    setVisibleCount(12);
                  }}
                >
                  <option value="all">All Role Levels</option>
                  <option value="internship">Internship</option>
                  <option value="entry">Entry-Level / Graduate</option>
                  <option value="experienced">Mid / Senior</option>
                  <option value="general">Standard Role</option>
                </select>

                <select
                  className="select"
                  aria-label="Filter by location"
                  value={locationFilter}
                  onChange={(e) => {
                    setLocationFilter(e.target.value);
                    setVisibleCount(12);
                  }}
                >
                  <option value="all">All Locations</option>
                  {stats.allLocations.map((loc) => (
                    <option key={loc} value={loc}>
                      {loc}
                    </option>
                  ))}
                </select>

                <select
                  className="select"
                  aria-label="Sort jobs"
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                >
                  <option value="newest">Sort: Newest</option>
                  <option value="links">Sort: Most Links</option>
                  <option value="company">Sort: Company A–Z</option>
                </select>
              </div>

              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "12px",
                  marginBottom: "16px"
                }}
              >
                <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>
                  Showing{" "}
                  <strong style={{ color: "var(--text-primary)" }}>
                    {Math.min(visibleCount, filteredJobs.length)}
                  </strong>{" "}
                  of{" "}
                  <strong style={{ color: "var(--text-primary)" }}>
                    {filteredJobs.length}
                  </strong>{" "}
                  matching roles
                </span>

                <label className="checkbox-pill">
                  <input
                    type="checkbox"
                    checked={verifiedOnly}
                    onChange={(e) => {
                      setVerifiedOnly(e.target.checked);
                      setVisibleCount(12);
                    }}
                  />
                  Verified application links only
                </label>
              </div>

              {loadingJobs ? (
                <div className="job-stack">
                  {[1, 2, 3, 4].map((n) => (
                    <div
                      key={n}
                      className="skeleton"
                      style={{ height: "160px", borderRadius: "12px" }}
                    />
                  ))}
                </div>
              ) : filteredJobs.length === 0 ? (
                <div className="empty-state">
                  <h2 className="empty-state-title">No matching jobs found</h2>
                  <p className="empty-state-desc">
                    Try clearing your search keyword or resetting the role and
                    location filters.
                  </p>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setSearchQuery("");
                      setRoleFilter("all");
                      setLocationFilter("all");
                      setVerifiedOnly(false);
                    }}
                  >
                    Reset Filters
                  </button>
                </div>
              ) : (
                <>
                  <div className="job-stack">
                    {filteredJobs.slice(0, visibleCount).map((job) => (
                      <JobCard key={job.id} job={job} />
                    ))}
                  </div>

                  {visibleCount < filteredJobs.length && (
                    <div
                      style={{
                        marginTop: "24px",
                        display: "flex",
                        justifyContent: "center"
                      }}
                    >
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => setVisibleCount((prev) => prev + 12)}
                      >
                        Load More Roles ({filteredJobs.length - visibleCount}{" "}
                        remaining)
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;