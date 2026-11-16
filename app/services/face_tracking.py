
import cv2
import math
from pathlib import Path
from statistics import pstdev


BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_DIR / "models" / "face_detection_yunet.onnx"


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def smooth_points(points, radius=2):
    if len(points) < 3:
        return points

    smoothed = []
    numeric_fields = ("x", "y", "width", "height")

    for index, point in enumerate(points):
        start = max(0, index - radius)
        end = min(len(points), index + radius + 1)
        nearby = points[start:end]

        updated = dict(point)

        for field in numeric_fields:
            updated[field] = sum(
                item[field] for item in nearby
            ) / len(nearby)

        smoothed.append(updated)

    return smoothed


def build_face_tracks(
    frames,
    max_distance=0.16,
    max_size_ratio=2.2,
    max_missing=2,
):
    """
    Connects face detections across frames.

    Each track represents one continuously observed face.
    Faces that suddenly appear in another scene should not
    replace an already established track.
    """

    tracks = []
    next_track_id = 0

    for frame_index, frame_data in enumerate(frames):
        detections = frame_data["faces"]
        used_tracks = set()

        possible_matches = []

        for track in tracks:
            last_observation = track["observations"][-1]
            missing = frame_index - last_observation["index"] - 1

            if missing > max_missing:
                continue

            for detection_index, detection in enumerate(detections):
                previous = last_observation["face"]

                distance = math.hypot(
                    detection["x"] - previous["x"],
                    detection["y"] - previous["y"],
                )

                previous_size = max(
                    previous["width"] * previous["height"],
                    0.0001,
                )

                current_size = max(
                    detection["width"] * detection["height"],
                    0.0001,
                )

                size_ratio = max(
                    current_size / previous_size,
                    previous_size / current_size,
                )

                if distance > max_distance:
                    continue

                if size_ratio > max_size_ratio:
                    continue

                score = distance + abs(math.log(size_ratio)) * 0.025

                possible_matches.append(
                    (score, track, detection_index)
                )

        possible_matches.sort(key=lambda item: item[0])

        assigned_detections = set()

        for _, track, detection_index in possible_matches:
            if track["id"] in used_tracks:
                continue

            if detection_index in assigned_detections:
                continue

            detection = detections[detection_index]

            track["observations"].append({
                "index": frame_index,
                "time": frame_data["time"],
                "face": detection,
            })

            used_tracks.add(track["id"])
            assigned_detections.add(detection_index)

        for detection_index, detection in enumerate(detections):
            if detection_index in assigned_detections:
                continue

            tracks.append({
                "id": next_track_id,
                "observations": [{
                    "index": frame_index,
                    "time": frame_data["time"],
                    "face": detection,
                }],
            })

            next_track_id += 1

    return tracks


def score_face_track(track, total_samples):
    observations = track["observations"]

    if not observations:
        return 0.0

    count = len(observations)

    first_index = observations[0]["index"]
    last_index = observations[-1]["index"]

    span = max(1, last_index - first_index + 1)

    coverage = count / max(total_samples, 1)
    continuity = count / span

    centers_x = [
        item["face"]["x"]
        for item in observations
    ]

    centers_y = [
        item["face"]["y"]
        for item in observations
    ]

    movement_x = pstdev(centers_x) if len(centers_x) > 1 else 0
    movement_y = pstdev(centers_y) if len(centers_y) > 1 else 0

    movement = math.sqrt(
        movement_x ** 2 + movement_y ** 2
    )

    stability = math.exp(-movement * 8)

    average_area = sum(
        item["face"]["width"] * item["face"]["height"]
        for item in observations
    ) / count

    # A small webcam overlay can be more relevant than
    # a large face inside the game or reaction video.
    size_preference = 1.0 - min(average_area / 0.20, 1.0)

    score = (
        coverage * 0.55
        + continuity * 0.20
        + stability * 0.20
        + size_preference * 0.05
    )

    return score


def select_locked_track(
    tracks,
    total_samples,
    min_track_samples=3,
):
    valid_tracks = [
        track
        for track in tracks
        if len(track["observations"]) >= min_track_samples
    ]

    if not valid_tracks:
        return None

    return max(
        valid_tracks,
        key=lambda track: score_face_track(
            track,
            total_samples,
        ),
    )


def create_tracking_points(
    track,
    frames,
    max_hold_samples=2,
):
    observations = {
        item["index"]: item
        for item in track["observations"]
    }

    first_index = min(observations)
    last_index = max(observations)

    points = []
    last_face = None
    last_seen_index = None

    for index in range(first_index, last_index + 1):
        frame_time = frames[index]["time"]

        if index in observations:
            observation = observations[index]
            last_face = observation["face"]
            last_seen_index = index
            confidence = last_face["confidence"]

        elif (
            last_face is not None
            and last_seen_index is not None
            and index - last_seen_index <= max_hold_samples
        ):
            confidence = 0.0

        else:
            continue

        points.append({
            "time": round(frame_time, 3),
            "x": last_face["x"],
            "y": last_face["y"],
            "width": last_face["width"],
            "height": last_face["height"],
            "confidence": round(confidence, 3),
        })

    return points


