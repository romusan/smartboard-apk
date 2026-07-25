package edu.umng.smartboard.webrtc

/**
 * Optional future mode, intentionally disabled in the MVP.
 *
 * The product path is vector-first synchronization over WebSocket. This seam is
 * reserved for a full-screen MediaProjection + WebRTC transport if a later
 * version needs screen sharing, remote control, or video fallback.
 */
class MediaProjectionWebRtcMode {
    val enabled: Boolean = false

    fun start() {
        error("MediaProjection/WebRTC mode is not implemented in the MVP. Use vector WebSocket sync.")
    }
}
