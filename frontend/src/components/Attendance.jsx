
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import api from "../api/axios";
import { captureVideoFrame } from "../utils/camera";

const PAGE_SIZE = 20;

function getErrorMessage(error, fallback) {
  const detail = error.response?.data?.detail;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map(
        (item) =>
          `${item.loc?.at(-1) || "Field"}: ${item.msg}`
      )
      .join(" ");
  }

  return error.message || fallback;
}

function localDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function formatDate(value) {
  if (!value) return "—";

  const parsed = new Date(value);

  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString();
}

function formatDateTime(value) {
  if (!value) return "—";

  const parsed = new Date(value);

  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString();
}

function formatTime(value) {
  if (!value) return "—";

  const parsed = new Date(value);

  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
}

function statusClass(status) {
  switch (status) {
    case "Present":
      return "attendance-status attendance-status-present";
    case "Late":
      return "attendance-status attendance-status-late";
    case "HalfDay":
      return "attendance-status attendance-status-half-day";
    case "MissingCheckout":
      return "attendance-status attendance-status-missing";
    case "Absent":
      return "attendance-status attendance-status-absent";
    default:
      return "attendance-status";
  }
}

function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(
        new Error("Geolocation is not supported by this browser.")
      );
      return;
    }

    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 0,
    });
  });
}

function getLocationErrorMessage(error) {
  switch (error.code) {
    case 1:
      return "Location permission denied. Allow location access in your browser.";
    case 2:
      return "Your location is unavailable. Please try again.";
    case 3:
      return "Location request timed out. Please try again.";
    default:
      return error.message || "Unable to retrieve your location.";
  }
}

