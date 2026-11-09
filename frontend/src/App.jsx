import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  LayoutDashboard,
  Users,
  Clapperboard,
  Compass,
  Radio,
  RefreshCw,
  Search,
  Play,
  ExternalLink,
  Eye,
  Clock3,
  CheckCircle2,
  AlertCircle,
  Plus,
  Trash2,
  Power,
  X,
  Scissors,
  Download,
  SlidersHorizontal,
} from "lucide-react";
import "./App.css";

const API = "http://127.0.0.1:8000";

async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {}
    throw new Error(message);
  }

  if (response.status === 204) return null;
  return response.json();
}

function getItems(data) {
  if (Array.isArray(data)) return data;
  return data?.items || data?.results || [];
}

function getClipSlug(clip) {
  if (clip.external_id) return clip.external_id;

  const url = clip.url || "";
  const match = url.match(
    /(?:clips\.twitch\.tv\/|twitch\.tv\/[^/]+\/clip\/)([A-Za-z0-9_-]+)/i,
  );

  return match?.[1] || "";
}

function getClipUrl(clip) {
  if (clip.url) return clip.url;
  const slug = getClipSlug(clip);
  return slug ? `https://clips.twitch.tv/${slug}` : "";
}

function parseTwitchUrl(value) {
  let input = value.trim();

  if (!input) throw new Error("لینک کانال را وارد کن.");

  if (!/^https?:\/\//i.test(input)) {
    input = `https://${input}`;
  }

  let parsed;

  try {
    parsed = new URL(input);
  } catch {
    throw new Error("لینک واردشده معتبر نیست.");
  }

  const host = parsed.hostname.toLowerCase().replace(/^www\./, "");

  if (!["twitch.tv", "m.twitch.tv"].includes(host)) {
    throw new Error("فعلاً فقط لینک Twitch پشتیبانی می‌شود.");
  }

  const username = parsed.pathname.split("/").filter(Boolean)[0];

  if (
    !username ||
    ["directory", "downloads", "p", "settings", "videos", "clip"].includes(
      username.toLowerCase(),
    )
  ) {
    throw new Error("لینک کانال Twitch معتبر نیست.");
  }

  return {
    username,
    profileUrl: `https://www.twitch.tv/${username}`,
    slug: `twitch-${username}`.toLowerCase().replace(/[^a-z0-9-]/g, "-"),
  };
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("en-US");
}

function Score({ value }) {
  const score = Math.max(0, Math.min(100, Number(value || 0)));

  return (
    <div className="score">
      <div className="score-track">
        <div className="score-fill" style={{ width: `${score}%` }} />
      </div>
      <strong>{Math.round(score)}</strong>
    </div>
  );
}

function ClipStatus({ status }) {
  const value = status || "pending";

  return (
    <span className={`clip-status ${value}`}>
      <i />
      {value}
    </span>
  );
}

/* ---------------- CLIP PREVIEW MODAL ---------------- */

function ClipModal({ clip, onClose }) {
  if (!clip) return null;

  const slug = getClipSlug(clip);
  const clipUrl = getClipUrl(clip);
  const parent = window.location.hostname;

  const embedUrl = slug
    ? `https://clips.twitch.tv/embed?clip=${encodeURIComponent(
        slug,
      )}&parent=${encodeURIComponent(parent)}&autoplay=false`
    : "";

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="clip-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <span className="eyebrow">TWITCH CLIP PREVIEW</span>
            <h2>{clip.title || "Untitled clip"}</h2>
          </div>

          <button className="icon-button" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {embedUrl ? (
          <div className="clip-player">
            <iframe
              src={embedUrl}
              title={clip.title || "Twitch clip"}
              allowFullScreen
              allow="autoplay; fullscreen"
            />
          </div>
        ) : (
          <div className="player-error">
            شناسه کلیپ در اطلاعات دریافتی از API وجود ندارد.
          </div>
        )}

        <div className="modal-details">
          <span>
            <Eye size={15} /> {formatNumber(clip.views)} views
          </span>
          <span>
            <Clock3 size={15} /> {Number(clip.duration || 0).toFixed(0)} sec
          </span>
          <span>Viral score: {Math.round(Number(clip.viral_score || 0))}</span>
        </div>

        {clipUrl && (
          <a
            className="primary-button open-twitch"
            href={clipUrl}
            target="_blank"
            rel="noreferrer"
          >
            Open original Twitch video <ExternalLink size={16} />
          </a>
        )}
      </div>
    </div>
  );
}

/* ---------------- CLIP CARD ---------------- */

