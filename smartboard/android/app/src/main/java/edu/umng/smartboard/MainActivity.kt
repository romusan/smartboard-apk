package edu.umng.smartboard

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
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
import edu.umng.smartboard.model.BoardPoint
import edu.umng.smartboard.model.Stroke
import edu.umng.smartboard.ui.BoardViewModel

class MainActivity : ComponentActivity() {
    private val vm: BoardViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { SmartBoardApp(vm) }
    }
}

@Composable
fun SmartBoardApp(vm: BoardViewModel) {
    var server by remember { mutableStateOf("http://127.0.0.1:8000") }
    var session by remember { mutableStateOf("demo") }
    var color by remember { mutableStateOf("#111111") }
    var width by remember { mutableStateOf(4f) }
    var lasso by remember { mutableStateOf(false) }
    var showOutlineMenu by remember { mutableStateOf(false) }
    var millerPlane by remember { mutableStateOf("112") }
    var elementSymbol by remember { mutableStateOf("Fe") }
    val connected by vm.socket.connected.collectAsState()

    MaterialTheme {
        Column(Modifier.fillMaxSize().background(Color(0xfff6f7fb)).padding(10.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(server, { server = it }, label = { Text("Servidor/IP o QR") }, modifier = Modifier.width(260.dp))
                OutlinedTextField(session, { session = it }, label = { Text("Sesión") }, modifier = Modifier.width(140.dp))
                Button(onClick = { vm.connect(server, session) }) { Text(if (connected) "Conectado" else "Conectar") }
                Button(onClick = vm::undo) { Text("Deshacer") }
                Button(onClick = vm::eraseLast) { Text("Borrar") }
                Button(onClick = vm::newPage) { Text("Nueva página") }
                AssistChip(onClick = { lasso = !lasso }, label = { Text(if (lasso) "Lazo activo" else "Lazo") })
            }
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(vertical = 8.dp)) {
                items(AiActions.size) { index ->
                    val item = AiActions[index]
                    Button(onClick = {
                        if (item.second == "outline") showOutlineMenu = true else vm.askAi(item.second)
                    }) { Text(item.first) }
                }
            }
            val aiStatus by vm.aiStatus
            val recognizedText by vm.recognizedText
            if (aiStatus.isNotBlank() || recognizedText.isNotBlank()) {
                Text(
                    text = aiStatus.ifBlank { "Leí: $recognizedText" },
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
            }
            BoardCanvas(vm, color, width, lasso, Modifier.fillMaxSize())
        }
        if (showOutlineMenu) {
            AlertDialog(
                onDismissRequest = { showOutlineMenu = false },
                title = { Text("Crear esquema") },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
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

@Composable
fun BoardCanvas(vm: BoardViewModel, color: String, width: Float, lasso: Boolean, modifier: Modifier = Modifier) {
    var size by remember { mutableStateOf(IntSize(1, 1)) }
    var activePoints by remember { mutableStateOf(emptyList<BoardPoint>()) }
    Box(modifier.background(Color.White)) {
        Canvas(
            Modifier.fillMaxSize().onSizeChanged { size = it }.pointerInput(color, width, lasso) {
                detectDragGestures(
                    onDragStart = { offset -> activePoints = listOf(offset.toPoint(size)) },
                    onDrag = { change, _ -> activePoints = activePoints + change.position.toPoint(size) },
                    onDragEnd = {
                        if (activePoints.size > 1) vm.addStroke(vm.strokeFromPoints(activePoints, if (lasso) "#2563eb" else color, if (lasso) 2f else width))
                        activePoints = emptyList()
                    }
                )
            }
        ) {
            vm.strokes.forEach { drawVectorStroke(it, size) }
            drawVectorStroke(Stroke(color = color, width = width, points = activePoints), size)
        }
        vm.aiCards.forEach { card ->
            Card(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(18.dp)
                    .widthIn(min = 280.dp, max = 420.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xfffffbeb))
            ) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Respuesta IA supervisada", style = MaterialTheme.typography.titleMedium)
                    Text(card.content, style = MaterialTheme.typography.bodyMedium)
                    Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                        TextButton(onClick = vm::clearAiCards) { Text("Quitar") }
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
