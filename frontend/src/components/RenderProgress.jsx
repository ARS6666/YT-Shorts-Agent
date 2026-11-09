import { useEffect, useState } from "react";
import {
  Activity,
  Check,
  CheckCircle2,
  Clock3,
  Download,
  Film,
  LoaderCircle,
  Scissors,
  Sparkles,
  Subtitles,
  XCircle,
  Zap,
} from "lucide-react";

const API = "http://127.0.0.1:8000";

const STAGES = [
  { id: "queued", label: "Waiting in queue", icon: Clock3 },
  { id: "downloading", label: "Downloading source", icon: Download },
  { id: "tracking", label: "Face detection & tracking", icon: Activity },
  { id: "processing", label: "Creating vertical video", icon: Scissors },
  { id: "transcribing", label: "AI transcription", icon: Sparkles },
  { id: "subtitles", label: "Generating subtitles", icon: Subtitles },
  { id: "encoding", label: "Final encoding", icon: Film },
  { id: "completed", label: "Render completed", icon: CheckCircle2 },
];

function formatTime(seconds) {
  if (seconds == null || !Number.isFinite(Number(seconds))) {
    return "Calculating...";
  }

  const value = Math.max(0, Math.ceil(Number(seconds)));
  const minutes = Math.floor(value / 60);
  const remaining = value % 60;

  if (minutes === 0) return `${remaining}s remaining`;
  return `${minutes}m ${remaining}s remaining`;
}

