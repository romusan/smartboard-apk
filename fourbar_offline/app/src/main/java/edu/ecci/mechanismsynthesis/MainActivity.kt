package edu.ecci.mechanismsynthesis

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import edu.ecci.mechanismsynthesis.core.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale
import kotlin.math.max
import kotlin.math.min

private val Navy = Color(0xFF081526)
private val Panel = Color(0xFF11243A)
private val Cyan = Color(0xFF48CAE4)
private val Magenta = Color(0xFFFF4FA3)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme(colorScheme = darkColorScheme(primary = Cyan, secondary = Magenta, background = Navy, surface = Panel)) { FourBarApp() } }
    }
}

@Composable
private fun FourBarApp() {
    var drawing by remember { mutableStateOf<List<Vec2>>(emptyList()) }
    var solution by remember { mutableStateOf<MechanismSolution?>(null) }
    var running by remember { mutableStateOf(false) }
    var progress by remember { mutableFloatStateOf(0f) }
    var message by remember { mutableStateOf("Dibuja una curva cerrada con el lápiz") }
    val scope = rememberCoroutineScope()

    Surface(Modifier.fillMaxSize(), color = Navy) {
        Column(Modifier.fillMaxSize().padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("SÍNTESIS INVERSA · 4 BARRAS", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.headlineSmall)
                Spacer(Modifier.weight(1f))
                Text("100 % EN LA TABLETA · SIN INTERNET", color = Cyan, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(10.dp))
            if (solution == null) {
                DrawScreen(drawing, running, progress, message, onPoint = { p -> if (!running) drawing = drawing + p }, onClear = { drawing = emptyList(); message = "Dibuja una curva cerrada con el lápiz" }, onSynthesize = {
                    if (drawing.size < 20) { message = "Traza una curva más larga antes de calcular"; return@DrawScreen }
                    running = true; progress = 0f; message = "Buscando el mecanismo óptimo con PSO–TASS…"
                    scope.launch {
                        try {
                            val four = withContext(Dispatchers.Default) { FourBarSynthesizer().synthesize(drawing) { progress = it * .38f } }
                            solution = if (four.rmsError <= 2.5) four else {
                                message = "La curva supera a cuatro barras. Buscando Watt I de seis barras…"
                                val watt = withContext(Dispatchers.Default) { WattISynthesizer().synthesize(drawing) { progress = .38f + it * .62f } }
                                if (watt.rmsError < four.rmsError) watt else four
                            }
                        } catch (e: Exception) { message = e.message ?: "No fue posible sintetizar esta curva" }
                        running = false
                    }
                })
            } else ResultScreen(solution!!, onNew = { solution = null; drawing = emptyList(); progress = 0f; message = "Dibuja una curva cerrada con el lápiz" })
        }
    }
}

@Composable
private fun ColumnScope.DrawScreen(points: List<Vec2>, running: Boolean, progress: Float, message: String, onPoint: (Vec2) -> Unit, onClear: () -> Unit, onSynthesize: () -> Unit) {
    Row(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        Card(Modifier.weight(1f).fillMaxHeight(), colors = CardDefaults.cardColors(containerColor = Color(0xFFF8FAFC)), shape = RoundedCornerShape(18.dp)) {
            Canvas(Modifier.fillMaxSize().padding(8.dp).pointerInput(running) {
                detectDragGestures(onDragStart = { onPoint(Vec2(it.x.toDouble(), it.y.toDouble())) }, onDrag = { change, _ -> change.consume(); onPoint(Vec2(change.position.x.toDouble(), change.position.y.toDouble())) })
            }) {
                if (points.size > 1) {
                    val path = Path().apply { moveTo(points.first().x.toFloat(), points.first().y.toFloat()); points.drop(1).forEach { lineTo(it.x.toFloat(), it.y.toFloat()) } }
                    drawPath(path, Color(0xFF132A45), style = Stroke(6f, cap = StrokeCap.Round))
                }
            }
        }
        Card(Modifier.width(290.dp).fillMaxHeight(), colors = CardDefaults.cardColors(containerColor = Panel)) {
            Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("1. Dibuja una curva cerrada\n2. Pulsa CALCULAR\n3. Observa el mecanismo reproducirla", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.weight(1f))
                Text(message, color = if (running) Cyan else Color.White)
                if (running) LinearProgressIndicator({ progress }, Modifier.fillMaxWidth())
                Button(onClick = onSynthesize, enabled = !running, modifier = Modifier.fillMaxWidth().height(58.dp)) { Text("CALCULAR MECANISMO", fontWeight = FontWeight.Bold) }
                OutlinedButton(onClick = onClear, enabled = !running, modifier = Modifier.fillMaxWidth()) { Text("BORRAR") }
            }
        }
    }
}