function ClipCard({ clip, onPreview, onStatusChange }) {
  const clipUrl = getClipUrl(clip);

  return (
    <article className="clip-card">
      <button
        className="clip-thumbnail"
        onClick={() => onPreview(clip)}
        type="button"
      >
        {clip.thumbnail_url ? (
          <img
            src={clip.thumbnail_url}
            alt={clip.title || "Twitch clip"}
            loading="lazy"
          />
        ) : (
          <div className="thumbnail-placeholder">
            <Radio size={32} />
            <span>TWITCH CLIP</span>
          </div>
        )}

        <span className="play-button">
          <Play size={22} fill="currentColor" />
        </span>

        <span className="duration">
          {Number(clip.duration || 0).toFixed(0)}s
        </span>
      </button>

      <div className="clip-card-body">
        <div className="clip-title-line">
          <h3>{clip.title || "Untitled Twitch clip"}</h3>
          <span className="platform-label">TWITCH</span>
        </div>

        <p className="clip-creator">
          {clip.creator ||
            clip.streamer_name ||
            clip.channel_title ||
            "Unknown creator"}
        </p>

        <div className="clip-metrics">
          <span>
            <Eye size={14} /> {formatNumber(clip.views)}
          </span>
          <span>
            <Clock3 size={14} /> {Number(clip.duration || 0).toFixed(0)}s
          </span>
        </div>

        <div className="clip-score-row">
          <span>Viral score</span>
          <Score value={clip.viral_score} />
        </div>

        <div className="clip-card-footer">
          <ClipStatus status={clip.status} />

          <div className="clip-actions">
            <button
              type="button"
              title="Preview clip"
              onClick={() => onPreview(clip)}
            >
              <Play size={15} />
            </button>

            {clipUrl && (
              <a
                title="Open Twitch"
                href={clipUrl}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={15} />
              </a>
            )}

            <button
              type="button"
              title="Approve"
              onClick={() => onStatusChange(clip.id, "approved")}
            >
              <CheckCircle2 size={15} />
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

/* ---------------- CLIP LIBRARY ---------------- */

function ClipLibrary({
  clips,
  loading,
  collecting,
  onCollect,
  onRefresh,
  onStatusChange,
  collectionSummary,
  analytics,
}) {
  const [selectedClip, setSelectedClip] = useState(null);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("score");

  const twitchClips = useMemo(() => {
    let result = clips.filter(
      (clip) => (clip.platform || "").toLowerCase() === "twitch",
    );

    if (search.trim()) {
      const query = search.toLowerCase();

      result = result.filter((clip) =>
        `${clip.title || ""} ${clip.creator || ""} ${clip.streamer_name || ""}`
          .toLowerCase()
          .includes(query),
      );
    }

    result.sort((a, b) => {
      if (sort === "views") {
        return Number(b.views || 0) - Number(a.views || 0);
      }

      return Number(b.viral_score || 0) - Number(a.viral_score || 0);
    });

    return result;
  }, [clips, search, sort]);

  const twitchStats = analytics?.twitch || {};

  const totalViews = Number(twitchStats.total_views || 0);
  const totalClips = Number(twitchStats.total || 0);
  const pendingClips = Number(twitchStats.pending || 0);
  const approvedClips = Number(twitchStats.approved || 0);
  const rejectedClips = Number(twitchStats.rejected || 0);

  return (
    <section className="page-content">
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            <i className="live-dot" /> TWITCH DISCOVERY
          </span>
          <h1>
            Clip library<span>.</span>
          </h1>
          <p>Discover, preview and manage clips collected from Twitch.</p>
        </div>

        <div className="heading-actions">
          <button
            className="secondary-button"
            onClick={onRefresh}
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            Refresh clips
          </button>

          <button
            className="primary-button"
            onClick={onCollect}
            disabled={collecting}
          >
            <Radio size={16} className={collecting ? "spin" : ""} />
            {collecting ? "Collecting..." : "Collect Twitch clips"}
          </button>
        </div>
      </div>

      <div className="clip-stats-grid">
        <div className="clip-stat">
          <span>Total Twitch clips</span>
          <strong>{formatNumber(totalClips)}</strong>
          <small>All clips stored in database</small>
        </div>

        <div className="clip-stat">
          <span>Total views</span>
          <strong>{formatNumber(totalViews)}</strong>
          <small>Views across all stored Twitch clips</small>
        </div>

        <div className="clip-stat">
          <span>Waiting for review</span>
          <strong>{formatNumber(pendingClips)}</strong>
          <small>Not approved or rejected</small>
        </div>

        <div className="clip-stat">
          <span>Approved / Rejected</span>
          <strong>
            {formatNumber(approvedClips)} / {formatNumber(rejectedClips)}
          </strong>
          <small>Reviewed clips</small>
        </div>
      </div>

      <div className="library-count-note">
        Showing {formatNumber(twitchClips.length)} clips loaded in this view
        {totalClips > twitchClips.length
          ? ` · ${formatNumber(totalClips - twitchClips.length)} more in database`
          : ""}
      </div>

      {collectionSummary && (
        <div className="collection-notice">
          <CheckCircle2 size={20} />

          <div>
            <strong>Collection completed</strong>

            <span>
              Accounts checked: {collectionSummary.accounts_checked ?? 0}
            </span>

            <span>
              Found: {formatNumber(collectionSummary.clips_found ?? 0)}
              {" · "}
              New: {formatNumber(collectionSummary.clips_created ?? 0)}
              {" · "}
              Updated: {formatNumber(collectionSummary.clips_updated ?? 0)}
            </span>

            {collectionSummary.errors?.length > 0 && (
              <div className="collection-errors">
                <strong>
                  {collectionSummary.errors.length} collection errors
                </strong>

                {collectionSummary.errors.map((item, index) => (
                  <span key={`${item.account}-${index}`}>
                    {item.account}: {item.error}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="library-toolbar">
        <div className="search-field">
          <Search size={17} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search clips or creators..."
          />
        </div>

        <select value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="score">Highest viral score</option>
          <option value="views">Most viewed</option>
        </select>
      </div>

      {loading ? (
        <div className="empty-library">
          <RefreshCw className="spin" size={26} />
          <strong>Loading clips...</strong>
        </div>
      ) : twitchClips.length === 0 ? (
        <div className="empty-library">
          <Clapperboard size={34} />
          <strong>No Twitch clips found</strong>
          <p>
            First add some Twitch streamers, then click Collect Twitch clips.
          </p>
          <button
            className="primary-button"
            onClick={onCollect}
            disabled={collecting}
          >
            <Radio size={16} /> Collect clips
          </button>
        </div>
      ) : (
        <div className="clip-grid">
          {twitchClips.map((clip) => (
            <ClipCard
              key={clip.id}
              clip={clip}
              onPreview={setSelectedClip}
              onStatusChange={onStatusChange}
            />
          ))}
        </div>
      )}

      <ClipModal clip={selectedClip} onClose={() => setSelectedClip(null)} />
    </section>
  );
}

/* ---------------- STREAMER MANAGEMENT ---------------- */

function StreamersPage({ streamers, onRefresh, setError }) {
  const [channelUrl, setChannelUrl] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [priority, setPriority] = useState(8);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [notice, setNotice] = useState("");

  async function addStreamer(event) {
    event.preventDefault();
    setNotice("");
    setError("");

    let channel;

    try {
      channel = parseTwitchUrl(channelUrl);
    } catch (error) {
      setNotice(error.message);
      return;
    }

    setSaving(true);

    try {
      const existing = streamers.find((streamer) =>
        streamer.accounts?.some(
          (account) =>
            account.platform === "twitch" &&
            account.username?.toLowerCase() === channel.username.toLowerCase(),
        ),
      );

      let streamer = existing;

      if (!streamer) {
        streamer = await request(`${API}/streamers`, {
          method: "POST",
          body: JSON.stringify({
            name: displayName.trim() || channel.username,
            slug: channel.slug,
            priority: Number(priority),
            notes: `Twitch channel: ${channel.profileUrl}`,
          }),
        });
      }

      const alreadyConnected = streamer.accounts?.some(
        (account) =>
          account.platform === "twitch" &&
          account.username?.toLowerCase() === channel.username.toLowerCase(),
      );

      if (!alreadyConnected) {
        await request(`${API}/streamers/${streamer.id}/accounts`, {
          method: "POST",
          body: JSON.stringify({
            platform: "twitch",
            username: channel.username,
            external_id: null,
            profile_url: channel.profileUrl,
          }),
        });
      }

      setNotice(`Streamer ${channel.username} added successfully.`);
      setChannelUrl("");
      setDisplayName("");
      await onRefresh();
    } catch (error) {
      setNotice(error.message || "Could not add streamer.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleStreamer(streamer) {
    setBusyId(streamer.id);
    setError("");

    try {
      await request(`${API}/streamers/${streamer.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !streamer.is_active }),
      });

      await onRefresh();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusyId(null);
    }
  }

  async function deleteStreamer(streamer) {
    if (!window.confirm(`Delete ${streamer.name}?`)) return;

    setBusyId(streamer.id);

    try {
      await request(`${API}/streamers/${streamer.id}`, {
        method: "DELETE",
      });

      await onRefresh();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="page-content">
      <div className="page-heading">
        <div>
          <span className="eyebrow">CREATOR SOURCES</span>
          <h1>
            Streamers<span>.</span>
          </h1>
          <p>Manage the Twitch channels monitored by TrendHunter.</p>
        </div>
      </div>

      <form className="add-streamer-form" onSubmit={addStreamer}>
        <div>
          <label>Twitch channel URL</label>
          <input
            value={channelUrl}
            onChange={(event) => setChannelUrl(event.target.value)}
            placeholder="https://www.twitch.tv/streamername"
          />
        </div>

        <div>
          <label>Display name (optional)</label>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Streamer name"
          />
        </div>

        <div>
          <label>Priority</label>
          <select
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
          >
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((number) => (
              <option key={number} value={number}>
                {number}
              </option>
            ))}
          </select>
        </div>

        <button className="primary-button" disabled={saving}>
          <Plus size={16} />
          {saving ? "Adding..." : "Add streamer"}
        </button>
      </form>

      {notice && <div className="inline-notice">{notice}</div>}

      <div className="streamer-list">
        {streamers.map((streamer) => {
          const twitchAccounts = (streamer.accounts || []).filter(
            (account) => account.platform === "twitch",
          );

          return (
            <article className="streamer-card" key={streamer.id}>
              <div className="streamer-avatar">
                {(streamer.name || "?").slice(0, 1).toUpperCase()}
              </div>

              <div className="streamer-info">
                <strong>{streamer.name}</strong>
                <span>
                  {twitchAccounts
                    .map((account) => account.username)
                    .join(", ") || "No Twitch account connected"}
                </span>
                <small>
                  {streamer.is_active ? "Monitoring active" : "Paused"}
                </small>
              </div>

              <div className="streamer-actions">
                <button
                  title={streamer.is_active ? "Pause" : "Activate"}
                  disabled={busyId === streamer.id}
                  onClick={() => toggleStreamer(streamer)}
                >
                  <Power size={16} />
                </button>

                <button
                  title="Delete"
                  disabled={busyId === streamer.id}
                  onClick={() => deleteStreamer(streamer)}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </article>
          );
        })}

        {streamers.length === 0 && (
          <div className="empty-library">
            <Users size={30} />
            <strong>No streamers added yet</strong>
          </div>
        )}
      </div>
    </section>
  );
}
/* ---------------- SMART CLIP EDITOR ---------------- */

function EditorPage({ clips, setError }) {
  const [selectedClipId, setSelectedClipId] = useState("");
  const [cropMode, setCropMode] = useState("auto");
  const [zoom, setZoom] = useState(1);
  const [volume, setVolume] = useState(1);
  const [manualX, setManualX] = useState(0.5);
  const [manualY, setManualY] = useState(0.5);

  // Streamer Split
  const [splitRatio, setSplitRatio] = useState(0.5);
  const [faceScale, setFaceScale] = useState(3.4);
  const [gameplayX, setGameplayX] = useState(0.5);
  const [gameplayY, setGameplayY] = useState(0.5);

  // Subtitle settings
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true);
  const [captionDisplayMode, setCaptionDisplayMode] = useState("word");
  const [captionAnimation, setCaptionAnimation] = useState("pop_bounce");
  const [animationIntensity, setAnimationIntensity] = useState(1);
  const [captionPosition, setCaptionPosition] = useState("lower");
  const [captionBold, setCaptionBold] = useState(true);
  const [captionFontSize, setCaptionFontSize] = useState(null);
  const [captionSize, setCaptionSize] = useState("large");
  const [captionColor, setCaptionColor] = useState("mrbeast");
  const [captionOutline, setCaptionOutline] = useState("white_black");
  const [captionShadow, setCaptionShadow] = useState("strong");

  // Sound effects
  const [soundEffects, setSoundEffects] = useState(true);
  const [sfxVolume, setSfxVolume] = useState(0.25);

  const [rendering, setRendering] = useState(false);
  const [result, setResult] = useState(null);

  const sizePresets = {
    small: 82,
    medium: 94,
    large: 104,
    extra_large: 130,
  };

  const colorPresets = {
    mrbeast: "#FFD700",
    white: "#FFFFFF",
    green: "#00FF66",
    cyan: "#00FFFF",
    pink: "#FF66CC",
  };

  const effectiveCaptionFontSize =
    captionFontSize ?? sizePresets[captionSize] ?? 88;

  const previewFontSize = Math.max(
    15,
    Math.min(34, effectiveCaptionFontSize * 0.25),
  );

  const twitchClips = useMemo(
    () =>
      clips
        .filter((clip) => clip.platform === "twitch")
        .sort(
          (a, b) => Number(b.viral_score || 0) - Number(a.viral_score || 0),
        ),
    [clips],
  );

  useEffect(() => {
    if (!selectedClipId && twitchClips.length > 0) {
      setSelectedClipId(String(twitchClips[0].id));
    }
  }, [twitchClips, selectedClipId]);

  const selectedClip = twitchClips.find(
    (clip) => String(clip.id) === String(selectedClipId),
  );

  async function renderVideo() {
    if (!selectedClip) {
      setError("Please select a Twitch clip first.");
      return;
    }

    setRendering(true);
    setResult(null);
    setError("");

    try {
      const data = await request(`${API}/editor/render`, {
        method: "POST",
        body: JSON.stringify({
          clip_id: Number(selectedClip.id),
          crop_mode: cropMode,
          zoom: Number(zoom),
          volume: Number(volume),
          manual_x: Number(manualX),
          manual_y: Number(manualY),
          split_ratio: Number(splitRatio),
          face_scale: Number(faceScale),
          gameplay_x: Number(gameplayX),
          gameplay_y: Number(gameplayY),

          subtitles_enabled: subtitlesEnabled,
          caption_display_mode: captionDisplayMode,
          caption_animation: captionAnimation,
          animation_intensity: Number(animationIntensity),
          caption_position: captionPosition,
          caption_bold: captionBold,
          caption_font_size: captionFontSize,
          caption_size: captionSize,
          caption_color: captionColor,
          caption_outline: captionOutline,
          caption_shadow: captionShadow,

          sound_effects: soundEffects,
          sfx_volume: Number(sfxVolume),
        }),
      });

      setResult(data);
    } catch (error) {
      setError(error.message || "Video rendering failed.");
    } finally {
      setRendering(false);
    }
  }

  const downloadUrl = result?.download_url
    ? `${API}${result.download_url}`
    : "";

  return (
    <section className="page-content">
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            <Scissors size={14} /> AI VIDEO PRODUCTION
          </span>
          <h1>
            Smart editor<span>.</span>
          </h1>
          <p>
            Turn Twitch clips into vertical YouTube Shorts with automatic face
            tracking and animated subtitles.
          </p>
        </div>
      </div>

      <div className="editor-layout">
        <div className="editor-settings">
          <div className="editor-section-heading">
            <div>
              <span className="eyebrow">01 / SOURCE</span>
              <h2>Select a clip</h2>
            </div>
          </div>

          <label className="editor-label">Twitch clip</label>

          <select
            className="editor-select"
            value={selectedClipId}
            onChange={(event) => {
              setSelectedClipId(event.target.value);
              setResult(null);
            }}
          >
            <option value="">Choose a clip...</option>

            {twitchClips.map((clip) => (
              <option key={clip.id} value={clip.id}>
                #{clip.id} · {(clip.title || "Untitled clip").slice(0, 65)}
              </option>
            ))}
          </select>

          {selectedClip && (
            <div className="editor-source-card">
              {selectedClip.thumbnail_url ? (
                <img
                  src={selectedClip.thumbnail_url}
                  alt={selectedClip.title}
                />
              ) : (
                <div className="editor-source-placeholder">
                  <Clapperboard size={26} />
                </div>
              )}

              <div>
                <strong>{selectedClip.title || "Untitled clip"}</strong>
                <span>{selectedClip.creator || "Unknown creator"}</span>
                <small>
                  {Number(selectedClip.duration || 0).toFixed(0)} sec
                  {" · "}
                  Score {Math.round(Number(selectedClip.viral_score || 0))}
                </small>
              </div>
            </div>
          )}

          <div className="editor-divider" />

          <div className="editor-section-heading">
            <div>
              <span className="eyebrow">02 / FRAMING</span>
              <h2>Crop settings</h2>
            </div>
          </div>

          <label className="editor-label">Tracking mode</label>

          <div className="crop-mode-grid">
            <button
              type="button"
              className={cropMode === "auto" ? "selected" : ""}
              onClick={() => setCropMode("auto")}
            >
              <Activity size={20} />
              <strong>Auto</strong>
              <small>Face tracking</small>
            </button>

            <button
              type="button"
              className={cropMode === "stream_split" ? "selected" : ""}
              onClick={() => setCropMode("stream_split")}
            >
              <Clapperboard size={20} />
              <strong>Streamer Split</strong>
              <small>Camera + Gameplay</small>
            </button>

            <button
              type="button"
              className={cropMode === "center" ? "selected" : ""}
              onClick={() => setCropMode("center")}
            >
              <Compass size={20} />
              <strong>Center</strong>
              <small>Center crop</small>
            </button>

            <button
              type="button"
              className={cropMode === "manual" ? "selected" : ""}
              onClick={() => setCropMode("manual")}
            >
              <SlidersHorizontal size={20} />
              <strong>Manual</strong>
              <small>Custom position</small>
            </button>
          </div>

          {cropMode === "auto" && (
            <div className="editor-info">
              <Activity size={17} />
              <span>
                AI detects faces and follows the selected face throughout the
                video. If no face is detected, center crop is used.
              </span>
            </div>
          )}

          {cropMode === "manual" && (
            <div className="manual-controls">
              <div className="editor-range-header">
                <label>Horizontal position</label>
                <strong>{Math.round(manualX * 100)}%</strong>
              </div>

              <input
                className="editor-range"
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={manualX}
                onChange={(event) => setManualX(Number(event.target.value))}
              />

              <div className="editor-range-header">
                <label>Vertical position</label>
                <strong>{Math.round(manualY * 100)}%</strong>
              </div>

              <input
                className="editor-range"
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={manualY}
                onChange={(event) => setManualY(Number(event.target.value))}
              />
            </div>
          )}

          {cropMode === "stream_split" && (
            <div className="split-controls">
              <div className="editor-info">
                <Clapperboard size={18} />
                <span>
                  Streamer camera appears in the upper panel and gameplay
                  appears in the lower panel.
                </span>
              </div>

              <div className="split-layout-demo">
                <div className="split-camera-demo">
                  <span>STREAMER CAMERA</span>
                </div>
                <div className="split-game-demo">
                  <span>GAMEPLAY</span>
                </div>
              </div>

              <div className="editor-range-header">
                <label>Camera panel height</label>
                <strong>{Math.round(splitRatio * 100)}%</strong>
              </div>

              <input
                className="editor-range"
                type="range"
                min="0.35"
                max="0.65"
                step="0.01"
                value={splitRatio}
                onChange={(event) => setSplitRatio(Number(event.target.value))}
              />

              <div className="editor-range-header">
                <label>Face size</label>
                <strong>{Number(faceScale).toFixed(1)}x</strong>
              </div>

              <input
                className="editor-range"
                type="range"
                min="2"
                max="6"
                step="0.1"
                value={faceScale}
                onChange={(event) => setFaceScale(Number(event.target.value))}
              />

              <div className="editor-range-header">
                <label>Gameplay horizontal position</label>
                <strong>{Math.round(gameplayX * 100)}%</strong>
              </div>

              <input
                className="editor-range"
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={gameplayX}
                onChange={(event) => setGameplayX(Number(event.target.value))}
              />

              <div className="editor-range-header">
                <label>Gameplay vertical position</label>
                <strong>{Math.round(gameplayY * 100)}%</strong>
              </div>

              <input
                className="editor-range"
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={gameplayY}
                onChange={(event) => setGameplayY(Number(event.target.value))}
              />
            </div>
          )}

          <div className="editor-divider" />

          <div className="editor-section-heading">
            <div>
              <span className="eyebrow">03 / ENHANCEMENT</span>
              <h2>Video & audio</h2>
            </div>
          </div>

          <div className="editor-range-header">
            <label>Zoom level</label>
            <strong>{Number(zoom).toFixed(2)}x</strong>
          </div>

          <input
            className="editor-range"
            type="range"
            min="1"
            max="1.5"
            step="0.05"
            value={zoom}
            onChange={(event) => setZoom(Number(event.target.value))}
          />

          <div className="editor-range-header">
            <label>Audio volume</label>
            <strong>{Math.round(volume * 100)}%</strong>
          </div>

          <input
            className="editor-range"
            type="range"
            min="0"
            max="2"
            step="0.05"
            value={volume}
            onChange={(event) => setVolume(Number(event.target.value))}
          />

          <div className="editor-divider" />
          <div className="editor-section-heading">
            <div>
              <span className="eyebrow">04 / CAPTIONS</span>
              <h2>High-effort subtitles</h2>
            </div>
            <span className="caption-font-chip">RUBIK EXTRA BOLD</span>
          </div>

          <div className="caption-settings">
            <label className="caption-toggle-row">
              <span>
                <strong>Animated subtitles</strong>
                <small>Burn captions into the final video</small>
              </span>
              <input
                type="checkbox"
                checked={subtitlesEnabled}
                onChange={(event) => setSubtitlesEnabled(event.target.checked)}
              />
            </label>

            {subtitlesEnabled && (
              <>
                <div className="caption-control-group">
                  <label className="editor-label">Display mode</label>

                  <div className="caption-preset-grid">
                    <button
                      type="button"
                      className={captionDisplayMode === "word" ? "active" : ""}
                      onClick={() => setCaptionDisplayMode("word")}
                    >
                      Word by Word
                    </button>

                    <button
                      type="button"
                      className={
                        captionDisplayMode === "phrase" ? "active" : ""
                      }
                      onClick={() => setCaptionDisplayMode("phrase")}
                    >
                      Phrase Mode
                    </button>
                  </div>

                  <small className="caption-help-text">
                    {captionDisplayMode === "word"
                      ? "Only the currently spoken word appears."
                      : "Show up to four words together with active highlighting."}
                  </small>
                </div>

                <div className="caption-control-group">
                  <label className="editor-label">Word animation</label>

                  <select
                    className="editor-select"
                    value={captionAnimation}
                    onChange={(event) =>
                      setCaptionAnimation(event.target.value)
                    }
                  >
                    <option value="pop_bounce">Pop + Bounce</option>
                    <option value="pop">Smooth Pop</option>
                    <option value="shake">Shake</option>
                    <option value="none">No animation</option>
                  </select>
                </div>

                <div className="editor-range-header">
                  <label>Animation intensity</label>
                  <strong>{Number(animationIntensity).toFixed(1)}x</strong>
                </div>

                <input
                  className="editor-range"
                  type="range"
                  min="0.5"
                  max="1.5"
                  step="0.1"
                  value={animationIntensity}
                  onChange={(event) =>
                    setAnimationIntensity(Number(event.target.value))
                  }
                />

                <div className="caption-control-group">
                  <label className="editor-label">Caption position</label>

                  <div className="caption-position-grid">
                    {[
                      ["lower", "Lower"],
                      ["center", "Center"],
                      ["upper", "Upper"],
                    ].map(([value, label]) => (
                      <button
                        type="button"
                        key={value}
                        className={captionPosition === value ? "selected" : ""}
                        onClick={() => setCaptionPosition(value)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="caption-control-group">
                  <label className="editor-label">Caption size</label>

                  <div className="caption-preset-grid">
                    {[
                      ["small", "Small"],
                      ["medium", "Medium"],
                      ["large", "Large"],
                      ["extra_large", "Extra Large"],
                    ].map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        className={
                          captionSize === value && captionFontSize === null
                            ? "active"
                            : ""
                        }
                        onClick={() => {
                          setCaptionSize(value);
                          setCaptionFontSize(null);
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="caption-control-group">
                  <div className="editor-range-header">
                    <label>Manual font size</label>
                    <strong>{effectiveCaptionFontSize}px</strong>
                  </div>

                  <input
                    className="editor-range"
                    type="range"
                    min="40"
                    max="140"
                    step="2"
                    value={effectiveCaptionFontSize}
                    onChange={(event) =>
                      setCaptionFontSize(Number(event.target.value))
                    }
                  />

                  <button
                    type="button"
                    className="caption-reset-button"
                    onClick={() => setCaptionFontSize(null)}
                  >
                    Reset to preset size
                  </button>
                </div>

                <label className="caption-toggle-row">
                  <span>
                    <strong>Extra Bold Typography</strong>
                    <small>Use heavy Rubik typography.</small>
                  </span>

                  <input
                    type="checkbox"
                    checked={captionBold}
                    onChange={(event) => setCaptionBold(event.target.checked)}
                  />
                </label>

                <div className="caption-control-group">
                  <label className="editor-label">Caption color</label>

                  <div className="caption-color-grid">
                    {[
                      ["mrbeast", "MrBeast Yellow", "#FFD700"],
                      ["white", "Pure White", "#FFFFFF"],
                      ["green", "Neon Green", "#00FF66"],
                      ["cyan", "Cyan", "#00FFFF"],
                      ["pink", "Pink", "#FF66CC"],
                    ].map(([value, label, color]) => (
                      <button
                        key={value}
                        type="button"
                        className={captionColor === value ? "active" : ""}
                        onClick={() => setCaptionColor(value)}
                      >
                        <span
                          className="caption-color-dot"
                          style={{ background: color }}
                        />
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="editor-divider" />

                <label className="caption-toggle-row">
                  <span>
                    <strong>Sound effects</strong>
                    <small>Pop and whoosh synchronized with captions.</small>
                  </span>

                  <input
                    type="checkbox"
                    checked={soundEffects}
                    onChange={(event) => setSoundEffects(event.target.checked)}
                  />
                </label>

                {soundEffects && (
                  <>
                    <div className="editor-range-header">
                      <label>Sound effect volume</label>
                      <strong>{Math.round(sfxVolume * 100)}%</strong>
                    </div>

                    <input
                      className="editor-range"
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={sfxVolume}
                      onChange={(event) =>
                        setSfxVolume(Number(event.target.value))
                      }
                    />
                  </>
                )}
              </>
            )}
          </div>
          <div className="caption-style-section">
            <div className="caption-control-heading">
              <span>Text Outline</span>
              <small>outlins style</small>
            </div>

            <div className="caption-style-grid">
              <button
                type="button"
                className={`caption-style-option ${
                  captionOutline === "white_black" ? "active" : ""
                }`}
                onClick={() => setCaptionOutline("white_black")}
              >
                <span className="caption-style-preview white-black">TEXT</span>
                <span>White + Black</span>
              </button>

              <button
                type="button"
                className={`caption-style-option ${
                  captionOutline === "black_white" ? "active" : ""
                }`}
                onClick={() => setCaptionOutline("black_white")}
              >
                <span className="caption-style-preview black-white">TEXT</span>
                <span>Black + White</span>
              </button>
            </div>

            <div className="caption-control-heading">
              <span>Text Shadow</span>
              <small>shadow density</small>
            </div>

            <div className="caption-shadow-options">
              {[
                { value: "none", label: "none" },
                { value: "soft", label: "soft" },
                { value: "strong", label: "strong" },
                { value: "glow", label: "glow" },
              ].map((option) => (
                <button
                  type="button"
                  key={option.value}
                  className={`caption-shadow-option ${
                    captionShadow === option.value ? "active" : ""
                  }`}
                  onClick={() => setCaptionShadow(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="editor-output-info">
            <div>
              <span>Output resolution</span>
              <strong>1080 × 1920</strong>
            </div>
            <div>
              <span>Format</span>
              <strong>MP4</strong>
            </div>
            <div>
              <span>Aspect ratio</span>
              <strong>9:16</strong>
            </div>
          </div>

          <button
            className="primary-button editor-render-button"
            onClick={renderVideo}
            disabled={rendering || !selectedClip}
          >
            {rendering ? (
              <>
                <RefreshCw size={18} className="spin" />
                Rendering video...
              </>
            ) : (
              <>
                <Scissors size={18} />
                Render YouTube Short
              </>
            )}
          </button>
        </div>

        <div className="editor-preview-panel">
          <div className="editor-section-heading">
            <div>
              <span className="eyebrow">05 / OUTPUT</span>
              <h2>Render preview</h2>
            </div>

            {result && <ClipStatus status="completed" />}
          </div>

          <div className="caption-live-preview">
            <div className="caption-live-preview-video">
              <span className="caption-preview-tag">LIVE STYLE PREVIEW</span>

              <div
                className={`caption-demo-text caption-demo-${captionAnimation}`}
                style={{
                  color: colorPresets[captionColor] || "#FFD700",
                  fontFamily: "Rubik, sans-serif",
                  fontSize: `${previewFontSize}px`,
                  fontWeight: captionBold ? 900 : 500,
                  textAlign: "center",
                  textShadow: "0 3px 8px rgba(0,0,0,0.9)",
                  position: "absolute",
                  left: "8px",
                  right: "8px",
                  top:
                    captionPosition === "upper"
                      ? "25%"
                      : captionPosition === "center"
                        ? "50%"
                        : "75%",
                  transform: "translateY(-50%)",
                  lineHeight: 1.25,
                  textTransform: "uppercase",
                  opacity: subtitlesEnabled ? 1 : 0.35,
                }}
              >
                {captionDisplayMode === "word" ? (
                  <strong>ANYBODY</strong>
                ) : (
                  <>
                    DOES ANYBODY HAVE
                    <strong> LAY'S POV?</strong>
                  </>
                )}
              </div>
            </div>

            <div className="caption-preview-meta">
              <span>Rubik {captionBold ? "ExtraBold" : "Medium"}</span>
              <span>{effectiveCaptionFontSize}px</span>
              <span>{captionAnimation.replace("_", " + ")}</span>
              <span>
                {captionDisplayMode === "word" ? "Word by Word" : "Phrase"}
              </span>
              <span>{captionPosition}</span>
            </div>
          </div>

          {rendering ? (
            <div className="editor-rendering">
              <RefreshCw size={35} className="spin" />
              <strong>Processing your video</strong>
              <p>
                Downloading, tracking faces, transcribing and rendering your
                video. This may take a few minutes.
              </p>
            </div>
          ) : result && downloadUrl ? (
            <div className="editor-result">
              <video
                className="editor-video"
                src={downloadUrl}
                controls
                playsInline
              />

              <div className="editor-result-heading">
                <CheckCircle2 size={19} />
                <strong>Your Short is ready!</strong>
              </div>

              {result.subtitles && (
                <div className="editor-info caption-result-info">
                  <span>
                    Captions:{" "}
                    {result.subtitles.enabled ? "Enabled" : "Disabled"}
                    {" · "}
                    Font: {result.subtitles.font || "Rubik"}
                    {" · "}
                    Animation: {result.subtitles.animation || "none"}
                    {" · "}
                    SFX: {result.subtitles.sound_effects ? "On" : "Off"}
                  </span>
                </div>
              )}

              <div className="editor-result-stats">
                <div>
                  <span>Resolution</span>
                  <strong>{result.resolution || "1080x1920"}</strong>
                </div>

                <div>
                  <span>Tracking samples</span>
                  <strong>{result.tracking_samples ?? 0}</strong>
                </div>

                <div>
                  <span>Processed frames</span>
                  <strong>{formatNumber(result.frames_processed)}</strong>
                </div>

                <div>
                  <span>Crop mode</span>
                  <strong>{result.crop_mode || cropMode}</strong>
                </div>
              </div>

              {result.center_fallback && (
                <div className="editor-info">
                  <AlertCircle size={17} />
                  <span>
                    No faces were detected. The video was rendered using center
                    crop.
                  </span>
                </div>
              )}

              <a
                className="primary-button editor-download-button"
                href={downloadUrl}
                download={result.filename || "trendhunter_short.mp4"}
              >
                <Download size={18} />
                Download YouTube Short
              </a>
            </div>
          ) : (
            <div className="editor-empty-preview">
              <div className="editor-phone">
                <Play size={32} />
                <span>9:16</span>
              </div>

              <strong>Your video preview will appear here</strong>
              <p>
                Select a clip and configure your editing settings to generate
                your first Short.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

/* ---------------- MAIN APP ---------------- */

export default function App() {
  const [clips, setClips] = useState([]);
  const [streamers, setStreamers] = useState([]);
  const [health, setHealth] = useState(false);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [error, setError] = useState("");
  const [collectionSummary, setCollectionSummary] = useState(null);
  const [activePage, setActivePage] = useState("Overview");
  const [analytics, setAnalytics] = useState(null);

  async function loadData(showLoader = true) {
    if (showLoader) setLoading(true);
    setError("");

    try {
      const [
        healthResponse,
        clipsResponse,
        streamersResponse,
        analyticsResponse,
      ] = await Promise.all([
        fetch(`${API}/health`),
        fetch(`${API}/clips?limit=100`),
        fetch(`${API}/streamers`),
        fetch(`${API}/analytics/overview`),
      ]);

      setHealth(healthResponse.ok);

      if (!clipsResponse.ok) {
        throw new Error("Could not load clips.");
      }

      if (!streamersResponse.ok) {
        throw new Error("Could not load streamers.");
      }

      if (!analyticsResponse.ok) {
        throw new Error("Could not load analytics.");
      }

      const clipsData = await clipsResponse.json();
      const streamersData = await streamersResponse.json();
      const analyticsData = await analyticsResponse.json();

      setClips(getItems(clipsData));
      setStreamers(getItems(streamersData));
      setAnalytics(analyticsData);
    } catch (error) {
      setHealth(false);
      setError(
        error.message ||
          "Backend connection failed. Make sure FastAPI is running.",
      );
    } finally {
      setLoading(false);
    }
  }
  async function collectTwitch() {
    setCollecting(true);
    setError("");
    setCollectionSummary(null);

    try {
      const result = await request(
        `${API}/collect/twitch?lookback_hours=24&max_pages=20`,
        { method: "POST" },
      );

      setCollectionSummary(result.collection || result);
      await loadData(false);
    } catch (error) {
      setError(error.message || "Twitch collection failed.");
    } finally {
      setCollecting(false);
    }
  }

  async function updateClipStatus(id, status) {
    try {
      await request(`${API}/clips/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });

      setClips((current) =>
        current.map((clip) => (clip.id === id ? { ...clip, status } : clip)),
      );
    } catch (error) {
      setError(error.message || "Could not update clip status.");
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const pendingCount = clips.filter(
    (clip) => !["approved", "rejected"].includes(clip.status),
  ).length;

  const navigation = [
    { label: "Overview", icon: LayoutDashboard },
    { label: "Discover", icon: Compass },
    { label: "Clip library", icon: Clapperboard },
    { label: "Editor", icon: Scissors },
    { label: "Streamers", icon: Users },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Activity size={23} />
          </div>
          <div>
            <strong>
              trendhunter<span>.</span>
            </strong>
            <small>CREATOR INTELLIGENCE</small>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <nav>
          {navigation.map(({ label, icon: Icon }) => (
            <button
              key={label}
              className={`nav-item ${activePage === label ? "active" : ""}`}
              onClick={() => setActivePage(label)}
            >
              <Icon size={18} />
              <span>{label}</span>
              {label === "Discover" && pendingCount > 0 && (
                <b>{pendingCount}</b>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <span className={`connection-dot ${health ? "online" : ""}`} />
          <div>
            <strong>{health ? "API Connected" : "API Offline"}</strong>
            <small>TrendHunter backend</small>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="topbar-label">TRENDHUNTER STUDIO</span>
            <strong>{activePage}</strong>
          </div>

          <div className="topbar-right">
            <span className={`connection-pill ${health ? "online" : ""}`}>
              <i /> {health ? "System online" : "Disconnected"}
            </span>
            <button
              className="icon-button"
              title="Refresh"
              onClick={() => loadData()}
              disabled={loading}
            >
              <RefreshCw size={17} className={loading ? "spin" : ""} />
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <AlertCircle size={18} />
            <span>{error}</span>
            <button onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}

        {activePage === "Streamers" ? (
          <StreamersPage
            streamers={streamers}
            onRefresh={() => loadData(false)}
            setError={setError}
          />
        ) : activePage === "Editor" ? (
          <EditorPage clips={clips} setError={setError} />
        ) : activePage === "Discover" || activePage === "Clip library" ? (
          <ClipLibrary
            clips={clips}
            loading={loading}
            collecting={collecting}
            onCollect={collectTwitch}
            onRefresh={() => loadData()}
            onStatusChange={updateClipStatus}
            collectionSummary={collectionSummary}
            analytics={analytics}
          />
        ) : (
          <section className="page-content">
            <div className="page-heading">
              <div>
                <span className="eyebrow">
                  <i className="live-dot" /> LIVE WORKSPACE
                </span>
                <h1>
                  Overview<span>.</span>
                </h1>
                <p>Your Twitch clip discovery workspace.</p>
              </div>

              <button
                className="primary-button"
                onClick={collectTwitch}
                disabled={collecting}
              >
                <Radio size={16} />
                {collecting ? "Collecting..." : "Collect Twitch clips"}
              </button>
            </div>

            <div className="overview-grid">
              <div className="overview-card">
                <span>Total Twitch clips</span>
                <strong>{formatNumber(analytics?.twitch?.total ?? 0)}</strong>
                <small>All clips in database</small>
              </div>

              <div className="overview-card">
                <span>Total Twitch views</span>
                <strong>
                  {formatNumber(analytics?.twitch?.total_views ?? 0)}
                </strong>
                <small>Combined clip views</small>
              </div>

              <div className="overview-card">
                <span>Waiting for review</span>
                <strong>{formatNumber(analytics?.twitch?.pending ?? 0)}</strong>
                <small>Clips to review</small>
              </div>

              <div className="overview-card">
                <span>Active streamers</span>
                <strong>
                  {formatNumber(analytics?.streamers?.active ?? 0)}
                </strong>
                <small>Currently monitored</small>
              </div>
            </div>

            <div className="overview-section">
              <div>
                <h2>Recent Twitch clips</h2>
                <p>Latest clips collected from your channels.</p>
              </div>

              <button
                className="secondary-button"
                onClick={() => setActivePage("Clip library")}
              >
                Open clip library
              </button>
            </div>

            <div className="overview-clip-list">
              {clips
                .filter((clip) => clip.platform === "twitch")
                .slice(0, 5)
                .map((clip) => (
                  <div className="overview-clip-row" key={clip.id}>
                    <div>
                      <strong>{clip.title || "Untitled clip"}</strong>
                      <span>
                        {clip.creator || clip.streamer_name || "Twitch"}
                      </span>
                    </div>
                    <Score value={clip.viral_score} />
                  </div>
                ))}

              {!loading && clips.length === 0 && (
                <div className="empty-library">
                  <Clapperboard size={30} />
                  <strong>No clips collected yet</strong>
                  <p>Add streamers and collect Twitch clips to get started.</p>
                </div>
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
