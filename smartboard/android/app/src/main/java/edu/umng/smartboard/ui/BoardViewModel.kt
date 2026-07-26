package edu.umng.smartboard.ui

import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.Gson
import edu.umng.smartboard.model.AiBoardCard
import edu.umng.smartboard.ai.HandwritingRecognizer
import edu.umng.smartboard.model.BoardMessage
import edu.umng.smartboard.model.BoardPoint
import edu.umng.smartboard.model.Stroke
import edu.umng.smartboard.net.BoardSocketClient
import kotlinx.coroutines.launch
import java.util.UUID

class BoardViewModel : ViewModel() {
    val socket = BoardSocketClient()
    val strokes = mutableStateListOf<Stroke>()
    val undone = mutableStateListOf<Stroke>()
    val aiCards = mutableStateListOf<AiBoardCard>()
    val recognizedText = mutableStateOf("")
    val aiStatus = mutableStateOf("")
    var sessionId = "demo"
    private val gson = Gson()
    private val handwritingRecognizer = HandwritingRecognizer()

    init {
        viewModelScope.launch {
            socket.incoming.collect { message ->
                if (message.type == "ai_response") {
                    val content = message.payload["content"]?.toString().orEmpty()
                    val kind = message.payload["kind"]?.toString() ?: "text"
                    if (content.isNotBlank()) {
                        aiCards.clear()
                        aiCards.add(AiBoardCard(kind = kind, content = content))
                        aiStatus.value = "Respuesta IA recibida."
                    }
                }
                if (message.type == "command") {
                    message.payload["error"]?.toString()?.let { aiStatus.value = it }
                }
            }
        }
    }

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

    fun clearAiCards() {
        aiCards.clear()
        send("command", mapOf("action" to "clear_ai_cards"))
    }

    fun askAi(action: String, selected: List<Stroke> = strokes.toList()) {
        viewModelScope.launch {
            aiStatus.value = "Leyendo escritura..."
            val text = runCatching { handwritingRecognizer.recognize(selected) }
                .onFailure { aiStatus.value = "No pude leer la escritura: ${it.message}" }
                .getOrDefault("")
                .trim()
            recognizedText.value = text
            aiStatus.value = if (text.isBlank()) {
                "Consulta enviada sin texto reconocido."
            } else {
                "Leí: $text"
            }
            send(
                "ai_request",
                mapOf(
                    "action" to action,
                    "strokes" to selected,
                    "recognized_text" to text,
                    "page_context" to "Página enviada desde APK. Pregunta manuscrita: $text"
                )
            )
        }
    }

    fun requestCard(cardType: String) {
        aiStatus.value = "Generando tarjeta..."
        send(
            "ai_request",
            mapOf(
                "action" to "outline",
                "card_type" to cardType,
                "recognized_text" to cardType.replace("_", " "),
                "page_context" to "Tarjeta paramétrica solicitada desde Crear esquema"
            )
        )
    }

    fun sendStroke(type: String, stroke: Stroke) = send(type, mapOf("stroke" to stroke), stroke.id)

    private fun send(type: String, payload: Map<String, Any?>, strokeId: String? = null) {
        socket.send(BoardMessage(type = type, session_id = sessionId, client_id = socket.clientId, stroke_id = strokeId, payload = payload))
    }

    fun strokeFromPoints(points: List<BoardPoint>, color: String, width: Float) = Stroke(color = color, width = width, points = points)
}
