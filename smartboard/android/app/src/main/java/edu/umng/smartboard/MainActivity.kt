package edu.umng.smartboard

import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebSettings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke as DrawStroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.viewinterop.AndroidView
import edu.umng.smartboard.model.BoardPoint
import edu.umng.smartboard.model.Stroke
import edu.umng.smartboard.ui.BoardViewModel

class MainActivity : ComponentActivity() {
    private val vm: BoardViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
        setContent { SmartBoardApp(vm) }
    }
}

@Composable
fun SmartBoardApp(vm: BoardViewModel) {
    var server by rememberSaveable { mutableStateOf("http://127.0.0.1:8000") }
    var session by rememberSaveable { mutableStateOf("demo") }
    var color by remember { mutableStateOf("#111111") }
    var width by remember { mutableStateOf(4f) }
    var lasso by remember { mutableStateOf(false) }
    var showOutlineMenu by remember { mutableStateOf(false) }
    var millerPlane by remember { mutableStateOf("112") }
    var elementSymbol by remember { mutableStateOf("Fe") }
    var menu by remember { mutableStateOf<String?>(null) }
    var focusMode by rememberSaveable { mutableStateOf(false) }
    var confirmErase by remember { mutableStateOf(false) }
    val connected by vm.socket.connected.collectAsState()
    val activeSubject by vm.subject

    LaunchedEffect(Unit) {
        vm.connect(server, session)
    }

    MaterialTheme {
        Box(Modifier.fillMaxSize().background(Color(0xffe2e8f0)).windowInsetsPadding(WindowInsets.displayCutout)) {
            Column(Modifier.fillMaxSize()) {
                if (!focusMode) {
                    Row(
                        Modifier.fillMaxWidth().background(Color(0xfff6f7fb))
                            .horizontalScroll(rememberScrollState()).padding(horizontal = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Box {
                            TextButton(onClick = { menu = "tools" }) { Text("Herramientas") }
                            DropdownMenu(expanded = menu == "tools", onDismissRequest = { menu = null }) {
                                DropdownMenuItem(text = { Text(if (lasso) "✓ Lazo" else "Lazo") }, onClick = { lasso = !lasso; menu = null })
                                PenColors.forEach { item ->
                                    DropdownMenuItem(text = { Text((if (item.hex == color) "✓ " else "") + item.label, color = Color(android.graphics.Color.parseColor(item.hex))) }, onClick = { color = item.hex; lasso = false; menu = null })
                                }
                                HorizontalDivider()
                                listOf(2f, 4f, 7f).forEach { value ->
                                    DropdownMenuItem(text = { Text("${if (width == value) "✓ " else ""}Grosor ${value.toInt()}") }, onClick = { width = value; menu = null })
                                }
                                HorizontalDivider()
                                DropdownMenuItem(text = { Text("Nueva página") }, onClick = { vm.newPage(); menu = null })
                                DropdownMenuItem(text = { Text("Borrar pizarra") }, onClick = { confirmErase = true; menu = null })
                            }
                        }
                        TextButton(onClick = vm::undo) { Text("Deshacer") }
                        Box {
                            TextButton(onClick = { menu = "subject" }) { Text(Subjects.first { it.second == activeSubject }.first) }
                            DropdownMenu(expanded = menu == "subject", onDismissRequest = { menu = null }) {
                                Subjects.forEach { item ->
                                    DropdownMenuItem(text = { Text(item.first) }, onClick = { vm.setSubject(item.second); menu = null })
                                }
                            }
                        }
                        Box {
                            TextButton(onClick = { menu = "ai" }) { Text("IA / Esquemas") }
                            DropdownMenu(expanded = menu == "ai", onDismissRequest = { menu = null }) {
                                AiActions.forEach { item ->
                                    DropdownMenuItem(text = { Text(item.first) }, onClick = {
                                        menu = null
                                        if (item.second == "outline" && activeSubject == "materiales") showOutlineMenu = true else vm.askAi(item.second)
                                    })
                                }
                                if (activeSubject == "mecanismos") DropdownMenuItem(text = { Text("Sintetizar mecanismo") }, onClick = { vm.requestMechanism(); menu = null })
                            }
                        }
                        TextButton(onClick = { menu = "connection" }) { Text(if (connected) "● Conexión" else "○ Conectar") }
                        val documentStatus by vm.documentStatus
                        if (documentStatus.isNotBlank()) {
                            TextButton(onClick = vm::previousDocumentPage) { Text("◀ PDF") }
                            Text(documentStatus, style = MaterialTheme.typography.labelSmall)
                            TextButton(onClick = vm::nextDocumentPage) { Text("PDF ▶") }
                        }
                        TextButton(onClick = { focusMode = true }) { Text("Solo pizarra") }
                    }
                }
                BoxWithConstraints(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
                    // Match the projection's 16:10 page so normalized strokes keep their shape.
                    val pageWidth = minOf(maxWidth, maxHeight * 1.6f)
                    BoardCanvas(vm = vm, color = color, width = width, lasso = lasso,
                        modifier = Modifier.width(pageWidth).height(pageWidth / 1.6f))
                }
            }
            if (focusMode) {
                FilledTonalButton(onClick = { focusMode = false }, modifier = Modifier.align(Alignment.TopEnd).padding(4.dp),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)) { Text("Menú") }
            }
        }
        if (menu == "connection") {
            val aiStatus by vm.aiStatus
            AlertDialog(onDismissRequest = { menu = null }, title = { Text("Conexión y estado") }, text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(server, { server = it }, label = { Text("Servidor/IP") }, singleLine = true)
                    OutlinedTextField(session, { session = it }, label = { Text("Sesión") }, singleLine = true)
                    Text(if (connected) "Conectado" else "Desconectado")
                    if (aiStatus.isNotBlank()) Text(aiStatus)
                }
            }, confirmButton = { TextButton(onClick = { vm.connect(server, session); menu = null }) { Text("Conectar") } },
                dismissButton = { TextButton(onClick = { menu = null }) { Text("Cerrar") } })
        }
        if (confirmErase) {
            AlertDialog(onDismissRequest = { confirmErase = false }, title = { Text("¿Borrar pizarra?") },
                text = { Text("Se eliminarán los trazos y las respuestas de esta pizarra.") },
                confirmButton = { TextButton(onClick = { vm.eraseBoard(); confirmErase = false }) { Text("Borrar") } },
                dismissButton = { TextButton(onClick = { confirmErase = false }) { Text("Cancelar") } })
        }
        if (showOutlineMenu) {
            AlertDialog(
                onDismissRequest = { showOutlineMenu = false },
                title = { Text("Crear esquema") },
                text = {
                    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Dibujos y tarjetas paramétricas")
                        OutlinedTextField(
                            value = millerPlane,
                            onValueChange = { millerPlane = it },
                            label = { Text("Plano de Miller (hkl)") },
                            supportingText = { Text("Ejemplo: 112, 100, 111") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Button(onClick = {
                            vm.requestMillerPlane(millerPlane)
                            showOutlineMenu = false
                        }, modifier = Modifier.fillMaxWidth()) {
                            Text("Planos de Miller")
                        }
                        Button(onClick = { vm.requestCard("atom_structure"); showOutlineMenu = false }, modifier = Modifier.fillMaxWidth()) {
                            Text("Estructura del átomo")
                        }
                        Button(onClick = { vm.requestCard("atomic_interaction"); showOutlineMenu = false }, modifier = Modifier.fillMaxWidth()) {
                            Text("Fuerzas y energía entre átomos")
                        }
                        Button(onClick = { vm.requestCard("quantum_numbers"); showOutlineMenu = false }, modifier = Modifier.fillMaxWidth()) {
                            Text("Números cuánticos / niveles")
                        }
                        OutlinedTextField(
                            value = elementSymbol,
                            onValueChange = { elementSymbol = it },
                            label = { Text("Elemento") },
                            supportingText = { Text("Ejemplo: H, C, Al, Fe, Cu, Kr") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Button(onClick = {
                            vm.requestElementEnergy(elementSymbol)
                            showOutlineMenu = false
                        }, modifier = Modifier.fillMaxWidth()) {
                            Text("Configuración electrónica por elemento")
                        }
                        Button(onClick = { vm.requestCard("bcc"); showOutlineMenu = false }, modifier = Modifier.fillMaxWidth()) {
                            Text("Estructura BCC")
                        }
                        Button(onClick = { vm.requestCard("fcc"); showOutlineMenu = false }, modifier = Modifier.fillMaxWidth()) {
                            Text("Estructura FCC")
                        }
                        Button(onClick = { vm.requestCard("sc"); showOutlineMenu = false }, modifier = Modifier.fillMaxWidth()) {
                            Text("Cúbica simple SC")
                        }
                    }
                },
                confirmButton = {
                    TextButton(onClick = { showOutlineMenu = false }) { Text("Cerrar") }
                }
            )
        }
    }
}

val AiActions = listOf(
    "Explicar" to "explain", "Completar idea" to "complete", "Corregir" to "correct",
    "Resolver" to "solve", "Crear esquema" to "outline", "Generar ejercicio" to "exercise", "Dibujar en 3D" to "draw3d"
)

val Subjects = listOf(
    "Materiales" to "materiales",
    "Mecanismos" to "mecanismos",
    "Dinámica" to "dinamica"
)

data class PenColor(val label: String, val hex: String)

val PenColors = listOf(
    PenColor("Negro", "#111111"),
    PenColor("Azul", "#2563eb"),
    PenColor("Rojo", "#dc2626"),
    PenColor("Verde", "#16a34a"),
    PenColor("Morado", "#7c3aed"),
    PenColor("Naranja", "#f97316"),
    PenColor("Amarillo", "#facc15")
)

@Composable
fun BoardCanvas(
    vm: BoardViewModel,
    color: String,
    width: Float,
    lasso: Boolean,
    modifier: Modifier = Modifier
) {
    var size by remember { mutableStateOf(IntSize(1, 1)) }
    var activePoints by remember { mutableStateOf(emptyList<BoardPoint>()) }
    Box(modifier.background(Color.White)) {
        Canvas(
            Modifier.fillMaxSize().onSizeChanged { size = it }.pointerInput(color, width, lasso) {
                detectDragGestures(
                    onDragStart = { offset -> activePoints = listOf(offset.toPoint(size)) },
                    onDrag = { change, _ -> activePoints = activePoints + change.position.toPoint(size) },
                    onDragCancel = { activePoints = emptyList() },
                    onDragEnd = {
                        if (activePoints.size > 1) vm.addStroke(
                            vm.strokeFromPoints(activePoints, if (lasso) "#2563eb" else color, if (lasso) 2f else width),
                            allowAutomaticSynthesis = !lasso
                        )
                        activePoints = emptyList()
                    }
                )
            }
        ) {
            vm.backgroundImage.value?.let { image ->
                drawImage(image, dstSize = androidx.compose.ui.unit.IntSize(size.width, size.height))
            }
            vm.strokes.forEach { drawVectorStroke(it, size) }
            drawVectorStroke(Stroke(color = color, width = width, points = activePoints), size)
        }
        val simulationCards = vm.aiCards.filter { it.simulationUrl != null }
        var simulationIndex by remember { mutableIntStateOf(0) }
        LaunchedEffect(simulationCards.size) {
            if (simulationCards.isNotEmpty()) simulationIndex = simulationCards.lastIndex
        }
        val visibleCards = vm.aiCards.filter { it.simulationUrl == null } +
            listOfNotNull(simulationCards.getOrNull(simulationIndex))
        visibleCards.forEach { card ->
            Card(
                modifier = if (card.simulationUrl != null) {
                    Modifier.align(Alignment.Center).fillMaxSize().padding(12.dp)
                } else {
                    Modifier.align(Alignment.TopEnd).padding(18.dp).widthIn(min = 280.dp, max = 420.dp)
                },
                colors = CardDefaults.cardColors(containerColor = Color(0xfffffbeb))
            ) {
                Column((if (card.simulationUrl != null) Modifier.fillMaxSize() else Modifier.heightIn(max = 300.dp).verticalScroll(rememberScrollState())).padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            if (card.simulationUrl != null) "Simulación interactiva ${simulationIndex + 1} de ${simulationCards.size}" else "Respuesta IA supervisada",
                            style = MaterialTheme.typography.titleMedium
                        )
                        if (card.simulationUrl != null && simulationCards.size > 1) {
                            Row {
                                TextButton(
                                    onClick = { simulationIndex = (simulationIndex - 1).coerceAtLeast(0) },
                                    enabled = simulationIndex > 0
                                ) { Text("Anterior") }
                                TextButton(
                                    onClick = { simulationIndex = (simulationIndex + 1).coerceAtMost(simulationCards.lastIndex) },
                                    enabled = simulationIndex < simulationCards.lastIndex
                                ) { Text("Siguiente") }
                            }
                        }
                        TextButton(onClick = vm::clearAiCards) { Text("Cerrar") }
                    }
                    if (card.simulationUrl == null) Text(card.content, style = MaterialTheme.typography.bodyMedium)
                    card.simulationUrl?.let { url ->
                        val tabletUrl = url + if (url.contains("?")) "&tablet=1" else "?tablet=1"
                        AndroidView(
                            factory = { context -> WebView(context).apply {
                                webViewClient = WebViewClient()
                                settings.javaScriptEnabled = true
                                settings.cacheMode = WebSettings.LOAD_NO_CACHE
                                clearCache(true)
                                loadUrl(tabletUrl)
                            } },
                            update = { view -> if (view.url != tabletUrl) view.loadUrl(tabletUrl) },
                            modifier = Modifier.fillMaxWidth().weight(1f)
                        )
                    }
                }
            }
        }

    }
}

fun Offset.toPoint(size: IntSize) = BoardPoint(
    x = (x / size.width).coerceIn(0f, 1f),
    y = (y / size.height).coerceIn(0f, 1f),
    pressure = 1f,
    t = System.currentTimeMillis()
)

fun androidx.compose.ui.graphics.drawscope.DrawScope.drawVectorStroke(stroke: Stroke, size: IntSize) {
    if (stroke.points.size < 2) return
    val path = Path()
    stroke.points.forEachIndexed { index, point ->
        val offset = Offset(point.x * size.width, point.y * size.height)
        if (index == 0) path.moveTo(offset.x, offset.y) else path.lineTo(offset.x, offset.y)
    }
    drawPath(path, color = Color(android.graphics.Color.parseColor(stroke.color)), style = DrawStroke(width = stroke.width, cap = StrokeCap.Round))
}
