package edu.umng.smartboard.ui

import android.graphics.BitmapFactory
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.Gson
import edu.umng.smartboard.ai.HandwritingRecognizer
import edu.umng.smartboard.model.AiBoardCard
import edu.umng.smartboard.model.BoardMessage
import edu.umng.smartboard.model.BoardPoint
import edu.umng.smartboard.model.Stroke
import edu.umng.smartboard.net.BoardSocketClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.URL
import java.util.UUID

class BoardViewModel : ViewModel() {
    val socket = BoardSocketClient()
    val strokes = mutableStateListOf<Stroke>()
    val undone = mutableStateListOf<Stroke>()
    val aiCards = mutableStateListOf<AiBoardCard>()
    val recognizedText = mutableStateOf("")
    val aiStatus = mutableStateOf("")
    val backgroundImage = mutableStateOf<ImageBitmap?>(null)
    val documentStatus = mutableStateOf("")
    var sessionId = "demo"
    private val gson = Gson()
    private val handwritingRecognizer = HandwritingRecognizer()
    private var documentPages: List<Map<String, Any?>> = emptyList()
    private var currentPageIndex = 0

    init {
        viewModelScope.launch {
            socket.incoming.collect { message ->
                applyMessage(message)
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

    fun eraseBoard() {
        val strokeIds = strokes.map { it.id }
        strokes.clear()
        aiCards.clear()
        undone.clear()
        if (strokeIds.isNotEmpty()) send("erase", mapOf("stroke_ids" to strokeIds))
        send("command", mapOf("action" to "clear_ai_cards"))
        send("command", mapOf("action" to "clear_board"))
    }

    fun newPage() = send("page_create", mapOf("page_id" to UUID.randomUUID().toString()))

    fun previousDocumentPage() = sendDocumentPageSelect(currentPageIndex - 1)

    fun nextDocumentPage() = sendDocumentPageSelect(currentPageIndex + 1)

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
            aiStatus.value = if (text.isBlank()) "Consulta enviada sin texto reconocido." else "Leí: $text"
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

    fun requestMillerPlane(plane: String) {
        val hkl = plane.filter { it.isDigit() }.take(3).ifBlank { "112" }
        aiStatus.value = "Generando plano de Miller ($hkl)..."
        send(
            "ai_request",
            mapOf(
                "action" to "outline",
                "card_type" to "miller_plane",
                "recognized_text" to "planos $hkl",
                "page_context" to "Tarjeta parametrica de planos de Miller solicitada desde Crear esquema: ($hkl)"
            )
        )
    }

    fun requestElementEnergy(element: String) {
        val cleanElement = element.filter { it.isLetter() }.take(2).ifBlank { "Fe" }
        aiStatus.value = "Generando configuración electrónica de $cleanElement..."
        send(
            "ai_request",
            mapOf(
                "action" to "outline",
                "card_type" to "element_energy",
                "recognized_text" to "elemento $cleanElement configuracion electronica niveles energeticos",
                "page_context" to "Tarjeta de configuracion electronica por elemento solicitada desde Crear esquema: $cleanElement"
            )
        )
    }

    fun sendStroke(type: String, stroke: Stroke) = send(type, mapOf("stroke" to stroke), stroke.id)

    private fun send(type: String, payload: Map<String, Any?>, strokeId: String? = null) {
        socket.send(BoardMessage(type = type, session_id = sessionId, client_id = socket.clientId, stroke_id = strokeId, payload = payload))
    }

    fun strokeFromPoints(points: List<BoardPoint>, color: String, width: Float) = Stroke(color = color, width = width, points = points)

    private fun applyMessage(message: BoardMessage) {
        if (message.type == "sync_state") {
            val history = message.payload["history"] as? List<*> ?: return
            strokes.clear()
            aiCards.clear()
            history.forEach { raw ->
                val nested = runCatching {
                    gson.fromJson(gson.toJson(raw), BoardMessage::class.java)
                }.getOrNull()
                if (nested != null) applyMessage(nested)
            }
            return
        }
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
            val action = message.payload["action"]?.toString().orEmpty()
            if (action in listOf("clear_ai_cards", "clear_ai_card", "clear_ai", "delete_ai_cards")) {
                aiCards.clear()
            }
            if (action in listOf("clear_board", "delete_board", "reset_board")) {
                strokes.clear()
                aiCards.clear()
                undone.clear()
            }
        }
        if (message.type == "object_update" && message.payload["action"] == "document_set") {
            handleDocumentSet(message.payload["document"])
        }
        if (message.type == "page_select") {
            val index = (message.payload["page_index"] as? Number)?.toInt() ?: currentPageIndex
            selectDocumentPage(index)
        }
        if (message.type == "stroke_end" || message.type == "stroke_update" || message.type == "stroke_start") {
            val rawStroke = message.payload["stroke"] ?: return
            val stroke = runCatching { gson.fromJson(gson.toJson(rawStroke), Stroke::class.java) }.getOrNull() ?: return
            val index = strokes.indexOfFirst { it.id == stroke.id }
            if (index >= 0) strokes[index] = stroke else strokes.add(stroke)
        }
        if (message.type == "erase") {
            val strokeIds = message.payload["stroke_ids"] as? List<*> ?: return
            strokes.removeAll { stroke -> strokeIds.any { it?.toString() == stroke.id } }
        }
    }

    @Suppress("UNCHECKED_CAST")
    private fun handleDocumentSet(rawDocument: Any?) {
        val document = rawDocument as? Map<String, Any?> ?: return
        documentPages = document["pages"] as? List<Map<String, Any?>> ?: emptyList()
        currentPageIndex = (document["current_page"] as? Number)?.toInt() ?: 0
        selectDocumentPage(currentPageIndex)
    }

    private fun sendDocumentPageSelect(index: Int) {
        if (documentPages.isEmpty()) return
        val nextIndex = index.coerceIn(0, documentPages.lastIndex)
        val page = documentPages[nextIndex]
        send(
            "page_select",
            mapOf(
                "page_index" to nextIndex,
                "page_id" to (page["page_id"] ?: "page-1")
            )
        )
        selectDocumentPage(nextIndex)
    }

    private fun selectDocumentPage(index: Int) {
        if (documentPages.isEmpty()) return
        currentPageIndex = index.coerceIn(0, documentPages.lastIndex)
        val page = documentPages[currentPageIndex]
        val relativeUrl = page["image_url"]?.toString() ?: return
        val imageUrl = if (relativeUrl.startsWith("http")) relativeUrl else "${socket.serverBase}$relativeUrl"
        documentStatus.value = "PDF página ${currentPageIndex + 1}/${documentPages.size}"
        viewModelScope.launch {
            backgroundImage.value = loadImage(imageUrl)
        }
    }

    private suspend fun loadImage(url: String): ImageBitmap? = withContext(Dispatchers.IO) {
        runCatching {
            URL(url).openStream().use { BitmapFactory.decodeStream(it).asImageBitmap() }
        }.getOrNull()
    }
}