@Composable
private fun ColumnScope.ResultScreen(solution: MechanismSolution, onNew: () -> Unit) {
    val frameCount = when(solution) { is FourBarSolution -> solution.poses.size; is WattISolution -> solution.poses.size }
    var frame by remember(solution) { mutableIntStateOf(0) }
    var delayMs by remember { mutableFloatStateOf(36f) }
    LaunchedEffect(solution, delayMs) { while (true) { delay(delayMs.toLong()); frame = (frame + 1) % frameCount } }
    Row(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        Card(Modifier.weight(1f).fillMaxHeight(), colors = CardDefaults.cardColors(containerColor = Color(0xFFF8FAFC)), shape = RoundedCornerShape(18.dp)) {
            when(solution) { is FourBarSolution -> MechanismCanvas(solution, frame, Modifier.fillMaxSize()); is WattISolution -> WattCanvas(solution, frame, Modifier.fillMaxSize()) }
        }
        Card(Modifier.width(320.dp).fillMaxHeight(), colors = CardDefaults.cardColors(containerColor = Panel)) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("MEJOR FAMILIA · ${solution.family.uppercase()}", color = Cyan, fontWeight = FontWeight.Bold)
                when(solution) {
                    is FourBarSolution -> { val d=solution.design; Length("L1 · bancada",d.l1);Length("L2 · manivela",d.l2);Length("L3 · acoplador",d.l3);Length("L4 · balancín",d.l4) }
                    is WattISolution -> { val d=solution.design; Length("L0 · bancada",d.l0);Length("L2 · manivela",d.l2);Length("L3 · acoplador",d.l3);Length("L4 · balancín",d.l4);Length("L5 · segundo lazo",d.l5);Length("L6 · segundo balancín",d.l6) }
                }
                HorizontalDivider(color = Color.White.copy(alpha = .15f))
                when(solution) { is FourBarSolution -> { Text("Punto trazador r = ${fmt(solution.design.couplerRadius)} mm"); Text(solution.grashof,color=Cyan) }; is WattISolution -> Text("Punto trazador u/v = ${fmt(solution.design.tracerU)} / ${fmt(solution.design.tracerV)} mm") }
                Text(solution.quality, color = if (solution.rmsError <= 5.0) Color(0xFF58E6A9) else Color(0xFFFFC857), fontWeight = FontWeight.Bold)
                Text("Error RMS: ${fmt(solution.rmsError)} mm")
                Text("Error máximo: ${fmt(solution.maxError)} mm")
                Spacer(Modifier.weight(1f))
                Text("Velocidad de animación")
                Slider(value = delayMs, onValueChange = { delayMs = it }, valueRange = 15f..85f)
                Button(onClick = onNew, Modifier.fillMaxWidth().height(52.dp)) { Text("NUEVA CURVA") }
            }
        }
    }
}

@Composable private fun Length(name: String, value: Double) { Row(Modifier.fillMaxWidth()) { Text(name); Spacer(Modifier.weight(1f)); Text("${fmt(value)} mm", fontWeight = FontWeight.Bold) } }
private fun fmt(v: Double) = String.format(Locale.US, "%.1f", v)

