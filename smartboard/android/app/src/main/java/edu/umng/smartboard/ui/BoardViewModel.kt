package edu.umng.smartboard.ui

import androidx.compose.runtime.mutableStateListOf
import androidx.lifecycle.ViewModel
import com.google.gson.Gson
import edu.umng.smartboard.model.BoardMessage
import edu.umng.smartboard.model.BoardPoint
import edu.umng.smartboard.model.Stroke
import edu.umng.smartboard.net.BoardSocketClient
import java.util.UUID

class BoardViewModel : ViewModel() {
    val socket = BoardSocketClient()
    val strokes = mutableStateListOf<Stroke>()
    val undone = mutableStateListOf<Stroke>()
    var sessionId = "demo"
    private val gson = Gson()

    fun connect(server: String, session: String) {
        sessionId = session.ifBlank { "demo" }
        socket.connect(server.ifBlank { "http://10.0.2.2:8000" }, sessionId)
    }

    fun addStroke(stroke: Stroke) {
        strokes.add(stroke)
        undone.clear()
        sendStroke("stroke_end", stroke)
    }

    fun undo() {
        strokes.removeLastOrNull()?.let {
            undone.add(it)
            send("undo", mapOf("stroke_id" to it.id))
        }
    }

    fun eraseLast() {
        strokes.removeLastOrNull()?.let { send("erase", mapOf("stroke_ids" to listOf(it.id))) }
    }

    fun newPage() = send("page_create", mapOf("page_id" to UUID.randomUUID().toString()))

    fun askAi(action: String, selected: List<Stroke> = strokes.toList()) {
        send("ai_request", mapOf("action" to action, "strokes" to selected, "recognized_text" to "", "page_context" to "Página enviada desde APK"))
    }

    fun sendStroke(type: String, stroke: Stroke) = send(type, mapOf("stroke" to stroke), stroke.id)

    private fun send(type: String, payload: Map<String, Any?>, strokeId: String? = null) {
        socket.send(BoardMessage(type = type, session_id = sessionId, client_id = socket.clientId, stroke_id = strokeId, payload = payload))
    }

    fun strokeFromPoints(points: List<BoardPoint>, color: String, width: Float) = Stroke(color = color, width = width, points = points)
}
