package edu.umng.smartboard.net

import com.google.gson.Gson
import edu.umng.smartboard.model.BoardMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.UUID
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.TimeUnit

class BoardSocketClient(private val gson: Gson = Gson()) {
    private val client = OkHttpClient.Builder().pingInterval(15, TimeUnit.SECONDS).build()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val queue = ConcurrentLinkedQueue<String>()
    private var socket: WebSocket? = null
    private var url: String = ""
    var serverBase: String = ""
        private set
    val incoming = MutableSharedFlow<BoardMessage>(extraBufferCapacity = 64)
    val connected = MutableStateFlow(false)
    val clientId: String = UUID.randomUUID().toString()

    fun connect(server: String, sessionId: String) {
        serverBase = server.trimEnd('/')
        url = serverBase.replace("http://", "ws://").replace("https://", "wss://") + "/ws/$sessionId"
        open()
    }

    private fun open() {
        val request = Request.Builder().url(url).build()
        socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                connected.value = true
                while (queue.isNotEmpty()) webSocket.send(queue.poll())
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching { gson.fromJson(text, BoardMessage::class.java) }.onSuccess { incoming.tryEmit(it) }
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { reconnect() }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) { reconnect() }
        })
    }

    fun send(message: BoardMessage) {
        val json = gson.toJson(message)
        if (connected.value && socket?.send(json) == true) return
        queue.add(json)
    }

    private fun reconnect() {
        connected.value = false
        scope.launch { delay(1200); if (url.isNotBlank()) open() }
    }
}
