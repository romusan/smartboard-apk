package edu.umng.smartboard.model

import java.util.UUID

data class BoardPoint(val x: Float, val y: Float, val pressure: Float, val t: Long)
data class Stroke(
    val id: String = UUID.randomUUID().toString(),
    val page_id: String = "page-1",
    val color: String = "#111111",
    val width: Float = 4f,
    val points: List<BoardPoint> = emptyList()
)
data class BoardMessage(
    val type: String,
    val session_id: String,
    val client_id: String,
    val page_id: String = "page-1",
    val stroke_id: String? = null,
    val timestamp: Long = System.currentTimeMillis(),
    val version: Int = 1,
    val payload: Map<String, Any?> = emptyMap()
)
data class AiBoardCard(
    val id: String = UUID.randomUUID().toString(),
    val kind: String = "text",
    val content: String,
    val x: Float = 0.56f,
    val y: Float = 0.08f
)
data class AiRequest(
    val action: String,
    val session_id: String,
    val page_id: String,
    val selection_id: String? = null,
    val strokes: List<Stroke> = emptyList(),
    val png_base64: String? = null,
    val recognized_text: String = "",
    val page_context: String = ""
)
