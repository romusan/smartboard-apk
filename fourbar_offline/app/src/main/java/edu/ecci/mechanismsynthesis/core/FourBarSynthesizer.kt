package edu.ecci.mechanismsynthesis.core

import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.yield
import kotlin.coroutines.coroutineContext
import kotlin.math.*
import kotlin.random.Random

class FourBarSynthesizer(
    private val particles: Int = 68,
    private val iterations: Int = 280,
    private val samples: Int = 72
) : MechanismSynthesizer<FourBarSolution> {
    private val lower = doubleArrayOf(35.0, 10.0, 25.0, 20.0, 3.0, -PI)
    private val upper = doubleArrayOf(150.0, 85.0, 150.0, 120.0, 120.0, PI)

    override suspend fun synthesize(curve: List<Vec2>, onProgress: (Float) -> Unit): FourBarSolution {
        require(curve.size >= 8) { "La curva necesita al menos 8 puntos" }
        val target = prepareCurve(curve, samples)
        val rng = Random(target.fold(17) { a, p -> 31 * a + (p.x * 10 + p.y).roundToInt() })
        val pos = Array(particles) { randomFeasible(rng) }
        val vel = Array(particles) { DoubleArray(6) }
        val best = Array(particles) { pos[it].copyOf() }
        val bestScore = DoubleArray(particles) { evaluate(best[it], target).score }
        var global = best[bestScore.indices.minBy { bestScore[it] }].copyOf()
        var globalScore = bestScore.min()

        repeat(iterations) { step ->
            coroutineContext.ensureActive()
            val inertia = 0.90 - 0.55 * step / max(1, iterations - 1).toDouble()
            val radius = 3 + (13 * step / max(1, iterations - 1))
            for (i in 0 until particles) {
                val neighborhood = (i - radius..i + radius).map { (it + particles) % particles }
                val localIndex = neighborhood.minBy { bestScore[it] }
                for (j in 0..5) {
                    val cognition = 1.65 * rng.nextDouble() * (best[i][j] - pos[i][j])
                    val social = 1.80 * rng.nextDouble() * (best[localIndex][j] - pos[i][j])
                    val jitter = (upper[j] - lower[j]) * 0.002 * rng.nextDouble(-1.0, 1.0)
                    vel[i][j] = inertia * vel[i][j] + cognition + social + jitter
                    pos[i][j] = (pos[i][j] + vel[i][j]).coerceIn(lower[j], upper[j])
                }
                val score = evaluate(pos[i], target).score
                if (score < bestScore[i]) {
                    bestScore[i] = score
                    best[i] = pos[i].copyOf()
                    if (score < globalScore) { globalScore = score; global = pos[i].copyOf() }
                }
            }
            onProgress((step + 1f) / iterations)
            yield()
        }
        // PSO finds the basin; deterministic coordinate search removes its residual error.
        var polished = global.copyOf()
        var polishedScore = evaluate(polished, target, shiftStep = 1).score
        var steps = DoubleArray(6) { j -> (upper[j] - lower[j]) * if (j == 5) 0.025 else 0.035 }
        repeat(11) {
            for (j in 0..5) for (direction in doubleArrayOf(-1.0, 1.0)) {
                val candidate = polished.copyOf()
                candidate[j] = (candidate[j] + direction * steps[j]).coerceIn(lower[j], upper[j])
                val score = evaluate(candidate, target, shiftStep = 1).score
                if (score < polishedScore) { polished = candidate; polishedScore = score }
            }
            steps = DoubleArray(6) { j -> steps[j] * 0.62 }
            onProgress(1f)
            yield()
        }
        return buildSolution(polished, target)
    }

    private data class Evaluation(val score: Double, val aligned: List<Vec2> = emptyList(), val shift: Int = 0, val reversed: Boolean = false, val angle: Double = 0.0, val translation: Vec2 = Vec2(0.0, 0.0))

    private fun randomFeasible(rng: Random): DoubleArray {
        repeat(250) {
            val x = DoubleArray(6) { j -> rng.nextDouble(lower[j], upper[j]) }
            if (mechanismPoses(FourBarDesign(x[0], x[1], x[2], x[3], x[4], x[5]), 24) != null) return x
        }
        // Guaranteed Grashof crank-rocker fallback.
        return doubleArrayOf(100.0, 30.0, 85.0, 70.0, rng.nextDouble(10.0, 100.0), rng.nextDouble(-PI, PI))
    }

    private fun evaluate(x: DoubleArray, target: List<Vec2>, shiftStep: Int = 2): Evaluation {
        val design = FourBarDesign(x[0], x[1], x[2], x[3], x[4], x[5])
        val poses = mechanismPoses(design, target.size) ?: return Evaluation(1e8)
        val raw = poses.map { it.p }
        var answer = Evaluation(1e8)
        for (reverse in listOf(false, true)) {
            val oriented = if (reverse) raw.reversed() else raw
            for (shift in target.indices step shiftStep) {
                val shifted = List(target.size) { oriented[(it + shift) % oriented.size] }
                val fit = align(shifted, target)
                val errors = fit.first.zip(target) { a, b -> a.distance(b) }
                val rms = sqrt(errors.sumOf { it * it } / errors.size)
                val maxError = errors.max()
                val singular = poses.count { abs(cross(it.c - it.b, it.d - it.c)) < 25.0 }.toDouble() / poses.size
                val score = rms + .22 * maxError + 8.0 * singular
                if (score < answer.score) answer = Evaluation(score, fit.first, shift, reverse, fit.second, fit.third)
            }
        }
        return answer
    }

    private fun buildSolution(x: DoubleArray, target: List<Vec2>): FourBarSolution {
        val d = FourBarDesign(x[0], x[1], x[2], x[3], x[4], x[5])
        val evaluation = evaluate(x, target, shiftStep = 1)
        var rawPoses = mechanismPoses(d, 180)!!
        if (evaluation.reversed) rawPoses = rawPoses.reversed()
        rawPoses = List(rawPoses.size) { rawPoses[(it + evaluation.shift * rawPoses.size / target.size) % rawPoses.size] }
        val alignedPoses = rawPoses.map { pose ->
            FourBarPose(transform(pose.a, evaluation.angle, evaluation.translation), transform(pose.b, evaluation.angle, evaluation.translation), transform(pose.c, evaluation.angle, evaluation.translation), transform(pose.d, evaluation.angle, evaluation.translation), transform(pose.p, evaluation.angle, evaluation.translation))
        }
        val errors = evaluation.aligned.zip(target) { a, b -> a.distance(b) }
        val links = listOf(d.l1, d.l2, d.l3, d.l4).sorted()
        val grashof = if (links.first() + links.last() <= links[1] + links[2]) "Grashof: rotación completa" else "No Grashof: movimiento oscilante"
        val rms = sqrt(errors.sumOf { it * it } / errors.size)
        val quality = when {
            rms <= 2.5 -> "Ajuste excelente"
            rms <= 5.0 -> "Ajuste bueno"
            rms <= 9.0 -> "Ajuste aproximado"
            else -> "La curva requiere más eslabones"
        }
        return FourBarSolution(d, target, evaluation.aligned, alignedPoses, rms, errors.max(), grashof, quality)
    }

    fun mechanismPoses(d: FourBarDesign, count: Int): List<FourBarPose>? {
        val result = ArrayList<FourBarPose>(count)
        var previous: Vec2? = null
        repeat(count) { i ->
            val theta = 2.0 * PI * i / count
            val a = Vec2(0.0, 0.0); val fixed = Vec2(d.l1, 0.0)
            val b = Vec2(d.l2 * cos(theta), d.l2 * sin(theta))
            val intersections = circleIntersections(b, d.l3, fixed, d.l4) ?: return null
            val c = previous?.let { p -> intersections.minBy { it.distance(p) } } ?: intersections.maxBy { it.y }
            previous = c
            val u = (c - b) * (1.0 / d.l3); val v = Vec2(-u.y, u.x)
            val p = b + u * (d.couplerRadius * cos(d.couplerAngle)) + v * (d.couplerRadius * sin(d.couplerAngle))
            result += FourBarPose(a, b, c, fixed, p)
        }
        return result.takeIf { it.size == count }
    }

    private fun circleIntersections(p0: Vec2, r0: Double, p1: Vec2, r1: Double): List<Vec2>? {
        val delta = p1 - p0; val distance = delta.norm()
        if (distance > r0 + r1 || distance < abs(r0 - r1) || distance < 1e-9) return null
        val a = (r0 * r0 - r1 * r1 + distance * distance) / (2 * distance)
        val h = sqrt(max(0.0, r0 * r0 - a * a)); val mid = p0 + delta * (a / distance)
        val side = Vec2(-delta.y / distance * h, delta.x / distance * h)
        return listOf(mid + side, mid - side)
    }

    private fun align(source: List<Vec2>, target: List<Vec2>): Triple<List<Vec2>, Double, Vec2> {
        val sc = centroid(source); val tc = centroid(target)
        var c = 0.0; var s = 0.0
        source.indices.forEach { i ->
            val a = source[i] - sc; val b = target[i] - tc
            c += a.x * b.x + a.y * b.y; s += a.x * b.y - a.y * b.x
        }
        val angle = atan2(s, c); val translation = tc - rotate(sc, angle)
        return Triple(source.map { transform(it, angle, translation) }, angle, translation)
    }

    internal fun prepareCurve(points: List<Vec2>, n: Int = samples): List<Vec2> {
        // Android can deliver repeated samples while the S Pen is momentarily still.
        // Removing zero-length segments prevents 0/0 during arc-length interpolation.
        val clean = ArrayList<Vec2>(points.size)
        points.filter { it.x.isFinite() && it.y.isFinite() }.forEach { point ->
            if (clean.isEmpty() || clean.last().distance(point) > 0.01) clean += point
        }
        require(clean.size >= 8) { "La curva necesita más puntos distintos" }
        val closed = if (clean.first().distance(clean.last()) < 2.0) clean else clean + clean.first()
        val lengths = closed.zipWithNext { a, b -> a.distance(b) }
        val total = lengths.sum(); require(total > 20.0) { "Dibuja una curva más grande" }
        val sampled = (0 until n).map { k ->
            val distance = total * k / n; var accumulated = 0.0; var index = 0
            while (index < lengths.lastIndex && accumulated + lengths[index] < distance) { accumulated += lengths[index]; index++ }
            val segmentLength = lengths[index]
            val t = if (segmentLength > 1e-9) ((distance - accumulated) / segmentLength).coerceIn(0.0, 1.0) else 0.0
            closed[index] + (closed[index + 1] - closed[index]) * t
        }
        val center = centroid(sampled)
        val width = sampled.maxOf { it.x } - sampled.minOf { it.x }
        val height = sampled.maxOf { it.y } - sampled.minOf { it.y }
        val scale = 100.0 / max(width, height).coerceAtLeast(1.0)
        return sampled.map { (it - center) * scale }.also { normalized ->
            require(normalized.all { it.x.isFinite() && it.y.isFinite() }) { "La curva contiene puntos no válidos" }
        }
    }

    private fun centroid(points: List<Vec2>) = Vec2(points.sumOf { it.x } / points.size, points.sumOf { it.y } / points.size)
    private fun rotate(p: Vec2, a: Double) = Vec2(cos(a) * p.x - sin(a) * p.y, sin(a) * p.x + cos(a) * p.y)
    private fun transform(p: Vec2, a: Double, t: Vec2) = rotate(p, a) + t
    private fun cross(a: Vec2, b: Vec2) = a.x * b.y - a.y * b.x
}