export default function RenderProgress({ jobId, onComplete, onClose }) {
  const [job, setJob] = useState({
    status: "queued",
    progress: 0,
    stage: "queued",
    eta_seconds: null,
    error: null,
    result: null,
  });

  useEffect(() => {
    if (!jobId) return;

    let active = true;
    let timer;

    const poll = async () => {
      try {
        const response = await fetch(`${API}/editor/progress/${jobId}`);

        if (!response.ok) {
          throw new Error("Could not retrieve render progress.");
        }

        const data = await response.json();

        if (!active) return;

        setJob(data);

        if (data.status === "completed") {
          onComplete?.(data.result || data);
          return;
        }

        if (data.status === "failed") return;

        timer = setTimeout(poll, 900);
      } catch (error) {
        if (!active) return;

        setJob((previous) => ({
          ...previous,
          status: "failed",
          error: error.message,
        }));
      }
    };

    poll();

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [jobId]);

  const progress = Math.min(100, Math.max(0, Number(job.progress) || 0));

  const failed = job.status === "failed";
  const completed = job.status === "completed";

  const stageAliases = {
    download: "downloading",
    face_tracking: "tracking",
    face_detection: "tracking",
    creating_video: "processing",
    video_processing: "processing",
    transcription: "transcribing",
    subtitle_generation: "subtitles",
    burning_subtitles: "encoding",
    muxing: "encoding",
    finalizing: "encoding",
    done: "completed",
  };

  const normalizedStage = stageAliases[job.stage] || job.stage;

  const currentIndex = STAGES.findIndex((item) => item.id === normalizedStage);
  const activeIndex = completed ? STAGES.length - 1 : Math.max(0, currentIndex);

  return (
    <section className="render-progress">
      <style>{`
        .render-progress {
          width: 100%;
          background: #111411;
          border: 1px solid #283029;
          border-radius: 18px;
          padding: 26px;
          color: #f1f5f1;
          box-shadow: 0 18px 55px rgba(0,0,0,.25);
          animation: renderEnter .35s ease;
        }

        @keyframes renderEnter {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .rp-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 16px;
          margin-bottom: 26px;
        }

        .rp-heading {
          display: flex;
          align-items: center;
          gap: 13px;
        }

        .rp-icon {
          width: 46px;
          height: 46px;
          display: grid;
          place-items: center;
          border-radius: 14px;
          color: #b5ff65;
          background: rgba(181,255,101,.10);
          border: 1px solid rgba(181,255,101,.18);
        }

        .rp-title {
          font-size: 16px;
          font-weight: 800;
          margin: 0 0 5px;
        }

        .rp-subtitle {
          font-size: 12px;
          color: #879188;
          margin: 0;
        }

        .rp-status {
          display: flex;
          align-items: center;
          gap: 7px;
          color: #b5ff65;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: .7px;
          text-transform: uppercase;
        }

        .rp-status.failed { color: #ff7777; }
        .rp-status.completed { color: #b5ff65; }

        .rp-pulse {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: currentColor;
          box-shadow: 0 0 12px currentColor;
          animation: rpPulse 1.2s infinite;
        }

        @keyframes rpPulse {
          50% { opacity: .3; }
        }

        .rp-progress-area {
          background: #191e19;
          border: 1px solid #293129;
          border-radius: 15px;
          padding: 21px;
          margin-bottom: 23px;
        }

        .rp-progress-top {
          display: flex;
          align-items: end;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 15px;
        }

        .rp-percent {
          font-size: 42px;
          line-height: 1;
          font-weight: 900;
          letter-spacing: -2px;
          color: #b5ff65;
        }

        .rp-percent span {
          font-size: 20px;
          color: #8c9989;
        }

        .rp-eta {
          text-align: right;
          color: #a1aaa1;
          font-size: 12px;
        }

        .rp-eta strong {
          display: block;
          color: #f1f5f1;
          font-size: 14px;
          margin-top: 5px;
        }

        .rp-track {
          height: 9px;
          width: 100%;
          background: #303830;
          border-radius: 20px;
          overflow: hidden;
        }

        .rp-fill {
          height: 100%;
          border-radius: inherit;
          background: linear-gradient(90deg, #83d83d, #c5ff79);
          box-shadow: 0 0 18px rgba(181,255,101,.35);
          transition: width .55s ease;
          position: relative;
        }

        .rp-fill::after {
          content: "";
          position: absolute;
          inset: 0;
          background: linear-gradient(
            100deg,
            transparent,
            rgba(255,255,255,.35),
            transparent
          );
          animation: rpShimmer 1.8s infinite;
        }

        @keyframes rpShimmer {
          from { transform: translateX(-100%); }
          to { transform: translateX(100%); }
        }

        .rp-current {
          display: flex;
          align-items: center;
          gap: 9px;
          margin-top: 16px;
          color: #d9e5d6;
          font-size: 12px;
        }

        .rp-current svg {
          color: #b5ff65;
        }

        .rp-stages-title {
          font-size: 11px;
          font-weight: 800;
          color: #758075;
          text-transform: uppercase;
          letter-spacing: 1px;
          margin: 0 0 15px;
        }

        .rp-stages {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
        }

        .rp-stage {
          min-width: 0;
          display: flex;
          align-items: center;
          gap: 11px;
          padding: 12px;
          border: 1px solid #252d25;
          background: #151a15;
          border-radius: 12px;
          color: #727e72;
          font-size: 11px;
          transition: .2s ease;
        }

        .rp-stage.active {
          color: #dfffc6;
          border-color: rgba(181,255,101,.4);
          background: rgba(181,255,101,.07);
        }

        .rp-stage.done {
          color: #a8b4a5;
          border-color: #303b2d;
        }

        .rp-stage-icon {
          flex-shrink: 0;
          width: 29px;
          height: 29px;
          display: grid;
          place-items: center;
          border-radius: 9px;
          background: #222922;
        }

        .rp-stage.active .rp-stage-icon {
          color: #b5ff65;
          background: rgba(181,255,101,.12);
        }

        .rp-stage.done .rp-stage-icon {
          color: #b5ff65;
        }

        .rp-error {
          display: flex;
          align-items: flex-start;
          gap: 11px;
          padding: 15px;
          border: 1px solid rgba(255,100,100,.25);
          border-radius: 12px;
          background: rgba(255,80,80,.07);
          color: #ffaaaa;
          font-size: 12px;
          line-height: 1.7;
          margin-top: 18px;
          overflow-wrap: anywhere;
        }

        .rp-success {
          display: flex;
          align-items: center;
          gap: 10px;
          color: #b5ff65;
          font-size: 13px;
          font-weight: 800;
          margin-top: 20px;
        }

        .rp-download {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 9px;
          margin-top: 17px;
          padding: 12px 18px;
          border-radius: 11px;
          background: #b5ff65;
          color: #10160d;
          font-size: 12px;
          font-weight: 900;
          text-decoration: none;
          transition: .2s;
        }

        .rp-download:hover {
          background: #caff91;
          transform: translateY(-2px);
        }

        .rp-close {
          border: 0;
          background: #252b25;
          color: #9ba69a;
          border-radius: 9px;
          width: 34px;
          height: 34px;
          cursor: pointer;
        }

        @media (max-width: 600px) {
          .render-progress { padding: 17px; }
          .rp-stages { grid-template-columns: 1fr; }
          .rp-percent { font-size: 34px; }
          .rp-progress-area { padding: 16px; }
        }
      `}</style>

      <div className="rp-header">
        <div className="rp-heading">
          <div className="rp-icon">
            {failed ? (
              <XCircle size={23} />
            ) : completed ? (
              <CheckCircle2 size={23} />
            ) : (
              <Zap size={23} />
            )}
          </div>

          <div>
            <h3 className="rp-title">
              {failed
                ? "Render failed"
                : completed
                  ? "Your video is ready"
                  : "Rendering your Short"}
            </h3>
            <p className="rp-subtitle">
              {failed
                ? "Something went wrong during processing"
                : completed
                  ? "All processing stages completed successfully"
                  : "TrendHunter is preparing your video"}
            </p>
          </div>
        </div>

        <div
          className={`rp-status ${failed ? "failed" : completed ? "completed" : ""}`}
        >
          {!failed && !completed && <span className="rp-pulse" />}
          {failed ? "Failed" : completed ? "Completed" : "Processing"}
        </div>
      </div>

      <div className="rp-progress-area">
        <div className="rp-progress-top">
          <div className="rp-percent">
            {Math.round(completed ? 100 : progress)}
            <span>%</span>
          </div>

          <div className="rp-eta">
            Estimated time
            <strong>
              {completed
                ? "Finished"
                : failed
                  ? "Unavailable"
                  : formatTime(job.eta_seconds)}
            </strong>
          </div>
        </div>

        <div className="rp-track">
          <div
            className="rp-fill"
            style={{
              width: `${completed ? 100 : progress}%`,
              background: failed ? "#ff7777" : undefined,
            }}
          />
        </div>

        <div className="rp-current">
          {completed ? (
            <CheckCircle2 size={16} />
          ) : failed ? (
            <XCircle size={16} />
          ) : (
            <LoaderCircle size={16} className="animate-spin" />
          )}

          <span>
            {job.stage_label ||
              STAGES.find((item) => item.id === job.stage)?.label ||
              "Preparing render..."}
          </span>
        </div>
      </div>

      <h4 className="rp-stages-title">Rendering pipeline</h4>

      <div className="rp-stages">
        {STAGES.map((stage, index) => {
          const Icon = stage.icon;
          const isDone = completed || (!failed && index < activeIndex);
          const isActive = !failed && !completed && index === activeIndex;

          return (
            <div
              key={stage.id}
              className={`rp-stage ${
                isDone ? "done" : isActive ? "active" : ""
              }`}
            >
              <div className="rp-stage-icon">
                {isDone ? <Check size={16} /> : <Icon size={15} />}
              </div>
              <span>{stage.label}</span>
            </div>
          );
        })}
      </div>

      {failed && (
        <div className="rp-error">
          <XCircle size={18} />
          <span>{job.error || "An unknown rendering error occurred."}</span>
        </div>
      )}

      {completed && (
        <div className="rp-success">
          <CheckCircle2 size={19} />
          Video successfully rendered.
        </div>
      )}

      {completed && job.result?.download_url && (
        <a
          className="rp-download"
          href={
            job.result.download_url.startsWith("http")
              ? job.result.download_url
              : `${API}${job.result.download_url}`
          }
          download
        >
          <Download size={16} />
          Download your Short
        </a>
      )}

      {(failed || completed) && onClose && (
        <button className="rp-close" onClick={onClose}>
          <X size={16} />
        </button>
      )}
    </section>
  );
}