def detect_faces_in_video(
    video_path,
    sample_interval=0.5,
    max_width=960,
    confidence_threshold=0.75,
    max_tracking_distance=0.16,
    max_missing_samples=2,
    min_track_samples=3,
    target_region=None,
):
    """
    Detects faces and locks onto the most persistent,
    spatially stable face track.

    target_region:
        Optional normalized region (x, y, width, height).
        Example: (0.65, 0.65, 0.35, 0.35)
        This restricts face detection to a known webcam area.
    """

    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"YuNet model not found: {MODEL_PATH}"
        )

    detector = cv2.FaceDetectorYN.create(
        str(MODEL_PATH),
        "",
        (320, 320),
        confidence_threshold,
        0.3,
        5000,
    )

    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        raise RuntimeError("Could not open video.")

    fps = capture.get(cv2.CAP_PROP_FPS)
    total_frames = int(
        capture.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    original_width = int(
        capture.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    original_height = int(
        capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    if (
        fps <= 0
        or original_width <= 0
        or original_height <= 0
    ):
        capture.release()
        raise RuntimeError("Invalid video metadata.")

    duration = total_frames / fps
    frame_step = max(1, int(fps * sample_interval))

    frames = []
    frame_index = 0

    try:
        while True:
            success, frame = capture.read()

            if not success:
                break

            if frame_index % frame_step == 0:
                height, width = frame.shape[:2]

                scale = min(1.0, max_width / width)

                if scale < 1.0:
                    resized = cv2.resize(
                        frame,
                        (
                            int(width * scale),
                            int(height * scale),
                        ),
                    )
                else:
                    resized = frame

                image_height, image_width = resized.shape[:2]

                detector.setInputSize(
                    (image_width, image_height)
                )

                _, faces = detector.detect(resized)

                timestamp = frame_index / fps
                candidates = []

                if faces is not None:
                    for face in faces:
                        x, y, face_width, face_height = face[:4]

                        center_x = x + face_width / 2
                        center_y = y + face_height / 2

                        normalized_x = center_x / image_width
                        normalized_y = center_y / image_height

                        if target_region is not None:
                            rx, ry, rw, rh = target_region

                            if not (
                                rx <= normalized_x <= rx + rw
                                and ry <= normalized_y <= ry + rh
                            ):
                                continue

                        candidates.append({
                            "x": clamp(normalized_x, 0.0, 1.0),
                            "y": clamp(normalized_y, 0.0, 1.0),
                            "width": clamp(
                                face_width / image_width,
                                0.0,
                                1.0,
                            ),
                            "height": clamp(
                                face_height / image_height,
                                0.0,
                                1.0,
                            ),
                            "confidence": float(face[-1]),
                        })

                frames.append({
                    "time": round(timestamp, 3),
                    "faces": candidates,
                })

            frame_index += 1

    finally:
        capture.release()

    if not frames:
        return {
            "success": False,
            "message": "No frames could be sampled.",
            "duration": round(duration, 2),
            "video_width": original_width,
            "video_height": original_height,
            "fps": round(fps, 2),
            "detected_samples": 0,
            "tracking_points": [],
        }

    tracks = build_face_tracks(
        frames,
        max_distance=max_tracking_distance,
        max_missing=max_missing_samples,
    )

    locked_track = select_locked_track(
        tracks,
        len(frames),
        min_track_samples=min_track_samples,
    )

    if locked_track is None:
        return {
            "success": False,
            "message": "No stable face track found.",
            "duration": round(duration, 2),
            "video_width": original_width,
            "video_height": original_height,
            "fps": round(fps, 2),
            "detected_samples": 0,
            "total_samples": len(frames),
            "tracking_points": [],
        }

    points = create_tracking_points(
        locked_track,
        frames,
        max_hold_samples=max_missing_samples,
    )

    if not points:
        return {
            "success": False,
            "message": "Could not create tracking points.",
            "duration": round(duration, 2),
            "video_width": original_width,
            "video_height": original_height,
            "fps": round(fps, 2),
            "detected_samples": 0,
            "tracking_points": [],
        }

    points = smooth_points(points, radius=2)

    return {
        "success": True,
        "duration": round(duration, 2),
        "video_width": original_width,
        "video_height": original_height,
        "fps": round(fps, 2),
        "detected_samples": len(locked_track["observations"]),
        "total_samples": len(frames),
        "selected_track_id": locked_track["id"],
        "selected_track_score": round(
            score_face_track(locked_track, len(frames)),
            3,
        ),
        "tracking_points": points,
    }