@Composable
private fun MechanismCanvas(solution: FourBarSolution, frame: Int, modifier: Modifier) {
    Canvas(modifier.padding(12.dp)) {
        val all = solution.target + solution.generated + solution.poses.flatMap { listOf(it.a, it.b, it.c, it.d, it.p) }
        val minX = all.minOf { it.x }; val maxX = all.maxOf { it.x }; val minY = all.minOf { it.y }; val maxY = all.maxOf { it.y }
        val scale = .88 * min(size.width / max(1.0, maxX - minX), size.height / max(1.0, maxY - minY))
        fun map(p: Vec2) = Offset((size.width / 2 + (p.x - (minX + maxX) / 2) * scale).toFloat(), (size.height / 2 - (p.y - (minY + maxY) / 2) * scale).toFloat())
        fun path(points: List<Vec2>, color: Color, width: Float) { if (points.size > 1) drawPath(Path().apply { moveTo(map(points[0]).x, map(points[0]).y); points.drop(1).forEach { lineTo(map(it).x, map(it).y) }; close() }, color, style = Stroke(width, cap = StrokeCap.Round)) }
        path(solution.target, Color(0xFF457B9D).copy(alpha = .65f), 5f)
        path(solution.generated, Magenta.copy(alpha = .85f), 4f)
        val p = solution.poses[frame]
        drawLine(Color(0xFF64748B), map(p.a), map(p.d), 12f, StrokeCap.Round)
        drawLine(Color(0xFF00B4D8), map(p.a), map(p.b), 11f, StrokeCap.Round)
        drawLine(Color(0xFFFF9F1C), map(p.b), map(p.c), 11f, StrokeCap.Round)
        drawLine(Color(0xFF2EC4B6), map(p.c), map(p.d), 11f, StrokeCap.Round)
        drawLine(Magenta.copy(alpha = .65f), map(p.b), map(p.p), 4f)
        listOf(p.a, p.b, p.c, p.d).forEach { drawCircle(Color.White, 9f, map(it)); drawCircle(Color(0xFF132A45), 4f, map(it)) }
        drawCircle(Magenta, 11f, map(p.p))
    }
}

@Composable
private fun WattCanvas(solution: WattISolution, frame: Int, modifier: Modifier) {
    Canvas(modifier.padding(12.dp)) {
        val all=solution.target+solution.generated+solution.poses.flatMap{listOf(it.o2,it.o4,it.a,it.b,it.c,it.d,it.ground,it.p)}
        val minX=all.minOf{it.x};val maxX=all.maxOf{it.x};val minY=all.minOf{it.y};val maxY=all.maxOf{it.y}
        val scale=.88*min(size.width/max(1.0,maxX-minX),size.height/max(1.0,maxY-minY))
        fun map(p:Vec2)=Offset((size.width/2+(p.x-(minX+maxX)/2)*scale).toFloat(),(size.height/2-(p.y-(minY+maxY)/2)*scale).toFloat())
        fun curve(points:List<Vec2>,color:Color,width:Float){if(points.size>1)drawPath(Path().apply{moveTo(map(points[0]).x,map(points[0]).y);points.drop(1).forEach{lineTo(map(it).x,map(it).y)};close()},color,style=Stroke(width,cap=StrokeCap.Round))}
        curve(solution.target,Color(0xFF457B9D).copy(alpha=.65f),5f);curve(solution.generated,Magenta.copy(alpha=.9f),4f)
        val p=solution.poses[frame]
        drawLine(Color(0xFF64748B),map(p.o2),map(p.o4),12f,StrokeCap.Round)
        drawLine(Color(0xFF00B4D8),map(p.o2),map(p.a),10f,StrokeCap.Round)
        drawLine(Color(0xFFFF9F1C),map(p.a),map(p.b),10f,StrokeCap.Round)
        drawLine(Color(0xFF2EC4B6),map(p.b),map(p.o4),10f,StrokeCap.Round)
        drawLine(Color(0xFFFF9F1C).copy(alpha=.7f),map(p.a),map(p.c),6f,StrokeCap.Round)
        drawLine(Color(0xFF9B5DE5),map(p.c),map(p.d),10f,StrokeCap.Round)
        drawLine(Color(0xFF06D6A0),map(p.d),map(p.ground),10f,StrokeCap.Round)
        drawLine(Magenta.copy(alpha=.7f),map(p.c),map(p.p),4f,StrokeCap.Round)
        listOf(p.o2,p.o4,p.a,p.b,p.c,p.d,p.ground).forEach{drawCircle(Color.White,8f,map(it));drawCircle(Color(0xFF132A45),3.5f,map(it))}
        drawCircle(Magenta,11f,map(p.p))
    }
}
