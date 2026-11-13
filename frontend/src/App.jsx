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
  Zap,
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
  onReset,
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
            className="secondary-button"
            onClick={onReset}
            disabled={loading || collecting}
          >
            <Trash2 size={16} />
            Reset Clip List
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

  // GTA Gameplay Split
  const [gtaGameplayFile, setGtaGameplayFile] = useState(null);
  const [gtaGameplayUrl, setGtaGameplayUrl] = useState("");

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

  // Background Music
  const [bgMusicEnabled, setBgMusicEnabled] = useState(true);
  const [bgMusicTrack, setBgMusicTrack] = useState("bedtime_baby_lullabies");
  const [bgMusicVolume, setBgMusicVolume] = useState(0.08);
  const [bgMusicFadeIn, setBgMusicFadeIn] = useState(2);
  const [bgMusicFadeOut, setBgMusicFadeOut] = useState(3);

  // Sound Effects
  const [soundEffects, setSoundEffects] = useState(true);
  const [soundEffectTracks, setSoundEffectTracks] = useState([]);
  const [newSfxTime, setNewSfxTime] = useState("00:00.000");
  const [newSfxVolume, setNewSfxVolume] = useState(0.25);
  const [sfxError, setSfxError] = useState("");
  const [impactIntensity, setImpactIntensity] = useState(0.8);

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

  function parseSfxTime(value) {
    const match = value.match(/^(\d{2}):([0-5]\d)\.(\d{3})$/);

    if (!match) return null;

    const minutes = Number(match[1]);
    const seconds = Number(match[2]);
    const milliseconds = Number(match[3]);

    return minutes * 60 + seconds + milliseconds / 1000;
  }

  function addSoundEffects(event) {
    const files = Array.from(event.target.files || []);

    if (!files.length) return;

    const audioFiles = files.filter((file) => file.type.startsWith("audio/"));

    if (!audioFiles.length) {
      setSfxError("Please select valid audio files.");
      event.target.value = "";
      return;
    }

    const newTracks = audioFiles.map((file) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      name: file.name,
      file,
      url: URL.createObjectURL(file),
      startTime: newSfxTime,
      volume: newSfxVolume,
      visualImpact: true,
    }));

    setSoundEffectTracks((previous) => [...previous, ...newTracks]);
    setSfxError("");
    setSoundEffects(true);

    event.target.value = "";
  }

  function removeSoundEffect(id) {
    setSoundEffectTracks((previous) => {
      const track = previous.find((item) => item.id === id);

      if (track?.url) {
        URL.revokeObjectURL(track.url);
      }

      return previous.filter((item) => item.id !== id);
    });
  }

  function updateSoundEffect(id, field, value) {
    setSoundEffectTracks((previous) =>
      previous.map((track) =>
        track.id === id ? { ...track, [field]: value } : track,
      ),
    );
  }
  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = () => {
        const result = reader.result;

        if (typeof result !== "string") {
          reject(new Error("Could not read audio file."));
          return;
        }

        resolve(result.split(",")[1]);
      };

      reader.onerror = () => reject(new Error("Failed to read audio file."));
      reader.readAsDataURL(file);
    });
  }

  async function prepareSoundEffectTracks() {
    return Promise.all(
      soundEffectTracks.map(async (track) => {
        const startTime = parseSfxTime(track.startTime);

        if (startTime === null) {
          throw new Error(`Invalid start time for "${track.name}".`);
        }

        return {
          id: track.id,
          name: track.name,
          file_name: track.file.name,
          file_data: await fileToBase64(track.file),
          start_time: startTime,
          volume: Number(track.volume),
          visual_impact: Boolean(track.visualImpact),
        };
      }),
    );
  }
  async function renderVideo() {
    if (!selectedClip) {
      setError("Please select a Twitch clip first.");
      return;
    }

    if (soundEffects && soundEffectTracks.length > 0) {
      const invalidTrack = soundEffectTracks.find(
        (track) => parseSfxTime(track.startTime) === null,
      );

      if (invalidTrack) {
        setError(`Invalid start time for "${invalidTrack.name}".`);
        return;
      }
    }

    if (cropMode === "gta_split" && !gtaGameplayFile) {
      setError("Please upload a GTA gameplay video.");
      setRendering(false);
      return;
    }

    const gtaGameplayData =
      cropMode === "gta_split" ? await fileToBase64(gtaGameplayFile) : null;

    setRendering(true);
    setResult(null);
    setError("");

    try {
      const preparedTracks =
        soundEffects && soundEffectTracks.length > 0
          ? await prepareSoundEffectTracks()
          : [];

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

          gta_gameplay_data: gtaGameplayData,
          gta_gameplay_file_name: gtaGameplayFile?.name || null,
          // Background Music
          bg_music_enabled: bgMusicEnabled,
          bg_music_track: bgMusicTrack,
          bg_music_volume: Number(bgMusicVolume),
          bg_music_fade_in: Number(bgMusicFadeIn),
          bg_music_fade_out: Number(bgMusicFadeOut),

          // Sound Effects
          sound_effects: soundEffects,
          sfx_volume: Number(newSfxVolume),
          sfx_tracks: preparedTracks,

          // Visual Impact FX
          visual_impact_enabled: preparedTracks.some(
            (track) => track.visual_impact,
          ),
          impact_intensity: Number(impactIntensity),
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
    <section className="page-content editor-page">
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
        {/* EDITOR SETTINGS */}
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

          {/* FRAMING */}
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
              className={cropMode === "gta_split" ? "selected" : ""}
              onClick={() => setCropMode("gta_split")}
            >
              <Clapperboard size={20} />
              <strong>GTA Split</strong>
              <small>Streamer + GTA gameplay</small>
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

          {cropMode === "gta_split" && (
            <div className="split-controls">
              <div className="editor-info">
                <Clapperboard size={18} />
                <span>
                  Upload a GTA gameplay video. The streamer stays in the top
                  panel and GTA gameplay plays below.
                </span>
              </div>

              <label className="editor-label">GTA Gameplay Video</label>

              <input
                className="editor-select"
                type="file"
                accept="video/*"
                onChange={(event) => {
                  const file = event.target.files?.[0];

                  if (!file) return;

                  if (gtaGameplayUrl) {
                    URL.revokeObjectURL(gtaGameplayUrl);
                  }

                  setGtaGameplayFile(file);
                  setGtaGameplayUrl(URL.createObjectURL(file));
                  setResult(null);
                }}
              />

              {gtaGameplayUrl && (
                <div className="editor-source-card">
                  <video
                    src={gtaGameplayUrl}
                    controls
                    muted
                    playsInline
                    style={{
                      width: "100%",
                      maxHeight: "180px",
                      objectFit: "cover",
                    }}
                  />

                  <div>
                    <strong>{gtaGameplayFile?.name}</strong>
                    <span>GTA gameplay selected</span>
                  </div>
                </div>
              )}

              <div className="split-layout-demo">
                <div className="split-camera-demo">
                  <span>STREAMER CAMERA</span>
                </div>
                <div className="split-game-demo">
                  <span>GTA GAMEPLAY</span>
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

              <div className="editor-info">
                <Activity size={17} />
                <span>
                  GTA gameplay loops automatically if it is shorter than the
                  streamer clip. Its original audio is not included in the final
                  video.
                </span>
              </div>
            </div>
          )}

          <div className="editor-divider" />

          {/* VIDEO ENHANCEMENT */}
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

          {/* SUBTITLES */}
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
              </>
            )}
          </div>

          {/* CAPTION STYLE */}
          <div className="caption-style-section">
            <div className="caption-control-heading">
              <span>Text Outline</span>
              <small>Outline style</small>
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
              <small>Shadow density</small>
            </div>

            <div className="caption-shadow-options">
              {[
                { value: "none", label: "None" },
                { value: "soft", label: "Soft" },
                { value: "strong", label: "Strong" },
                { value: "glow", label: "Glow" },
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

          {/* AUDIO STUDIO - INDEPENDENT FROM SUBTITLES */}
          <div className="editor-divider" />

          <div className="audio-studio">
            <div className="audio-studio-heading">
              <div>
                <span className="eyebrow">05 / AUDIO PRODUCTION</span>
                <h3>Audio Studio</h3>
                <p>Manage music, sound effects and audio levels.</p>
              </div>
              <span className="audio-studio-icon">
                <Activity size={21} />
              </span>
            </div>

            {/* BACKGROUND MUSIC */}
            <div className="audio-layer-card">
              <div className="audio-layer-header">
                <div className="audio-layer-title">
                  <span className="audio-layer-number">01</span>
                  <div>
                    <strong>Background Music</strong>
                    <small>Independent background music layer</small>
                  </div>
                </div>

                <label className="audio-switch">
                  <input
                    type="checkbox"
                    checked={bgMusicEnabled}
                    onChange={(event) =>
                      setBgMusicEnabled(event.target.checked)
                    }
                  />
                  <span />
                </label>
              </div>

              <div
                className={`audio-layer-content ${!bgMusicEnabled ? "disabled" : ""}`}
              >
                <label className="editor-label">Music track</label>

                <select
                  className="editor-select"
                  value={bgMusicTrack}
                  onChange={(event) => setBgMusicTrack(event.target.value)}
                  disabled={!bgMusicEnabled}
                >
                  <option value="bedtime_baby_lullabies">
                    Ts Pmo — Bedtime Baby Lullabies
                  </option>
                </select>

                <div className="audio-track-info">
                  <div className="audio-track-art">
                    <Activity size={22} />
                  </div>
                  <div className="audio-track-details">
                    <strong>Bedtime Baby Lullabies</strong>
                    <small>Selected background track</small>
                  </div>
                  <span className="audio-track-status">
                    {bgMusicEnabled ? "ACTIVE" : "OFF"}
                  </span>
                </div>

                <div className="audio-control">
                  <div className="editor-range-header">
                    <label>Music volume</label>
                    <strong>{Math.round(bgMusicVolume * 100)}%</strong>
                  </div>

                  <input
                    className="editor-range"
                    type="range"
                    min="0"
                    max="0.5"
                    step="0.01"
                    value={bgMusicVolume}
                    disabled={!bgMusicEnabled}
                    onChange={(event) =>
                      setBgMusicVolume(Number(event.target.value))
                    }
                  />
                </div>

                <div className="audio-fade-grid">
                  <div>
                    <label className="editor-label">Fade In</label>
                    <div className="audio-number-input">
                      <input
                        type="number"
                        min="0"
                        max="15"
                        step="0.5"
                        value={bgMusicFadeIn}
                        disabled={!bgMusicEnabled}
                        onChange={(event) =>
                          setBgMusicFadeIn(Number(event.target.value))
                        }
                      />
                      <span>sec</span>
                    </div>
                  </div>

                  <div>
                    <label className="editor-label">Fade Out</label>
                    <div className="audio-number-input">
                      <input
                        type="number"
                        min="0"
                        max="30"
                        step="0.5"
                        value={bgMusicFadeOut}
                        disabled={!bgMusicEnabled}
                        onChange={(event) =>
                          setBgMusicFadeOut(Number(event.target.value))
                        }
                      />
                      <span>sec</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* STREAMER AUDIO */}
            <div className="audio-layer-card audio-original-layer">
              <div className="audio-layer-header">
                <div className="audio-layer-title">
                  <span className="audio-layer-number">02</span>
                  <div>
                    <strong>Streamer Audio</strong>
                    <small>Original audio from the source clip</small>
                  </div>
                </div>
                <span className="audio-original-badge">ORIGINAL</span>
              </div>

              <div className="audio-original-info">
                <Activity size={18} />
                <span>
                  Original streamer audio remains independent. Disabling
                  background music will never mute the source audio.
                </span>
              </div>
            </div>

            {/* SOUND EFFECTS */}
            <div className="audio-layer-card">
              <div className="audio-layer-header">
                <div className="audio-layer-title">
                  <span className="audio-layer-number">03</span>
                  <div>
                    <strong>Sound Effects</strong>
                    <small>
                      Multiple effects with individual timing and volume
                    </small>
                  </div>
                </div>

                <label className="audio-switch">
                  <input
                    type="checkbox"
                    checked={soundEffects}
                    onChange={(event) => setSoundEffects(event.target.checked)}
                  />
                  <span />
                </label>
              </div>

              {soundEffects && (
                <div className="audio-layer-content">
                  <div className="sfx-upload-area">
                    <input
                      id="sfx-upload-input"
                      type="file"
                      accept="audio/*"
                      multiple
                      onChange={addSoundEffects}
                    />

                    <label htmlFor="sfx-upload-input">
                      <span className="sfx-upload-icon">
                        <Plus size={23} />
                      </span>
                      <strong>Add sound effects</strong>
                      <small>Upload MP3, WAV, M4A or other audio files</small>
                    </label>
                  </div>

                  {sfxError && (
                    <div className="sfx-error">
                      <AlertCircle size={15} />
                      {sfxError}
                    </div>
                  )}

                  <div className="sfx-default-controls">
                    <div>
                      <label className="editor-label">Default start time</label>
                      <input
                        className="editor-select sfx-time-input"
                        type="text"
                        placeholder="00:12.500"
                        value={newSfxTime}
                        onChange={(event) => setNewSfxTime(event.target.value)}
                      />
                    </div>

                    <div>
                      <div className="editor-range-header">
                        <label>Default volume</label>
                        <strong>{Math.round(newSfxVolume * 100)}%</strong>
                      </div>
                      <input
                        className="editor-range"
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={newSfxVolume}
                        onChange={(event) =>
                          setNewSfxVolume(Number(event.target.value))
                        }
                      />
                    </div>
                  </div>

                  {soundEffectTracks.length === 0 ? (
                    <div className="sfx-empty">
                      <Activity size={25} />
                      <strong>No sound effects added</strong>
                      <span>
                        Upload audio files to build your effects timeline.
                      </span>
                    </div>
                  ) : (
                    <div className="sfx-track-list">
                      <div className="sfx-list-heading">
                        <strong>Added effects</strong>
                        <span>{soundEffectTracks.length} tracks</span>
                      </div>
                      {soundEffectTracks.map((track, index) => (
                        <div className="sfx-track-card" key={track.id}>
                          <div className="sfx-track-top">
                            <div className="sfx-track-file">
                              <span className="sfx-track-index">
                                {String(index + 1).padStart(2, "0")}
                              </span>
                              <div>
                                <strong title={track.name}>{track.name}</strong>
                                <small>Audio effect</small>
                              </div>
                            </div>

                            <button
                              type="button"
                              className="sfx-remove-button"
                              onClick={() => removeSoundEffect(track.id)}
                              title="Remove effect"
                            >
                              <Trash2 size={17} />
                            </button>
                          </div>

                          <audio
                            className="sfx-audio-preview"
                            src={track.url}
                            controls
                            preload="metadata"
                          />
                          <label className="visual-impact-track-toggle">
                            <span>
                              <strong>Flash / Visual Impact</strong>
                              <small>
                                Enable or disable the flash for this sound
                                effect
                              </small>
                            </span>

                            <input
                              type="checkbox"
                              checked={Boolean(track.visualImpact)}
                              onChange={(event) =>
                                updateSoundEffect(
                                  track.id,
                                  "visualImpact",
                                  event.target.checked,
                                )
                              }
                            />
                          </label>
                          <div className="sfx-track-controls">
                            <div>
                              <label className="editor-label">Start time</label>
                              <input
                                className="editor-select sfx-time-input"
                                type="text"
                                value={track.startTime}
                                placeholder="00:12.500"
                                onChange={(event) =>
                                  updateSoundEffect(
                                    track.id,
                                    "startTime",
                                    event.target.value,
                                  )
                                }
                              />

                              {parseSfxTime(track.startTime) === null && (
                                <small className="sfx-field-error">
                                  Use MM:SS.mmm format
                                </small>
                              )}
                            </div>

                            <div>
                              <div className="editor-range-header">
                                <label>Volume</label>
                                <strong>
                                  {Math.round(track.volume * 100)}%
                                </strong>
                              </div>
                              <input
                                className="editor-range"
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={track.volume}
                                onChange={(event) =>
                                  updateSoundEffect(
                                    track.id,
                                    "volume",
                                    Number(event.target.value),
                                  )
                                }
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                      <div className="visual-impact-panel">
                        <div className="visual-impact-header">
                          <div className="visual-impact-title">
                            <span className="visual-impact-icon">
                              <Zap size={19} />
                            </span>

                            <div>
                              <strong>Visual Impact FX</strong>
                              <small>
                                Configure flash separately for each sound effect
                              </small>
                            </div>
                          </div>

                          <span className="visual-impact-mode-badge">
                            PER EFFECT
                          </span>
                        </div>

                        <div>
                          <div className="editor-range-header">
                            <label>Glow intensity</label>
                            <strong>
                              {Math.round(impactIntensity * 100)}%
                            </strong>
                          </div>

                          <input
                            className="editor-range"
                            type="range"
                            min="0.2"
                            max="1"
                            step="0.05"
                            value={impactIntensity}
                            onChange={(event) =>
                              setImpactIntensity(Number(event.target.value))
                            }
                          />

                          <small className="caption-help-text">
                            Each sound effect can independently trigger the
                            visual impact.
                          </small>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* MIXER SUMMARY */}
            <div className="audio-mixer-summary">
              <div className="audio-mixer-heading">
                <Activity size={18} />
                <strong>Final Audio Mixer</strong>
              </div>

              <div className="audio-mixer-row">
                <span>Streamer audio</span>
                <strong className="mixer-active">Independent</strong>
              </div>

              <div className="audio-mixer-row">
                <span>Background music</span>
                <strong
                  className={bgMusicEnabled ? "mixer-active" : "mixer-muted"}
                >
                  {bgMusicEnabled
                    ? `${Math.round(bgMusicVolume * 100)}%`
                    : "Disabled"}
                </strong>
              </div>

              <div className="audio-mixer-row">
                <span>Sound effects</span>
                <strong
                  className={soundEffects ? "mixer-active" : "mixer-muted"}
                >
                  {soundEffects
                    ? `${soundEffectTracks.length} tracks`
                    : "Disabled"}
                </strong>
              </div>

              <p>
                All audio layers will be mixed independently in the final video.
              </p>
            </div>
          </div>

          {/* OUTPUT FORMAT */}
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
        </div>

        {/* PREVIEW AND RENDER RESULT - MOVED TO BOTTOM */}
        <div className="editor-preview-panel">
          <div className="editor-section-heading">
            <div>
              <span className="eyebrow">06 / OUTPUT</span>
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
                  textShadow:
                    captionShadow === "none"
                      ? "none"
                      : captionShadow === "soft"
                        ? "0 2px 5px rgba(0,0,0,0.65)"
                        : captionShadow === "strong"
                          ? "0 4px 10px rgba(0,0,0,0.95)"
                          : `0 0 5px ${colorPresets[captionColor] || "#FFD700"},
           0 0 12px ${colorPresets[captionColor] || "#FFD700"},
           0 0 22px ${colorPresets[captionColor] || "#FFD700"}`,
                  WebkitTextStroke:
                    captionOutline === "black_white"
                      ? "2px #FFFFFF"
                      : "2px #000000",
                  paintOrder: "stroke fill",
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

        {/* RENDER BUTTON - AFTER PREVIEW */}
        <div className="editor-bottom-actions">
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
  async function resetClips() {
    if (
      !window.confirm(
        "Are you sure you want to delete all collected clips? This action cannot be undone.",
      )
    ) {
      return;
    }

    try {
      setError("");

      const data = await request(`${API}/clips/reset`, {
        method: "DELETE",
      });

      setCollectionSummary(null);

      await loadData(false);

      alert(
        `Clip list reset successfully. ${data.deleted_clips ?? 0} clips deleted.`,
      );
    } catch (error) {
      setError(error.message || "Could not reset clip list.");
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
            onReset={resetClips}
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

              <div className="page-actions">
                <button
                  className="secondary-button"
                  onClick={async () => {
                    const confirmed = window.confirm(
                      "Are you sure you want to delete all collected clips? This action cannot be undone.",
                    );

                    if (!confirmed) return;

                    try {
                      const response = await fetch(
                        "http://127.0.0.1:8000/clips/reset",
                        {
                          method: "DELETE",
                        },
                      );

                      const data = await response.json();

                      if (!response.ok) {
                        throw new Error(
                          data.detail || "Failed to reset clips.",
                        );
                      }

                      alert(
                        `Clip list reset successfully. ${data.deleted_clips} clips deleted.`,
                      );
                      window.location.reload();
                    } catch (error) {
                      alert(error.message || "Could not reset clip list.");
                    }
                  }}
                >
                  <Trash2 size={16} />
                  Reset Clip List
                </button>

                <button
                  className="primary-button"
                  onClick={collectTwitch}
                  disabled={collecting}
                >
                  <Radio size={16} />
                  {collecting ? "Collecting..." : "Collect Twitch clips"}
                </button>
              </div>
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
