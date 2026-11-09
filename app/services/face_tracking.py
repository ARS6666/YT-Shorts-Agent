
import cv2
import math
from pathlib import Path


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


def select_face(faces, previous_center=None):
    if faces is None or len(faces) == 0:
        return None

    candidates = []

    for face in faces:
        x, y, width, height = face[:4]
        confidence = float(face[-1])

        center_x = x + width / 2
        center_y = y + height / 2
        area = width * height

        candidates.append({
            "x": center_x,
            "y": center_y,
            "left": x,
            "top": y,
            "width": width,
            "height": height,
            "area": area,
            "confidence": confidence,
        })

    if previous_center is None:
        return max(candidates, key=lambda item: item["area"])

    def candidate_score(item):
        distance = math.hypot(
            item["x"] - previous_center[0],
            item["y"] - previous_center[1],
        )

        return (
            distance / max(item["area"] ** 0.5, 1)
            - math.log1p(item["area"]) * 0.15
        )

    return min(candidates, key=candidate_score)


def detect_faces_in_video(
    video_path,
    sample_interval=0.5,
    max_width=960,
    confidence_threshold=0.75,
):
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"YuNet model not found: {MODEL_PATH}")

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
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    original_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if fps <= 0 or original_width <= 0 or original_height <= 0:
        capture.release()
        raise RuntimeError("Invalid video metadata.")

    duration = total_frames / fps
    frame_step = max(1, int(fps * sample_interval))

    points = []
    previous_center = None
    previous_bbox = None
    frame_index = 0
    detected_count = 0

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

                detector.setInputSize(
                    (resized.shape[1], resized.shape[0])
                )

                _, faces = detector.detect(resized)
                selected = select_face(faces, previous_center)
                timestamp = frame_index / fps

                if selected:
                    image_width = resized.shape[1]
                    image_height = resized.shape[0]

                    previous_center = (
                        selected["x"],
                        selected["y"],
                    )
                    previous_bbox = {
                        "width": selected["width"] / image_width,
                        "height": selected["height"] / image_height,
                    }

                    points.append({
                        "time": round(timestamp, 3),
                        "x": clamp(
                            selected["x"] / image_width, 0.0, 1.0
                        ),
                        "y": clamp(
                            selected["y"] / image_height, 0.0, 1.0
                        ),
                        "width": clamp(
                            selected["width"] / image_width, 0.0, 1.0
                        ),
                        "height": clamp(
                            selected["height"] / image_height, 0.0, 1.0
                        ),
                        "confidence": round(
                            selected["confidence"], 3
                        ),
                    })

                    detected_count += 1

                elif previous_center is not None:
                    image_width = resized.shape[1]
                    image_height = resized.shape[0]

                    points.append({
                        "time": round(timestamp, 3),
                        "x": clamp(
                            previous_center[0] / image_width, 0.0, 1.0
                        ),
                        "y": clamp(
                            previous_center[1] / image_height, 0.0, 1.0
                        ),
                        "width": previous_bbox["width"],
                        "height": previous_bbox["height"],
                        "confidence": 0.0,
                    })

            frame_index += 1

    finally:
        capture.release()

    if not points:
        return {
            "success": False,
            "message": "No faces detected in the video.",
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
        "detected_samples": detected_count,
        "total_samples": len(points),
        "tracking_points": points,
    }