export default function Attendance({ role }) {
  const normalizedRole = String(role ?? "")
    .trim()
    .toLowerCase();

  const isEmployee = normalizedRole === "employee";
  const isManager =
    normalizedRole === "admin" || normalizedRole === "hr";

  const videoRef = useRef(null);
  const videoStreamRef = useRef(null);

  const [cameraReady, setCameraReady] = useState(false);
  const [cameraStarting, setCameraStarting] = useState(false);

  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [employeeId, setEmployeeId] = useState("");

  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const today = localDateString();

  const todayRecord = useMemo(
    () =>
      records.find(
        (record) => record.attendance_date === today
      ),
    [records, today]
  );

  const checkedInToday = Boolean(todayRecord);
  const checkedOutToday = Boolean(todayRecord?.check_out_at);

  const stopCamera = useCallback(() => {
    videoStreamRef.current?.getTracks().forEach((track) => {
      track.stop();
    });

    videoStreamRef.current = null;

    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }

    setCameraReady(false);
    setCameraStarting(false);
  }, []);

  const startCamera = async () => {
    setError("");
    setNotice("");

    if (cameraStarting || videoStreamRef.current) return;

    if (!navigator.mediaDevices?.getUserMedia) {
      setError(
        "Camera access is unavailable. Open this app using localhost or HTTPS."
      );
      return;
    }

    setCameraStarting(true);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
        },
        audio: false,
      });

      videoStreamRef.current = stream;

      const video = videoRef.current;

      if (!video) {
        stream.getTracks().forEach((track) => track.stop());
        videoStreamRef.current = null;
        throw new Error("Camera preview element was not found.");
      }

      video.srcObject = stream;
      video.muted = true;
      video.playsInline = true;

      await new Promise((resolve, reject) => {
        if (video.readyState >= 2) {
          resolve();
          return;
        }

        const handleReady = () => {
          cleanup();
          resolve();
        };

        const handleError = () => {
          cleanup();
          reject(new Error("The camera video could not be loaded."));
        };

        const cleanup = () => {
          video.removeEventListener("loadeddata", handleReady);
          video.removeEventListener("error", handleError);
        };

        video.addEventListener("loadeddata", handleReady, {
          once: true,
        });

        video.addEventListener("error", handleError, {
          once: true,
        });
      });

      await video.play();
      setCameraReady(true);
    } catch (err) {
      stopCamera();

      let message = err.message || "Unable to start the camera.";

      if (err.name === "NotAllowedError") {
        message =
          "Camera permission was denied. Allow camera access in your browser settings.";
      } else if (err.name === "NotFoundError") {
        message = "No camera was found on this device.";
      } else if (err.name === "NotReadableError") {
        message =
          "The camera is already in use by another application. Close that application and retry.";
      }

      setError(message);
    } finally {
      setCameraStarting(false);
    }
  };

  useEffect(() => {
    return () => {
      videoStreamRef.current?.getTracks().forEach((track) => {
        track.stop();
      });
    };
  }, []);

  const fetchAttendance = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const endpoint = isEmployee
        ? "/attendance/my"
        : "/attendance";

      const params = {
        page,
        page_size: PAGE_SIZE,
      };

      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      if (isManager && employeeId.trim()) {
        params.employee_id = employeeId.trim();
      }

      const response = await api.get(endpoint, { params });

      setRecords(
        Array.isArray(response.data?.items)
          ? response.data.items
          : []
      );

      setTotal(Number(response.data?.total ?? 0));
    } catch (err) {
      setError(
        getErrorMessage(err, "Unable to load attendance records.")
      );
      setRecords([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [
    isEmployee,
    isManager,
    page,
    startDate,
    endDate,
    employeeId,
  ]);

  useEffect(() => {
    fetchAttendance();
  }, [fetchAttendance]);

  const handleFilterSubmit = async (event) => {
    event.preventDefault();

    if (startDate && endDate && startDate > endDate) {
      setError("Start date must not be later than end date.");
      return;
    }

    setPage(1);
    setLoading(true);
    setError("");
    setNotice("");

    try {
      const endpoint = isEmployee
        ? "/attendance/my"
        : "/attendance";

      const params = {
        page: 1,
        page_size: PAGE_SIZE,
      };

      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      if (isManager && employeeId.trim()) {
        params.employee_id = employeeId.trim();
      }

      const response = await api.get(endpoint, { params });

      setRecords(response.data?.items ?? []);
      setTotal(Number(response.data?.total ?? 0));
    } catch (err) {
      setError(
        getErrorMessage(err, "Unable to filter attendance records.")
      );
    } finally {
      setLoading(false);
    }
  };

  const handleClearFilters = async () => {
    setStartDate("");
    setEndDate("");
    setEmployeeId("");
    setError("");
    setNotice("");
    setPage(1);
    setLoading(true);

    try {
      const endpoint = isEmployee
        ? "/attendance/my"
        : "/attendance";

      const response = await api.get(endpoint, {
        params: {
          page: 1,
          page_size: PAGE_SIZE,
        },
      });

      setRecords(response.data?.items ?? []);
      setTotal(Number(response.data?.total ?? 0));
    } catch (err) {
      setError(
        getErrorMessage(err, "Unable to load attendance records.")
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCheckIn = async () => {
    setActionLoading(true);
    setError("");
    setNotice("");

    try {
      if (!cameraReady || !videoRef.current) {
        throw new Error("Start the camera before checking in.");
      }

      const imageBase64 = captureVideoFrame(videoRef.current);

      let position;

      try {
        position = await getCurrentPosition();
      } catch (locationError) {
        throw new Error(
          getLocationErrorMessage(locationError)
        );
      }

      const { latitude, longitude, accuracy } = position.coords;

      await api.post("/attendance/check-in", {
        source: "camera",
        face_image_base64: imageBase64,
        latitude,
        longitude,
        gps_accuracy_m: accuracy,
      });

      setNotice(
        "Face verified and check-in recorded successfully."
      );

      await fetchAttendance();
    } catch (err) {
      setError(
        getErrorMessage(err, "Unable to check in.")
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleCheckOut = async () => {
    setActionLoading(true);
    setError("");
    setNotice("");

    try {
      await api.post("/attendance/check-out", {});

      setNotice("Check-out recorded successfully.");
      await fetchAttendance();
    } catch (err) {
      setError(
        getErrorMessage(err, "Unable to check out.")
      );
    } finally {
      setActionLoading(false);
    }
  };

  if (!isEmployee && !isManager) {
    return (
      <section className="employees-page">
        <p className="error-message">
          Your account does not have permission to view attendance.
          If you are an employee, check that the logged-in user role
          is passed to this component.
        </p>
      </section>
    );
  }

  const totalPages = Math.max(
    1,
    Math.ceil(total / PAGE_SIZE)
  );

  return (
    <section className="employees-page attendance-page">
      <div className="section-heading">
        <div>
          <h2>
            {isEmployee
              ? "My Attendance"
              : "Attendance Management"}
          </h2>

          <p>
            {isEmployee
              ? "Record your workday and review your attendance history."
              : "Review attendance records and filter by date or employee."}
          </p>
        </div>

        <button
          className="secondary-button"
          type="button"
          onClick={fetchAttendance}
          disabled={loading || actionLoading}
        >
          Refresh
        </button>
      </div>

      {error && (
        <div
          className="form-alert form-alert-error"
          role="alert"
        >
          {error}
        </div>
      )}

      {notice && (
        <div
          className="form-alert form-alert-success"
          role="status"
        >
          {notice}
        </div>
      )}

      {isEmployee && (
        <section className="attendance-today-card">
          <div>
            <h3>Today's Attendance</h3>
            <p>{formatDate(today)}</p>

            {todayRecord ? (
              <>
                <p>
                  Status:{" "}
                  <span className={statusClass(todayRecord.status)}>
                    {todayRecord.status}
                  </span>
                </p>

                <p>
                  Check-in: {formatTime(todayRecord.check_in_at)}
                </p>

                <p>
                  Check-out: {formatTime(todayRecord.check_out_at)}
                </p>
              </>
            ) : (
              <p>No attendance record found for today.</p>
            )}
          </div>

          <div className="attendance-camera">
            <h3>Face Verification Camera</h3>

            <div
              style={{
                width: "100%",
                maxWidth: "480px",
                marginBottom: "12px",
                padding: "8px",
                border: "1px solid #d1d5db",
                borderRadius: "12px",
                background: "#111827",
              }}
            >
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                aria-label="Live attendance camera preview"
                style={{
                  display: "block",
                  width: "100%",
                  height: "auto",
                  minHeight: "220px",
                  maxHeight: "360px",
                  objectFit: "cover",
                  background: "#111827",
                  borderRadius: "8px",
                  transform: "scaleX(-1)",
                }}
              />

              {!cameraReady && (
                <p
                  style={{
                    color: "#ffffff",
                    textAlign: "center",
                    margin: "10px 0",
                  }}
                >
                  {cameraStarting
                    ? "Starting camera..."
                    : "Camera is off. Select Start Camera."}
                </p>
              )}
            </div>

            <div className="attendance-actions">
              <button
                className="secondary-button"
                type="button"
                onClick={cameraReady ? stopCamera : startCamera}
                disabled={cameraStarting || actionLoading}
              >
                {cameraStarting
                  ? "Starting..."
                  : cameraReady
                    ? "Stop Camera"
                    : "Start Camera"}
              </button>

              {cameraReady && (
                <span role="status">
                  Camera ready
                </span>
              )}
            </div>
          </div>

          <div className="attendance-actions">
            <button
              className="primary-button"
              type="button"
              onClick={handleCheckIn}
              disabled={
                actionLoading ||
                checkedInToday ||
                !cameraReady ||
                cameraStarting
              }
            >
              {actionLoading
                ? "Please wait..."
                : checkedInToday
                  ? "Already Checked In"
                  : "Check In"}
            </button>

            <button
              className="secondary-button"
              type="button"
              onClick={handleCheckOut}
              disabled={
                actionLoading ||
                !checkedInToday ||
                checkedOutToday
              }
            >
              {checkedOutToday
                ? "Already Checked Out"
                : "Check Out"}
            </button>
          </div>

          <p className="field-hint">
            Allow camera and location permissions before checking in.
            Face verification and office GPS validation are performed
            by the backend. This prototype does not implement liveness
            detection.
          </p>
        </section>
      )}

      <section className="attendance-history">
        <div className="section-heading">
          <div>
            <h3>
              {isEmployee
                ? "My Attendance History"
                : "Attendance Records"}
            </h3>
            <p>{total} record(s) found.</p>
          </div>
        </div>

        <form
          className="attendance-filters"
          onSubmit={handleFilterSubmit}
        >
          <label className="form-field">
            Start Date
            <input
              type="date"
              value={startDate}
              onChange={(event) =>
                setStartDate(event.target.value)
              }
              max={endDate || undefined}
            />
          </label>

          <label className="form-field">
            End Date
            <input
              type="date"
              value={endDate}
              onChange={(event) =>
                setEndDate(event.target.value)
              }
              min={startDate || undefined}
            />
          </label>

          {isManager && (
            <label className="form-field">
              Employee ID
              <input
                type="text"
                value={employeeId}
                onChange={(event) =>
                  setEmployeeId(event.target.value)
                }
                placeholder="MongoDB employee ID"
              />
            </label>
          )}

          <div className="attendance-filter-actions">
            <button
              className="primary-button"
              type="submit"
              disabled={loading}
            >
              Apply Filters
            </button>

            <button
              className="secondary-button"
              type="button"
              onClick={handleClearFilters}
              disabled={loading}
            >
              Clear
            </button>
          </div>
        </form>

        {loading ? (
          <p>Loading attendance records...</p>
        ) : (
          <div className="employee-table-wrapper">
            <table className="employee-table">
              <thead>
                <tr>
                  {isManager && <th>Employee ID</th>}
                  <th>Date</th>
                  <th>Check In</th>
                  <th>Check Out</th>
                  <th>Status</th>
                  <th>Source</th>
                  <th>Notes</th>
                </tr>
              </thead>

              <tbody>
                {records.length === 0 ? (
                  <tr>
                    <td colSpan={isManager ? 7 : 6}>
                      No attendance records found.
                    </td>
                  </tr>
                ) : (
                  records.map((record) => (
                    <tr key={record.id}>
                      {isManager && (
                        <td>{record.employee_id}</td>
                      )}
                      <td>{formatDate(record.attendance_date)}</td>
                      <td>{formatDateTime(record.check_in_at)}</td>
                      <td>{formatDateTime(record.check_out_at)}</td>
                      <td>
                        <span className={statusClass(record.status)}>
                          {record.status}
                        </span>
                      </td>
                      <td>{record.source}</td>
                      <td>{record.notes || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="pagination-controls">
          <button
            className="secondary-button"
            type="button"
            onClick={() =>
              setPage((current) => Math.max(1, current - 1))
            }
            disabled={page <= 1 || loading}
          >
            Previous
          </button>

          <span>
            Page {page} of {totalPages}
          </span>

          <button
            className="secondary-button"
            type="button"
            onClick={() => setPage((current) => current + 1)}
            disabled={page >= totalPages || loading}
          >
            Next
          </button>
        </div>
      </section>
    </section>
  );
}
