
export function captureVideoFrame(videoElement, quality = 0.85) {
  if (!videoElement || videoElement.readyState < 2) {
    throw new Error("Camera is not ready. Please start the camera.");
  }

  const canvas = document.createElement("canvas");
  canvas.width = videoElement.videoWidth;
  canvas.height = videoElement.videoHeight;

  if (!canvas.width || !canvas.height) {
    throw new Error("Could not read the camera frame.");
  }

  const context = canvas.getContext("2d");

  if (!context) {
    throw new Error("Unable to capture the camera frame.");
  }

  context.drawImage(
    videoElement,
    0,
    0,
    canvas.width,
    canvas.height
  );

  // Return only the Base64 content, without the data URL prefix.
  return canvas.toDataURL("image/jpeg", quality).split(",")[1];
}
